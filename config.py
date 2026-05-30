"""
Configuración del Bot Deriv - Contratos Multiplicadores con Triple Confirmación
"""
import os

# =============================================
# CONFIGURACIÓN DE API
# =============================================
_env_token = os.environ.get("DERIV_API_TOKEN")
API_TOKEN = _env_token.strip() if _env_token and _env_token.strip() else "hWG6PhodZEHSEiO"
APP_ID = 1089
WS_URL = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"

# =============================================
# CONFIGURACIÓN DE CONTRATOS MULTIPLICADORES
# =============================================
SYMBOL = "R_10"          # Volatility 10 Index (el más estable de Deriv)
STAKE_AMOUNT = 1.0       # $1 por operación
MULTIPLIER = 400         # Multiplicador 400x (el más conservador disponible para R_10)

# TP/SL automático en el servidor de Deriv
TAKE_PROFIT_PCT = 0.10   # Cerrar al ganar +10% del stake  → +$0.10 en $1
STOP_LOSS_PCT   = 0.30   # Cerrar al perder -30% del stake → -$0.30 en $1

# Monitoreo del contrato abierto
MAX_CONTRACT_WAIT      = 300   # Segundos máximos por contrato (5 min)
CONTRACT_POLL_INTERVAL = 3     # Segundos entre consultas de estado

# =============================================
# GESTIÓN DE RIESGO DIARIA
# =============================================
DAILY_PROFIT_TARGET    = 50.0  # Parar al ganar $50 en el día
DAILY_LOSS_LIMIT       = 20.0  # Parar al perder $20 en el día
MAX_CONSECUTIVE_LOSSES = 5     # Parar con 5 pérdidas seguidas
COOLDOWN_AFTER_LOSS    = 30    # Segundos de pausa tras pérdida
TRADE_INTERVAL         = 10    # Segundos entre análisis sin señal
MAX_TRADES_PER_DAY     = 100   # Límite de operaciones diarias

# =============================================
# ANÁLISIS TÉCNICO - TRIPLE CONFIRMACIÓN
# Bollinger Bands + RSI + Estocástico
# =============================================
TICK_HISTORY_COUNT = 60    # Historial amplio para calcular los 3 indicadores

# Bandas de Bollinger
BB_PERIOD  = 20
BB_STD_DEV = 2.0

# RSI (Relative Strength Index)
RSI_PERIOD     = 14
RSI_OVERSOLD   = 35   # Zona de compra
RSI_OVERBOUGHT = 65   # Zona de venta

# Oscilador Estocástico (%K y %D)
STOCH_K_PERIOD   = 14
STOCH_D_PERIOD   = 3
STOCH_OVERSOLD   = 25   # Zona de compra
STOCH_OVERBOUGHT = 75   # Zona de venta

# =============================================
# LOGGING
# =============================================
LOG_FILE   = "trading_log.txt"
TRADES_CSV = "trades_history.csv"

# =============================================
# NOTIFICACIONES WHATSAPP (CallMeBot)
# =============================================
WHATSAPP_ENABLED = True
WHATSAPP_PHONE   = "+584141629417"
WHATSAPP_API_KEY = "3610205"
