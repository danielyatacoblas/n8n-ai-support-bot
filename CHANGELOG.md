# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y versionado [SemVer](https://semver.org/lang/es/).

## [1.0.0]

### Añadido
- Motor de decisión: búsqueda en la base de conocimiento con sinónimos, derivación a un asesor y memoria por chat.
- Nodo Code de n8n generado desde `workflows/src/responder_mensaje.js` con la base inyectada.
- Workflow demo sin credenciales y workflow de producción con Telegram, IA y Google Sheets.
- Respaldo cuando la IA falla: se envía la respuesta de la base.
- Chat de demostración con modo simulado y modo conectado a n8n.
- Evaluación sobre 48 mensajes etiquetados (96 % de acierto) y umbral mínimo en la CI.
- Test de paridad entre el nodo JavaScript y la lógica Python.
