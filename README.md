# 🤖 Bot de Trading Ultra-Seguro para Deriv (Automatizado en la Nube)

Este sistema de trading algorítmico automatizado está diseñado para ejecutarse diariamente en la nube utilizando **GitHub Actions**. Opera de forma ultra-segura aplicando filtros de gestión de riesgo estrictos y un algoritmo de análisis técnico en tiempo real a través de WebSockets de Deriv.

---

## ⚙️ Características del Bot

1. **Operación Asíncrona Directa**: Conectado directamente a las APIs WebSocket de Deriv utilizando la biblioteca `websockets` en Python. Sin intermediarios pesados.
2. **Gestión de Riesgo Estricta (Ultra-Seguro)**:
   - **Monto por Operación**: $1.00 USD fijo (configurable en `config.py`).
   - **Objetivo diario (Take Profit)**: Detiene inmediatamente la ejecución cuando alcanza **$50.00 USD de ganancia**.
   - **Límite de pérdida diaria (Stop Loss)**: Detiene el bot si se acumulan pérdidas por valor de **$20.00 USD** para proteger tu capital.
   - **Límite de pérdidas consecutivas**: Freno automático de emergencia si ocurren **5 pérdidas seguidas**.
   - **Período de Enfriamiento (Cooldown)**: Espera **30 segundos** antes de reintentar tras una pérdida para evitar sobreoperar en mercados desfavorables.
3. **Estrategia Basada en Tendencia y RSI**:
   - Analiza en tiempo real los ticks del índice **Volatility 10 (R_10)** (el índice sintético más estable de Deriv).
   - Calcula el RSI de forma nativa.
   - **Señal CALL (Compra)**: Ejecutada únicamente si el RSI está por debajo de **35** (sobreventa) Y el precio muestra un cambio de tendencia al alza en los últimos 5 ticks.
   - **Señal PUT (Venta)**: Ejecutada únicamente si el RSI está por encima de **65** (sobrecompra) Y el precio muestra un cambio de tendencia a la baja en los últimos 5 ticks.
4. **Ejecución Diaria en la Nube**: Configurado para ejecutarse de forma gratuita y automática usando **GitHub Actions (Cron)** todos los días.

---

## 📁 Archivos del Proyecto

*   `config.py`: Parámetros de la estrategia, credenciales de API, y reglas de gestión de capital.
*   `bot.py`: Código fuente principal del bot con la lógica asíncrona de trading, algoritmos e indicadores.
*   `requirements.txt`: Dependencias de librerías de Python.
*   `.github/workflows/daily_trading.yml`: Automatización diaria en GitHub.

---

## 🚀 Guía de Instalación y Despliegue en la Nube

Para ejecutar este bot en la nube de forma **100% gratuita** y diaria, sigue estos pasos estructurados:

### Paso 1: Crear un Repositorio en GitHub
1. Entra a tu cuenta de [GitHub](https://github.com/).
2. Crea un nuevo repositorio (puede ser **Privado** para mayor seguridad de tus credenciales).
3. Sube todos los archivos de esta carpeta (`config.py`, `bot.py`, `requirements.txt` y la carpeta `.github`) a tu nuevo repositorio.

### Paso 2: Configurar tu API Key de manera Ultra-Segura (Secrets)
Para evitar exponer tu API Token de Deriv en el código público:
1. En tu repositorio de GitHub, ve a **Settings** (Configuración) -> **Secrets and variables** -> **Actions**.
2. Haz clic en **New repository secret** (Nuevo secreto del repositorio).
3. Configúralo así:
   - **Name**: `DERIV_API_TOKEN`
   - **Value**: *Coloca aquí tu API token actualizado de Deriv (por ejemplo, el nuevo token que generes).*
4. Guarda el secreto. GitHub lo enmascarará y lo inyectará de forma invisible en la nube al ejecutarse.

### Paso 3: Activación y Monitoreo del Bot
*   **Ejecución Automática**: GitHub Actions ejecutará el bot de forma automática **todos los días** a la hora configurada en el cron (`.github/workflows/daily_trading.yml`).
*   **Ejecución Manual (Para probarlo hoy mismo)**:
    1. En tu repositorio de GitHub, haz clic en la pestaña **Actions** (Acciones).
    2. En el menú de la izquierda, selecciona **Daily Deriv Auto-Trading Bot**.
    3. Haz clic en el botón desplegable **Run workflow** (Ejecutar flujo de trabajo) y luego en el botón verde.
*   **Monitoreo y Resultados**:
    - Cada vez que el bot corra, podrás ver el registro exacto de las operaciones y análisis técnico en tiempo real en la consola de GitHub Actions.
    - Al terminar, se generará y guardará un archivo comprimido descargable (`trading-session-logs`) con el archivo `trading_log.txt` detallado y `trades_history.csv` para que analices tu historial en Excel.

---

## 🔒 Consejos de Seguridad Críticos

1. **Renueva tu API Token expuesto**: Tu API key `hWG6PhodZEHSEiO` ha sido enviada en el chat y podría quedar expuesta. Te recomendamos encarecidamente entrar a tu portal de [Deriv Token Management](https://app.deriv.com/account/api-token), eliminar ese token viejo y crear uno nuevo con permisos exclusivos de **Lectura (Read)** y **Operación (Trade)**.
2. **Entorno Demo Inicial**: Te recomendamos realizar las primeras ejecuciones del flujo de GitHub Actions vinculando el API Token de una **cuenta demo** para verificar el comportamiento del bot en el mercado antes de usar fondos reales.
