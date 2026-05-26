import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
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
            self.api_token = env_token.strip()
            logger.info("Usando API Token provisto por la variable de entorno de GitHub.")
        else:
            self.api_token = config.API_TOKEN.strip() if config.API_TOKEN else ""
            logger.info("Usando API Token predeterminado de la configuración (o vacío).")
            
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
        Estrategia Ultra Segura de Análisis Técnico
        Usa RSI e indicadores de tendencia sobre los últimos ticks.
        Retorna 'CALL' (comprar al alza), 'PUT' (comprar a la baja) o None (esperar).
        """
        if len(self.ticks_history) < config.TICK_HISTORY_COUNT:
            return None
            
        prices = self.ticks_history[-config.TICK_HISTORY_COUNT:]
        rsi = self.calculate_rsi(prices, config.RSI_PERIOD)
        
        # Calcular tendencia simple de corto plazo (últimos 5 ticks)
        short_term = prices[-5:]
        is_trending_up = all(short_term[i] > short_term[i-1] for i in range(1, len(short_term)))
        is_trending_down = all(short_term[i] < short_term[i-1] for i in range(1, len(short_term)))
        
        logger.info(f"Análisis Técnico -> Último precio: {prices[-1]} | RSI: {rsi:.2f}")

        # Filtro Ultra Seguro: Comprar CALL sólo si está en Sobreventa extrema Y empieza a subir
        if rsi <= config.RSI_OVERSOLD and is_trending_up:
            logger.info("🟢 SEÑAL DE COMPRA: Mercado sobrevendido con rebote alcista. Tipo: CALL (Subida)")
            return "CALL"
            
        # Comprar PUT sólo si está en Sobrecompra extrema Y empieza a bajar
        elif rsi >= config.RSI_OVERBOUGHT and is_trending_down:
            logger.info("🔴 SEÑAL DE VENTA: Mercado sobrecomprado con retroceso bajista. Tipo: PUT (Caída)")
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
            
            # Cargar historial de mercado inicial
            if not await self.fetch_tick_history():
                logger.error("No se pudo cargar el historial de ticks. Saliendo del programa.")
                return

            logger.info("==================================================")
            logger.info("        BOT INICIADO - OPERANDO EN VIVO           ")
            logger.info(f" Objetivo: +${config.DAILY_PROFIT_TARGET:.2f} | Límite Pérdida: -${config.DAILY_LOSS_LIMIT:.2f}")
            logger.info("==================================================")

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

        except Exception as e:
            logger.exception(f"Ocurrió un error inesperado durante la ejecución: {e}")
        finally:
            if self.ws:
                await self.ws.close()
                logger.info("Conexión WebSocket cerrada.")

if __name__ == "__main__":
    bot = DerivTradingBot()
    asyncio.run(bot.run())
