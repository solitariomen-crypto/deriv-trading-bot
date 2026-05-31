import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
import urllib.parse
import urllib.request
import websockets

# Importar configuración
try:
    import config
except ImportError:
    # Si se ejecuta desde otra ruta
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    import config

# Configuración de logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("DerivBot")

class DerivTradingBot:
    def __init__(self):
        env_token = os.environ.get("DERIV_API_TOKEN")
        if env_token and env_token.strip():
            # Limpiar espacios y comillas accidentales que invalidan la estructura del token
            self.api_token = env_token.strip().replace('"', '').replace("'", "")
            logger.info("Usando API Token provisto por la variable de entorno de GitHub.")
        else:
            raw_token = config.API_TOKEN if config.API_TOKEN else ""
            if not raw_token or not raw_token.strip():
                raw_token = "hWG6PhodZEHSEiO"
            self.api_token = raw_token.strip().replace('"', '').replace("'", "")
            logger.info("Usando API Token predeterminado de la configuración.")
            
        self.ws_url = config.WS_URL
        self.ws = None
        self.initial_balance = None
        self.current_balance = None
        self.session_profit = 0.0
        self.consecutive_losses = 0
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.ticks_history = []
        self.running = True
        self.account_balances = []   # Lista de todas las cuentas (demo + real)

    async def connect(self):
        """Establece conexión WebSocket con Deriv"""
        logger.info(f"Conectando a {self.ws_url}...")
        self.ws = await websockets.connect(self.ws_url)
        logger.info("Conexión WebSocket establecida.")

    async def send_request(self, request_data):
        """Envía una petición al WebSocket y retorna la respuesta"""
        await self.ws.send(json.dumps(request_data))
        response = await self.ws.recv()
        return json.loads(response)

    async def authorize(self):
        """Autoriza la sesión con el API Token"""
        if not self.api_token:
            err_msg = "El API Token de Deriv no está configurado (está vacío). Por favor configúralo en config.py o en los Secrets de tu repositorio en GitHub como DERIV_API_TOKEN."
            logger.error(err_msg)
            raise Exception(err_msg)

        logger.info("Autorizando token de API...")
        auth_req = {"authorize": self.api_token}
        res = await self.send_request(auth_req)
        
        if "error" in res:
            logger.error(f"Error de autorización: {res['error']['message']}")
            if res['error']['code'] == 'InvalidToken':
                logger.error("👉 Tu token de API es inválido o ha expirado. Por favor genera uno nuevo en la web de Deriv.")
            raise Exception(f"Fallo en la autorización: {res['error']['message']}")
        
        auth_data = res["authorize"]
        self.current_balance = float(auth_data["balance"])
        self.initial_balance = self.current_balance
        logger.info(f"Autorización exitosa. Usuario: {auth_data['email']}")
        logger.info(f"Balance inicial de la cuenta: ${self.current_balance:.2f} {auth_data['currency']}")
        
        # Guardar en archivo CSV un encabezado si no existe
        if not os.path.exists(config.TRADES_CSV):
            with open(config.TRADES_CSV, "w", encoding="utf-8") as f:
                f.write("timestamp,trade_type,stake,profit_loss,status,balance\n")

    def send_whatsapp(self, message):
        """Envía una notificación de WhatsApp usando la API gratuita de CallMeBot"""
        enabled = os.environ.get("WHATSAPP_ENABLED", "true" if config.WHATSAPP_ENABLED else "false").lower() == "true"
        if not enabled:
            return
            
        phone = os.environ.get("WHATSAPP_PHONE") or config.WHATSAPP_PHONE
        apikey = os.environ.get("WHATSAPP_API_KEY") or config.WHATSAPP_API_KEY
        
        if not phone or not apikey:
            logger.warning("⚠️ WhatsApp habilitado pero falta configurar el teléfono o la API key.")
            return
            
        phone_clean = "".join([c for c in phone.strip() if c.isdigit() or c == "+"])
        
        try:
            encoded_msg = urllib.parse.quote(message)
            url = f"https://api.callmebot.com/whatsapp.php?phone={phone_clean}&text={encoded_msg}&apikey={apikey.strip()}"
            
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                status = response.getcode()
                if status == 200:
                    logger.info("📱 Notificación de WhatsApp enviada con éxito.")
                else:
                    logger.error(f"❌ Error al enviar WhatsApp. Código HTTP: {status}")
        except Exception as e:
            logger.error(f"❌ Excepción al intentar enviar WhatsApp: {e}")

    async def fetch_all_accounts(self):
        """Obtiene los saldos de TODAS las cuentas (demo y reales) asociadas al token"""
        logger.info("Consultando saldos de todas las cuentas (demo + real)...")
        self.account_balances = []
        try:
            res = await self.send_request({"balance": 1, "account": "all"})
            if "error" in res:
                logger.warning(f"No se pudieron obtener todos los saldos: {res['error']['message']}")
                return
            
            accounts = res.get("balance", {}).get("accounts", {})
            for login_id, data in accounts.items():
                account_type = "DEMO" if data.get("demo_account", 0) == 1 else "REAL"
                currency = data.get("currency", "USD")
                balance = float(data.get("balance", 0))
                self.account_balances.append({
                    "id": login_id,
                    "type": account_type,
                    "currency": currency,
                    "balance": balance
                })
                logger.info(f"  [{account_type}] Cuenta {login_id}: {balance:.2f} {currency}")
        except Exception as e:
            logger.warning(f"Error al consultar todas las cuentas: {e}")

    def format_accounts_for_whatsapp(self):
        """Formatea la lista de cuentas para el mensaje de WhatsApp"""
        if not self.account_balances:
            return "  (No disponible)"
        demos = [a for a in self.account_balances if a["type"] == "DEMO"]
        reals = [a for a in self.account_balances if a["type"] == "REAL"]
        lines = []
        if reals:
            lines.append("💳 *Cuentas REALES:*")
            for a in reals:
                lines.append(f"   • {a['id']}: {a['balance']:.2f} {a['currency']}")
        if demos:
            lines.append("🧪 *Cuentas DEMO:*")
            for a in demos:
                lines.append(f"   • {a['id']}: {a['balance']:.2f} {a['currency']}")
        return "\n".join(lines)

    async def update_balance(self):
        """Solicita el balance actual de la cuenta"""
        res = await self.send_request({"balance": 1})
        if "balance" in res:
            self.current_balance = float(res["balance"]["balance"])
            self.session_profit = self.current_balance - self.initial_balance
            logger.info(f"Balance actualizado: ${self.current_balance:.2f} | Ganancia del día: ${self.session_profit:.2f}")

    async def fetch_tick_history(self):
        """Obtiene el historial inicial de ticks para el análisis técnico"""
        logger.info(f"Solicitando historial de ticks para {config.SYMBOL}...")
        req = {
            "ticks_history": config.SYMBOL,
            "adjust_start_time": 1,
            "count": config.TICK_HISTORY_COUNT,
            "end": "latest",
            "style": "ticks"
        }
        res = await self.send_request(req)
        if "error" in res:
            logger.error(f"Error al obtener ticks: {res['error']['message']}")
            return False
        
        self.ticks_history = [float(t) for t in res["history"]["prices"]]
        logger.info(f"Historial cargado. {len(self.ticks_history)} ticks obtenidos. Último precio: {self.ticks_history[-1]}")
        return True

    def calculate_bollinger_bands(self, prices, period=20, std_dev=2.0):
        """Calcula las Bandas de Bollinger (Superior, Media, Inferior)"""
        if len(prices) < period:
            return None, None, None
        recent_prices = prices[-period:]
        sma = sum(recent_prices) / period
        variance = sum((p - sma) ** 2 for p in recent_prices) / period
        std = variance ** 0.5
        upper = sma + std_dev * std
        lower = sma - std_dev * std
        return upper, sma, lower

    def calculate_rsi(self, prices, period=14):
        """Calcula el RSI en base a una lista de precios pura"""
        if len(prices) < period + 1:
            return 50.0 # Neutro por defecto
        
        changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [c if c > 0 else 0 for c in changes]
        losses = [-c if c < 0 else 0 for c in changes]
        
        # Promedio inicial
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        if avg_loss == 0:
            return 100.0
            
        for i in range(period, len(changes)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
        if avg_loss == 0:
            return 100.0
            
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    def calculate_stochastic(self, prices, k_period=14, d_period=3):
        """Calcula el Oscilador Estocástico (%K y %D) sobre ticks"""
        if len(prices) < k_period + d_period:
            return 50.0, 50.0  # Neutro por defecto
        
        k_values = []
        # Calcular %K para los últimos d_period elementos para obtener la SMA del %D
        for i in range(len(prices) - d_period, len(prices)):
            window = prices[i - k_period + 1 : i + 1]
            current_close = window[-1]
            lowest_low = min(window)
            highest_high = max(window)
            
            if highest_high == lowest_low:
                k = 50.0
            else:
                k = ((current_close - lowest_low) / (highest_high - lowest_low)) * 100
              
            k_values.append(k)
            
        current_k = k_values[-1]
        current_d = sum(k_values) / len(k_values)
        return current_k, current_d

    def get_market_signal(self):
        """
        Estrategia de Scalping Inteligente y Flexible v4.0 (Sistema de Scoring Ponderado)
        Usa Bandas de Bollinger, RSI y Estocástico con puntuación flexible.
        Puntuación máxima teórica: 9 puntos.
        Entrada permitida si:
        - Score >= 6 (Excelente probabilidad)
        - Momentum inmediato está a nuestro favor (evita que el precio se venga en contra).
        """
        if len(self.ticks_history) < config.TICK_HISTORY_COUNT:
            return None

        prices = self.ticks_history[-config.TICK_HISTORY_COUNT:]
        current_price = prices[-1]
        prev_price = prices[-2]

        # 1. Calcular indicadores técnicos
        upper_band, middle_band, lower_band = self.calculate_bollinger_bands(prices, config.BB_PERIOD, config.BB_STD_DEV)
        rsi = self.calculate_rsi(prices, config.RSI_PERIOD)
        stoch_k, stoch_d = self.calculate_stochastic(prices, config.STOCH_K_PERIOD, config.STOCH_D_PERIOD)

        if upper_band is None or middle_band is None or lower_band is None:
            return None

        # Rango de proximidad a las bandas
        bb_width = upper_band - lower_band
        bb_margin = bb_width * 0.15 if bb_width > 0 else 0.0

        # Dirección del último tick (Momentum para evitar entrar en contra)
        is_rebound_up = current_price > prev_price
        is_rebound_down = current_price < prev_price

        # --- EVALUACIÓN DE SEÑAL ALCISTA (CALL) ---
        call_score = 0
        
        # Bollinger (Max 3 pts)
        if current_price <= lower_band:
            call_score += 3  # Fuera o tocando la banda inferior (soporte fuerte)
        elif current_price <= lower_band + bb_margin:
            call_score += 2  # Muy cerca de la banda inferior (soporte moderado)
        elif current_price < middle_band:
            call_score += 1  # Por debajo de la media móvil

        # RSI (Max 3 pts)
        if rsi <= 30:
            call_score += 3  # Sobreventa extrema
        elif rsi <= config.RSI_OVERSOLD:
            call_score += 2  # Sobreventa moderada
        elif rsi <= 45:
            call_score += 1  # Ligera sobreventa

        # Estocástico (Max 3 pts)
        if stoch_k <= 20 and stoch_d <= 20:
            call_score += 2  # Ambos en sobreventa profunda
        elif stoch_k <= config.STOCH_OVERSOLD and stoch_d <= config.STOCH_OVERSOLD:
            call_score += 1  # Ambos en sobreventa moderada
        
        if stoch_k > stoch_d:
            call_score += 1  # Cruce o alineación alcista activa

        # --- EVALUACIÓN DE SEÑAL BAJISTA (PUT) ---
        put_score = 0
        
        # Bollinger (Max 3 pts)
        if current_price >= upper_band:
            put_score += 3  # Fuera o tocando la banda superior (resistencia fuerte)
        elif current_price >= upper_band - bb_margin:
            put_score += 2  # Muy cerca de la banda superior (resistencia moderada)
        elif current_price > middle_band:
            put_score += 1  # Por encima de la media móvil

        # RSI (Max 3 pts)
        if rsi >= 70:
            put_score += 3  # Sobrecompra extrema
        elif rsi >= config.RSI_OVERBOUGHT:
            put_score += 2  # Sobrecompra moderada
        elif rsi >= 55:
            put_score += 1  # Ligera sobrecompra

        # Estocástico (Max 3 pts)
        if stoch_k >= 80 and stoch_d >= 80:
            put_score += 2  # Ambos en sobrecompra profunda
        elif stoch_k >= config.STOCH_OVERBOUGHT and stoch_d >= config.STOCH_OVERBOUGHT:
            put_score += 1  # Ambos en sobrecompra moderada
        
        if stoch_k < stoch_d:
            put_score += 1  # Cruce o alineación bajista activa

        logger.info(
            f"Estrategia Scoring -> Precio: {current_price:.3f} | RSI: {rsi:.1f} | "
            f"Stoch %K: {stoch_k:.1f}/%D: {stoch_d:.1f} | "
            f"CALL Score: {call_score}/9 | PUT Score: {put_score}/9"
        )

        # Umbral de decisión: Score >= 6 y momentum inmediato a favor
        if call_score >= 6 and is_rebound_up:
            logger.info(f"🟢 SEÑAL DE COMPRA FLEXIBLE (Score: {call_score}/9 + Momentum): Comprando MULTUP (CALL)")
            return "CALL"
            
        if put_score >= 6 and is_rebound_down:
            logger.info(f"🔴 SEÑAL DE VENTA FLEXIBLE (Score: {put_score}/9 + Momentum): Comprando MULTDOWN (PUT)")
            return "PUT"

        return None

    async def execute_trade(self, contract_type):
        """Ejecuta una operación multiplicadora y la gestiona activamente (TP 10% / SL 30%)"""
        deriv_contract_type = "MULTUP" if contract_type == "CALL" else "MULTDOWN"
        logger.info(f"Iniciando propuesta de Multiplicador {deriv_contract_type} de ${config.STAKE_AMOUNT}...")
        
        # 1. Solicitar Propuesta (Proposal) para Multiplicador
        proposal_req = {
            "proposal": 1,
            "amount": config.STAKE_AMOUNT,
            "basis": "stake",
            "contract_type": deriv_contract_type,
            "currency": "USD",
            "multiplier": config.MULTIPLIER,
            "symbol": config.SYMBOL
        }
        
        proposal_res = await self.send_request(proposal_req)
        if "error" in proposal_res:
            logger.error(f"Error en la propuesta de multiplicador: {proposal_res['error']['message']}")
            return False
            
        proposal_id = proposal_res["proposal"]["id"]
        spot_price = proposal_res["proposal"]["spot"]
        logger.info(f"Propuesta de Multiplicador recibida ID: {proposal_id} | Spot: {spot_price}")
        
        # 2. Comprar el Contrato
        buy_req = {
            "buy": proposal_id,
            "price": config.STAKE_AMOUNT
        }
        
        buy_res = await self.send_request(buy_req)
        if "error" in buy_res:
            logger.error(f"Error al comprar contrato multiplicador: {buy_res['error']['message']}")
            return False
            
        contract_id = buy_res["buy"]["contract_id"]
        logger.info(f"¡Contrato Multiplicador comprado con éxito! ID: {contract_id}")
        self.total_trades += 1
        
        # 3. Monitoreo Activo del Contrato (TP 10% / SL 30%)
        logger.info("Iniciando monitoreo dinámico del contrato...")
        start_time = time.time()
        final_profit = 0.0
        final_status = "lost"
        is_sold = False
        
        while (time.time() - start_time) < config.MAX_CONTRACT_WAIT:
            await asyncio.sleep(config.CONTRACT_POLL_INTERVAL)
            
            # Consultar estado actual del contrato
            contract_status_req = {
                "proposal_open_contract": 1,
                "contract_id": contract_id
            }
            status_res = await self.send_request(contract_status_req)
            if "error" in status_res:
                logger.error(f"Error al verificar contrato abierto: {status_res['error']['message']}")
                continue
                
            contract_data = status_res["proposal_open_contract"]
            status = contract_data.get("status", "open")
            is_expired = contract_data.get("is_expired", 0)
            
            # Si ya se cerró en el servidor por sí mismo
            if status != "open" or is_expired == 1:
                final_profit = float(contract_data.get("profit", 0.0))
                final_status = status
                logger.info(f"El contrato se cerró automáticamente en el servidor. Estado: {final_status.upper()} | Profit: ${final_profit:.2f}")
                break
                
            # Calcular profit actual y porcentaje
            profit = float(contract_data.get("profit", 0.0))
            stake = float(contract_data.get("buy_price", config.STAKE_AMOUNT))
            profit_pct = profit / stake
            
            logger.info(f"Monitoreo -> Profit: ${profit:.2f} ({profit_pct*100:.1f}%) | Tiempo: {int(time.time() - start_time)}s")
            
            # Verificar si se cumple Take Profit (10%)
            if profit_pct >= config.TAKE_PROFIT_PCT:
                logger.info(f"🎯 ¡OBJETIVO DE GANANCIA DE {config.TAKE_PROFIT_PCT*100:.1f}% ALCANZADO! Vendiendo contrato early...")
                sell_req = {
                    "sell": contract_id,
                    "price": 0
                }
                sell_res = await self.send_request(sell_req)
                if "error" in sell_res:
                    logger.error(f"Error al intentar vender anticipadamente (TP): {sell_res['error']['message']}")
                else:
                    logger.info("¡Venta anticipada exitosa!")
                    is_sold = True
                    
            # Verificar si se cumple Stop Loss (30%)
            elif profit_pct <= -config.STOP_LOSS_PCT:
                logger.warning(f"🛑 ¡LÍMITE DE PÉRDIDA DE {config.STOP_LOSS_PCT*100:.1f}% ALCANZADO! Vendiendo contrato early para detener pérdidas...")
                sell_req = {
                    "sell": contract_id,
                    "price": 0
                }
                sell_res = await self.send_request(sell_req)
                if "error" in sell_res:
                    logger.error(f"Error al intentar vender anticipadamente (SL): {sell_res['error']['message']}")
                else:
                    logger.warning("¡Venta anticipada de protección ejecutada exitosamente!")
                    is_sold = True
            
            # Si se vendió con éxito, obtener el resultado final
            if is_sold:
                # Esperar 1 segundo y pedir el reporte final del contrato cerrado
                await asyncio.sleep(1)
                final_res = await self.send_request({"proposal_open_contract": 1, "contract_id": contract_id})
                if "proposal_open_contract" in final_res:
                    final_data = final_res["proposal_open_contract"]
                    final_profit = float(final_data.get("profit", profit))
                    final_status = final_data.get("status", "won" if final_profit > 0 else "lost")
                else:
                    final_profit = profit
                    final_status = "won" if final_profit > 0 else "lost"
                break
        else:
            # Límite de tiempo excedido, vender por seguridad
            logger.warning("⏳ Tiempo máximo de espera del contrato excedido. Cerrando por seguridad...")
            sell_res = await self.send_request({"sell": contract_id, "price": 0})
            await asyncio.sleep(1)
            final_res = await self.send_request({"proposal_open_contract": 1, "contract_id": contract_id})
            if "proposal_open_contract" in final_res:
                final_data = final_res["proposal_open_contract"]
                final_profit = float(final_data.get("profit", 0.0))
                final_status = final_data.get("status", "won" if final_profit > 0 else "lost")
            else:
                final_profit = 0.0
                final_status = "lost"

        # Registrar estadísticas de la sesión
        if final_profit > 0:
            self.wins += 1
            self.consecutive_losses = 0
            logger.info(f"🎉 Operación GANADA. Beneficio: +${final_profit:.2f}")
        else:
            self.losses += 1
            self.consecutive_losses += 1
            logger.warning(f"⚠️ Operación PERDIDA o CERRADA EN NEGATIVO. Racha de pérdidas: {self.consecutive_losses} | Resultado: ${final_profit:.2f}")
            # Cooldown después de pérdida
            if config.COOLDOWN_AFTER_LOSS > 0:
                logger.info(f"Entrando en periodo de enfriamiento de {config.COOLDOWN_AFTER_LOSS} segundos...")
                await asyncio.sleep(config.COOLDOWN_AFTER_LOSS)

        # Actualizar balance de la cuenta
        await self.update_balance()
        
        # Escribir en registro CSV
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(config.TRADES_CSV, "a", encoding="utf-8") as f:
            f.write(f"{timestamp},MULTIPLIER_{contract_type},{config.STAKE_AMOUNT},{final_profit},{final_status},{self.current_balance}\n")
            
        return True

    async def run(self):
        """Ciclo principal de ejecución del bot"""
        try:
            await self.connect()
            await self.authorize()

            # Obtener saldos de TODAS las cuentas (demo + real)
            await self.fetch_all_accounts()

            # Cargar historial de mercado inicial
            if not await self.fetch_tick_history():
                logger.error("No se pudo cargar el historial de ticks. Saliendo del programa.")
                return

            logger.info("==================================================")
            logger.info("        BOT INICIADO - OPERANDO EN VIVO           ")
            logger.info(f" Objetivo: +${config.DAILY_PROFIT_TARGET:.2f} | Límite Pérdida: -${config.DAILY_LOSS_LIMIT:.2f}")
            logger.info("==================================================")

            # Enviar notificación de inicio de jornada por WhatsApp (con saldos)
            accounts_text = self.format_accounts_for_whatsapp()
            self.send_whatsapp(
                f"🤖 *Deriv Multiplier Bot - Jornada Iniciada*\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"{accounts_text}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🎯 *Objetivo diario:* +${config.DAILY_PROFIT_TARGET:.2f} USD\n"
                f"🛑 *Límite de pérdida:* -${config.DAILY_LOSS_LIMIT:.2f} USD\n"
                f"📊 *Mercado:* Volatility {config.SYMBOL}\n"
                f"⏱️ *Hora:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
            )

            while self.running:
                # 1. Verificar condiciones de parada (Take Profit / Stop Loss)
                if self.session_profit >= config.DAILY_PROFIT_TARGET:
                    logger.info(f"🎯 OBJETIVO DIARIO ALCANZADO: +${self.session_profit:.2f}. Deteniendo bot para asegurar ganancias.")
                    self.running = False
                    break
                    
                if self.session_profit <= -config.DAILY_LOSS_LIMIT:
                    logger.critical(f"🛑 LÍMITE DE PÉRDIDA DIARIA ALCANZADO: -${abs(self.session_profit):.2f}. Deteniendo bot para proteger capital.")
                    self.running = False
                    break

                if self.consecutive_losses >= config.MAX_CONSECUTIVE_LOSSES:
                    logger.critical(f"🛑 RACHA CRÍTICA DE PÉRDIDAS ALCANZADA: {self.consecutive_losses} seguidas. Deteniendo bot.")
                    self.running = False
                    break

                if self.total_trades >= config.MAX_TRADES_PER_DAY:
                    logger.info(f"⏳ LÍMITE DE OPERACIONES DIARIAS ALCANZADO ({config.MAX_TRADES_PER_DAY}). Deteniendo bot.")
                    self.running = False
                    break

                # 2. Actualizar datos de mercado (obtener último tick)
                tick_req = {
                    "ticks_history": config.SYMBOL,
                    "adjust_start_time": 1,
                    "count": 1,
                    "end": "latest",
                    "style": "ticks"
                }
                tick_res = await self.send_request(tick_req)
                if "history" in tick_res and len(tick_res["history"]["prices"]) > 0:
                    latest_price = float(tick_res["history"]["prices"][0])
                    # Mantener el tamaño de la lista
                    if not self.ticks_history or latest_price != self.ticks_history[-1]:
                        self.ticks_history.append(latest_price)
                        if len(self.ticks_history) > config.TICK_HISTORY_COUNT:
                            self.ticks_history.pop(0)

                # 3. Analizar mercado para obtener señales
                signal = self.get_market_signal()
                
                if signal:
                    # Ejecutar la operación según la señal
                    await self.execute_trade(signal)
                else:
                    # Esperar antes del siguiente análisis
                    await asyncio.sleep(config.TRADE_INTERVAL)

            # Resumen al finalizar la jornada
            logger.info("==================================================")
            logger.info("            JORNADA DE TRADING FINALIZADA          ")
            logger.info(f" Trades Totales: {self.total_trades} | Ganados: {self.wins} | Perdidos: {self.losses}")
            logger.info(f" Balance Inicial: ${self.initial_balance:.2f} | Balance Final: ${self.current_balance:.2f}")
            logger.info(f" Ganancia/Pérdida neta: ${self.session_profit:.2f}")
            logger.info("==================================================")

            # Actualizar saldos de todas las cuentas para el reporte final
            await self.fetch_all_accounts()
            accounts_text = self.format_accounts_for_whatsapp()

            # Eficiencia de la sesión
            win_rate = (self.wins / self.total_trades * 100) if self.total_trades > 0 else 0.0

            # Generar estado de finalización y enviar notificación final
            status_emoji = "🎯" if self.session_profit >= config.DAILY_PROFIT_TARGET else "🛑" if self.session_profit <= -config.DAILY_LOSS_LIMIT else "⏳"
            status_text = "META ALCANZADA ✅" if self.session_profit >= config.DAILY_PROFIT_TARGET else "STOP LOSS ALCANZADO" if self.session_profit <= -config.DAILY_LOSS_LIMIT else "FIN DE JORNADA"

            self.send_whatsapp(
                f"{status_emoji} *Deriv Multiplier Bot - Reporte Diario*\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📝 *Estado:* {status_text}\n"
                f"📈 *Resultado Neto:* {'+' if self.session_profit >= 0 else ''}${self.session_profit:.2f} USD\n"
                f"🔄 *Operaciones:* {self.total_trades} total\n"
                f"   🟢 Ganadas: {self.wins}  |  🔴 Perdidas: {self.losses}\n"
                f"   📊 Efectividad: {win_rate:.1f}%\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💰 *Saldos Actualizados:*\n"
                f"{accounts_text}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"⏱️ {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
            )

        except Exception as e:
            err_msg = f"Ocurrió un error inesperado durante la ejecución: {e}"
            logger.exception(err_msg)
            
            # Enviar notificación de error
            self.send_whatsapp(
                f"⚠️ *Deriv Multiplier Bot - ALERTA DE ERROR*\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🚨 El bot se ha detenido debido a un error crítico:\n"
                f"`{str(e)}`"
            )
        finally:
            if self.ws:
                await self.ws.close()
                logger.info("Conexión WebSocket cerrada.")

if __name__ == "__main__":
    bot = DerivTradingBot()
    asyncio.run(bot.run())
