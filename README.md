# 🤖 Bot de Trading Ultra-Seguro para Deriv (Automatizado en la Nube con Scalping y WhatsApp)

Este sistema de trading algorítmico automatizado está diseñado para ejecutarse diariamente en la nube utilizando **GitHub Actions**. Opera aplicando una estrategia de **Scalping Seguro** de alta frecuencia sobre el índice **Volatility 10 (R_10)** e incluye notificaciones en tiempo real directamente a tu **WhatsApp**.

---

## ⚙️ Características del Bot

1. **Operación Asíncrona Directa**: Conectado directamente a las APIs WebSocket de Deriv utilizando la biblioteca `websockets` en Python. Sin intermediarios pesados.
2. **Estrategia de Scalping Seguro (EMA + RSI)**:
   - **Tendencia con EMA(10)**: Define la dirección predominante (alcista o bajista).
   - **Gatillo con RSI(7)**: Calcula retrocesos rápidos para comprar rebotes seguros a favor de la tendencia.
   - **CALL (Subida)**: Compra si la tendencia es alcista (Precio > EMA) Y ocurre un retroceso temporal (RSI <= 35).
   - **PUT (Caída)**: Compra si la tendencia es bajista (Precio < EMA) Y ocurre un rebote temporal (RSI >= 65).
   - **Frecuencia óptima**: A diferencia de la versión anterior, esta estrategia realiza múltiples operaciones por hora, permitiendo ganancias seguras poco a poco.
3. **Gestión de Riesgo Estricta (Ultra-Seguro)**:
   - **Monto por Operación**: $1.00 USD fijo (configurable en `config.py`).
   - **Objetivo diario (Take Profit)**: Detiene inmediatamente la ejecución cuando alcanza **$50.00 USD de ganancia**.
   - **Límite de pérdida diaria (Stop Loss)**: Detiene el bot si se acumulan pérdidas por valor de **$20.00 USD** para proteger tu capital.
   - **Límite de pérdidas consecutivas**: Freno automático de emergencia si ocurren **5 pérdidas seguidas**.
   - **Período de Enfriamiento (Cooldown)**: Espera **30 segundos** antes de reintentar tras una pérdida para evitar sobreoperar en mercados desfavorables.
4. **Ejecución Diaria en la Nube**: Configurado para ejecutarse de forma gratuita y automática usando **GitHub Actions (Cron)** todos los días.
5. **Notificaciones de WhatsApp**: Te avisa a tu celular al iniciar la jornada, al finalizarla con un reporte completo de ganancias/operaciones, o ante cualquier alerta de error.

---

## 📁 Archivos del Proyecto

*   `config.py`: Parámetros de la estrategia, credenciales de API, y reglas de gestión de capital.
*   `bot.py`: Código fuente principal del bot con la lógica asíncrona de trading, algoritmos e indicadores.
*   `requirements.txt`: Dependencias de librerías de Python.
*   `.github/workflows/daily_trading.yml`: Automatización diaria en GitHub.

---

## 📱 Cómo Activar las Notificaciones de WhatsApp (CallMeBot)

El bot utiliza el servicio gratuito **CallMeBot** para enviarte mensajes directamente a tu celular. Configurarlo toma menos de 2 minutos:

1. **Obtén tu API Key Gratuita**:
   - Guarda el número de teléfono de CallMeBot en tus contactos: **`+34 644 20 74 97`** (es el bot oficial de WhatsApp).
   - Envíale un mensaje de WhatsApp que diga exactamente: **`I allow callmebot to send me messages`**
   - El bot te responderá al instante con tu API Key y un enlace de prueba.
2. **Configura las Variables en GitHub Secrets**:
   Para mantener tu número y API Key seguros sin exponerlos en el código:
   - En tu repositorio de GitHub, ve a **Settings** -> **Secrets and variables** -> **Actions** -> **New repository secret**.
   - Crea un secreto con el nombre: **`WHATSAPP_PHONE`** y pon tu número con el código de país (ej: `+584120000000`).
   - Crea un segundo secreto con el nombre: **`WHATSAPP_API_KEY`** y pon la API Key que te dio el bot.
3. El sistema de GitHub Actions detectará estos secretos de forma automática al ejecutarse a las 7:30 PM (Hora Venezuela) y activará las notificaciones en vivo.

---

## 🚀 Guía de Instalación y Despliegue en la Nube

Para ejecutar este bot en la nube de forma **100% gratuita** y diaria, sigue estos pasos estructurados:

### Paso 1: Subir archivos a GitHub
1. Si ya realizaste la subida original, tus archivos se actualizarán en automático con cada actualización que yo haga.

### Paso 2: Configurar tus Secrets en GitHub
Para evitar exponer tus credenciales y números en el código público, ve a **Settings** -> **Secrets and variables** -> **Actions** en tu repositorio y crea los siguientes secretos:
*   `DERIV_API_TOKEN`: Tu API key de Deriv actualizada.
*   `WHATSAPP_PHONE`: Tu número con prefijo de país (Ej: `+584120000000`).
*   `WHATSAPP_API_KEY`: La API key que te dio CallMeBot.

### Paso 3: Activación y Monitoreo del Bot
*   **Ejecución Automática**: GitHub Actions ejecutará el bot de forma automática **todos los días a las 19:30 hora Venezuela (23:30 UTC)**. Operará durante unos minutos haciendo scalping seguro y te enviará el reporte diario completo de resultados a tu WhatsApp aproximadamente a las **20:00 (8:00 PM hora Venezuela)**.
*   **Ejecución Manual (Para probarlo hoy mismo)**:
    1. En tu repositorio de GitHub, haz clic en la pestaña **Actions** (Acciones).
    2. En el menú de la izquierda, selecciona **Daily Deriv Auto-Trading Bot**.
    3. Haz clic en el botón desplegable **Run workflow** (Ejecutar flujo de trabajo) y luego en el botón verde.

---

## 🔒 Consejos de Seguridad Críticos

1. **Renueva tu API Token expuesto**: Tu API key `hWG6PhodZEHSEiO` ha sido enviada en el chat y podría quedar expuesta. Te recomendamos encarecidamente entrar a tu portal de [Deriv Token Management](https://app.deriv.com/account/api-token), eliminar ese token viejo y crear uno nuevo con permisos exclusivos de **Lectura (Read)** y **Operación (Trade)**.
2. **Entorno Demo Inicial**: Te recomendamos realizar las primeras ejecuciones del flujo de GitHub Actions vinculando el API Token de una **cuenta demo** para verificar el comportamiento del bot en el mercado antes de usar fondos reales.
