"""
Configuración del Bot de Trading Deriv
"""
import os

# =============================================
# CONFIGURACIÓN DE API
# =============================================
# La API key se lee desde variable de entorno (GitHub Secrets)
# NUNCA hardcodear la key aquí en producción
_env_token = os.environ.get("DERIV_API_TOKEN")
API_TOKEN = _env_token.strip() if _env_token and _env_token.strip() else "hWG6PhodZEHSEiO"
APP_ID = 1089  # App ID oficial de Deriv (funciona con cuentas reales y demo)

# WebSocket endpoint
WS_URL = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"

# =============================================
# CONFIGURACIÓN DE TRADING
# =============================================
SYMBOL = "R_10"          # Volatility 10 Index (más estable / menor volatilidad)
STAKE_AMOUNT = 1.0       # $1 por operación
BASIS = "stake"          # Apostar monto fijo
DURATION = 5             # Duración del contrato
DURATION_UNIT = "t"      # 't' = ticks

# =============================================
# GESTIÓN DE RIESGO (ultra-conservador)
# =============================================
DAILY_PROFIT_TARGET = 50.0   # Detener si se ganan $50 en el día
DAILY_LOSS_LIMIT = 20.0      # Detener si se pierden $20 en el día
MAX_CONSECUTIVE_LOSSES = 5   # Detener si se pierden 5 operaciones seguidas
COOLDOWN_AFTER_LOSS = 30     # Segundos de pausa después de una pérdida
TRADE_INTERVAL = 15          # Segundos entre operaciones
MAX_TRADES_PER_DAY = 200     # Límite de operaciones por día

# =============================================
# ANÁLISIS TÉCNICO
# =============================================
TICK_HISTORY_COUNT = 20      # Número de ticks para analizar tendencia
RSI_PERIOD = 14              # Período del RSI
RSI_OVERSOLD = 35            # Umbral de sobreventa (comprar CALL)
RSI_OVERBOUGHT = 65          # Umbral de sobrecompra (comprar PUT)

# =============================================
# LOGGING
# =============================================
LOG_FILE = "trading_log.txt"
TRADES_CSV = "trades_history.csv"
