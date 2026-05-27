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

    async def subscribe_ticks(self):
        """Suscribirse a ticks en tiempo real (opcional para ejecución continua)"""
        # Para un bot de ejecución por pasos de bajo riesgo, podemos consultar el historial o suscribirnos.
        # Haremos consultas puntuales cada trade para mantener el WebSocket ligero y evitar saturación en GitHub Actions.
        pass

    def calculate_ema(self, prices, period):
        """Calcula la Media Móvil Exponencial (EMA) sobre los precios"""
        if len(prices) < period:
            return prices[-1]
        multiplier = 2 / (period + 1)
        ema = prices[0]
        for price in prices[1:]:
            ema = (price - ema) * multiplier + ema
        return ema

    def calculate_rsi(self, prices, period=14):
        """Calcula el RSI en base a una lista de precios pura (sin librerías pesadas)"""
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

    def get_market_signal(self):
        """
        Estrategia de Scalping Mejorada v2.0
        Combina EMA(10) + RSI(7) + Momentum de velas para mayor frecuencia de operaciones.
        - Nivel 1 (Fuerte): EMA confirma tendencia Y RSI en zona extrema -> Opera
        - Nivel 2 (Medio):  RSI en zona moderada + momentum de los últimos 3 ticks coincide -> Opera
        - Nivel 3 (Puro):   RSI extremo (sobreventa/sobrecompra absoluta) sin importar EMA -> Opera
        Retorna 'CALL', 'PUT' o None (esperar)
        """
        if len(self.ticks_history) < config.TICK_HISTORY_COUNT:
            return None

        prices = self.ticks_history[-config.TICK_HISTORY_COUNT:]
        current_price = prices[-1]

        # 1. Calcular indicadores
        rsi = self.calculate_rsi(prices, config.RSI_PERIOD)
        ema = self.calculate_ema(prices, config.EMA_PERIOD)
        ema_fast = self.calculate_ema(prices, 5)   # EMA rápida para confirmación

        # Tendencia general (EMA lenta)
        is_uptrend   = current_price > ema
        is_downtrend = current_price < ema

        # Momentum: dirección de los últimos 3 ticks consecutivos
        last3 = prices[-3:]
        momentum_up   = last3[-1] > last3[-2] > last3[-3]   # 3 velas verdes seguidas
        momentum_down = last3[-1] < last3[-2] < last3[-3]   # 3 velas rojas seguidas

        # Cruce de EMAs (5 cruza sobre 10 = señal)
        ema_cross_up   = ema_fast > ema   # EMA corta por encima -> alcista
        ema_cross_down = ema_fast < ema   # EMA corta por debajo -> bajista

        logger.info(
            f"Scalping v2 -> Precio: {current_price:.3f} | EMA10: {ema:.3f} | EMA5: {ema_fast:.3f} | "
            f"RSI({config.RSI_PERIOD}): {rsi:.2f} | Momentum: {'↑' if momentum_up else '↓' if momentum_down else '→'}"
        )

        # ── NIVEL 1: Tendencia EMA + RSI extremo (señal más fuerte) ──────────────
        if is_uptrend and rsi <= config.RSI_OVERSOLD:
            logger.info("🟢 [Nv1] Retroceso en tendencia alcista. CALL")
            return "CALL"
        if is_downtrend and rsi >= config.RSI_OVERBOUGHT:
            logger.info("🔴 [Nv1] Rebote en tendencia bajista. PUT")
            return "PUT"

        # ── NIVEL 2: Cruce de EMAs + Momentum confirmado ──────────────────────────
        if ema_cross_up and momentum_up and rsi < 55:
            logger.info("🟢 [Nv2] Cruce alcista + momentum positivo. CALL")
            return "CALL"
        if ema_cross_down and momentum_down and rsi > 45:
            logger.info("🔴 [Nv2] Cruce bajista + momentum negativo. PUT")
            return "PUT"

        # ── NIVEL 3: RSI absolutamente extremo (independiente de tendencia) ───────
        if rsi <= 22:
            logger.info("🟢 [Nv3] RSI en sobreventa absoluta. CALL")
            return "CALL"
        if rsi >= 78:
            logger.info("🔴 [Nv3] RSI en sobrecompra absoluta. PUT")
            return "PUT"

        return None

    async def execute_trade(self, contract_type):
        """Ejecuta una operación pidiendo propuesta y luego comprando"""
        logger.info(f"Iniciando compra de contrato {contract_type} de ${config.STAKE_AMOUNT}...")
        
        # 1. Solicitar Propuesta (Proposal)
        proposal_req = {
            "proposal": 1,
            "amount": config.STAKE_AMOUNT,
            "basis": config.BASIS,
            "contract_type": contract_type,
            "currency": "USD",
            "duration": config.DURATION,
            "duration_unit": config.DURATION_UNIT,
            "symbol": config.SYMBOL
        }
        
        proposal_res = await self.send_request(proposal_req)
        if "error" in proposal_res:
            logger.error(f"Error en la propuesta: {proposal_res['error']['message']}")
            return False
            
        proposal_id = proposal_res["proposal"]["id"]
        spot_price = proposal_res["proposal"]["spot"]
        logger.info(f"Propuesta recibida ID: {proposal_id} | Spot del mercado: {spot_price}")
        
        # 2. Comprar el Contrato
        buy_req = {
            "buy": proposal_id,
            "price": config.STAKE_AMOUNT
        }
        
        buy_res = await self.send_request(buy_req)
        if "error" in buy_res:
            logger.error(f"Error al comprar contrato: {buy_res['error']['message']}")
            return False
            
        contract_id = buy_res["buy"]["contract_id"]
        logger.info(f"Contrato comprado exitosamente! ID de Contrato: {contract_id}")
        self.total_trades += 1
        
        # 3. Esperar a que se resuelva el contrato (seguimiento)
        logger.info("Esperando resolución del contrato...")
        # Cada tick tarda 1 seg aprox. DURATION ticks = DURATION segundos.
        # Esperamos un poco más para asegurar el procesamiento en los servidores de Deriv.
        await asyncio.sleep(config.DURATION + 2)
        
        # Verificar resultado mediante el estado del contrato
        contract_status_req = {
            "proposal_open_contract": 1,
            "contract_id": contract_id
        }
        
        status_res = await self.send_request(contract_status_req)
        if "error" in status_res:
            logger.error(f"Error al verificar estado del contrato: {status_res['error']['message']}")
            # Alternativa: Actualizar balance y deducir ganancia/pérdida
            await self.update_balance()
            return False
            
        contract_data = status_res["proposal_open_contract"]
        is_expired = contract_data.get("is_expired", 0)
        
        # Si aún no ha expirado del todo en el WS, esperar un poco
        retries = 0
        while not is_expired and retries < 5:
            await asyncio.sleep(1)
            status_res = await self.send_request(contract_status_req)
            contract_data = status_res["proposal_open_contract"]
            is_expired = contract_data.get("is_expired", 0)
            retries += 1
            
        profit = float(contract_data.get("profit", 0.0))
        status = contract_data.get("status", "unknown") # 'won' o 'lost'
        
        logger.info(f"Contrato finalizado. Estado: {status.upper()} | Beneficio neto: ${profit:.2f}")
        
        # Registrar estadísticas de la sesión
        if profit > 0:
            self.wins += 1
            self.consecutive_losses = 0
            logger.info("🎉 Operación GANADA.")
        else:
            self.losses += 1
            self.consecutive_losses += 1
            logger.warning(f"⚠️ Operación PERDIDA. Racha de pérdidas: {self.consecutive_losses}")
            # Cooldown después de pérdida
            if config.COOLDOWN_AFTER_LOSS > 0:
                logger.info(f"Entrando en periodo de enfriamiento de {config.COOLDOWN_AFTER_LOSS} segundos...")
                await asyncio.sleep(config.COOLDOWN_AFTER_LOSS)

        # Actualizar balance de la cuenta
        await self.update_balance()
        
        # Escribir en registro CSV
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(config.TRADES_CSV, "a", encoding="utf-8") as f:
            f.write(f"{timestamp},{contract_type},{config.STAKE_AMOUNT},{profit},{status},{self.current_balance}\n")
            
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
                f"🤖 *Deriv Scalper Bot - Jornada Iniciada*\n"
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
                # Consultamos de nuevo el historial para obtener el tick más reciente
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
                    if latest_price != self.ticks_history[-1]:
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
                f"{status_emoji} *Deriv Scalper Bot - Reporte Diario*\n"
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
                f"⚠️ *Deriv Scalper Bot - ALERTA DE ERROR*\n"
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
