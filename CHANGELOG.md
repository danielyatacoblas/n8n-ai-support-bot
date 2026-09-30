# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y versionado [SemVer](https://semver.org/lang/es/).

## [1.2.1]

### Añadido
- GitHub Action `tags.yml`: crea el tag de cada release de Git Flow al llegar a `main`.

## [1.2.0]

### Añadido
- Sección «El workflow en n8n» en el README: captura del editor, diagrama de secuencia del mecanismo principal, técnicas de n8n usadas y tabla nodo por nodo.
- `scripts/documentar_workflow.py`: genera esas tablas desde el JSON del workflow.

### Cambiado
- El canvas se acomoda automáticamente a partir de las conexiones (`scripts/diseno_canvas.py`); ya no hay nodos encimados.

## [1.1.1]

### Añadido
- Diagrama gitGraph del historial en el README, generado por `scripts/diagrama_git.py` a partir de las ramas y tags reales.

## [1.1.0]

### Añadido
- Imagen de arquitectura en el README: problema, entradas, pasos dentro de n8n y salidas.
- Imagen de pruebas en el README: tests por archivo y verificaciones hechas en n8n real.

## [1.0.0]

### Añadido
- Motor de decisión: búsqueda en la base de conocimiento con sinónimos, derivación a un asesor y memoria por chat.
- Nodo Code de n8n generado desde `workflows/src/responder_mensaje.js` con la base inyectada.
- Workflow demo sin credenciales y workflow de producción con Telegram, IA y Google Sheets.
- Respaldo cuando la IA falla: se envía la respuesta de la base.
- Chat de demostración con modo simulado y modo conectado a n8n.
- Evaluación sobre 48 mensajes etiquetados (96 % de acierto) y umbral mínimo en la CI.
- Test de paridad entre el nodo JavaScript y la lógica Python.
