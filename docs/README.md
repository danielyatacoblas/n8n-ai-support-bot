# docs

Material de apoyo del repositorio.

- `chat_demo.png`: el chat de demostración conectado al workflow de n8n.

## Grabar el video de la demo

1. `docker compose up -d` e importa y activa `workflows/bot_demo.json` (ver README).
2. Abre `chat_demo/index.html` y elige **n8n real**.
3. Graba la pantalla con n8n a un lado (pestaña *Executions*) y el chat al otro.
4. Escribe en orden: `hola`, `¿cuánto cuestan los lentes?`, `quién ganó el
   partido`, `y el clima?` (deriva por no entender dos veces), `menu`,
   `quiero hablar con un asesor`.
5. Guarda el archivo como `docs/video.mp4`. Luego, al editar el README en
   GitHub, arrastra el video donde dice `VIDEO` para que se reproduzca en la página.
