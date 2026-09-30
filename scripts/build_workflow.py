#!/usr/bin/env python3
"""Construye los workflows de n8n y el motor del chat de demostración.

    python scripts/build_workflow.py

Genera:
  workflows/bot_demo.json        importable y ejecutable SIN credenciales
  workflows/bot_produccion.json  Telegram + IA + Google Sheets
  chat_demo/motor.js             la misma lógica, para el chat en modo simulado

El código del nodo vive en workflows/src/responder_mensaje.js y la base de
conocimiento en data/faq.json. Nada se edita a mano dentro de los JSON: la
integración continua falla si alguien lo hace.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from diseno_canvas import acomodar  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FAQ = ROOT / "data" / "faq.json"
JS = ROOT / "workflows" / "src" / "responder_mensaje.js"
OUT = ROOT / "workflows"
MOTOR = ROOT / "chat_demo" / "motor.js"

MARCA_EJECUCION = "// ── Ejecución en n8n ──"

PROMPT_SISTEMA = (
    "Eres el asistente de atención de {negocio}. Respondes por Telegram, en "
    "español, con un tono cercano y en un máximo de tres oraciones.\n"
    "Reglas:\n"
    "1. Usa SOLO la información del CONTEXTO. No inventes precios, horarios "
    "ni promociones.\n"
    "2. Si el contexto no alcanza para responder, dilo y ofrece que un asesor "
    "le confirme.\n"
    "3. No pidas datos sensibles (tarjetas, contraseñas, DNI).")

PROMPT_USUARIO = (
    "=CONTEXTO:\n"
    "{{ $json.contexto.map(c => '- ' + c.pregunta + ' ' + c.respuesta).join('\\n') }}\n\n"
    "PREGUNTA DEL CLIENTE: {{ $json.texto }}")


def codigo_nodo() -> str:
    faq = json.loads(FAQ.read_text(encoding="utf-8"))
    js = JS.read_text(encoding="utf-8")
    if "__FAQ__" not in js:
        raise SystemExit("falta el marcador __FAQ__ en " + str(JS))
    return js.replace("__FAQ__", json.dumps(faq, ensure_ascii=False, indent=2))


def motor_navegador(js: str) -> str:
    """Todo menos la parte que usa globals de n8n, expuesto en window."""
    if MARCA_EJECUCION not in js:
        raise SystemExit("falta la marca de ejecución en " + str(JS))
    logica = js.split(MARCA_EJECUCION)[0]
    return ("// Generado por scripts/build_workflow.py. No editar a mano.\n"
            "// Misma lógica que el nodo Code de n8n, para el modo simulado.\n"
            + logica +
            "window.MotorBot = { FAQ_DOC, indexar, procesarMensaje };\n")


def _node(nid, name, ntype, tv, pos, params, extra=None):
    n = {"parameters": params, "id": nid, "name": name, "type": ntype,
         "typeVersion": tv, "position": pos}
    if extra:
        n.update(extra)
    return n


def _link(*destinos, tipo="main"):
    return [{"node": d, "type": tipo, "index": 0} for d in destinos]


def _regla_texto(campo: str, valor: str, cid: str, salida: str) -> dict:
    return {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "",
                        "typeValidation": "strict", "version": 2},
            "conditions": [{"id": cid, "leftValue": campo, "rightValue": valor,
                            "operator": {"type": "string", "operation": "equals"}}],
            "combinator": "and"},
        "renameOutput": True, "outputKey": salida}


@acomodar
def build_demo(js: str) -> dict:
    """Webhook → Decidir respuesta → Responder. Sin ninguna credencial."""
    nodes = [
        _node("wh-1", "Webhook · Mensaje", "n8n-nodes-base.webhook", 2,
              [0, 0],
              {"httpMethod": "POST", "path": "bot-demo",
               "responseMode": "responseNode",
               # el chat de demostración se abre desde el disco (file://)
               "options": {"allowedOrigins": "*"}},
              {"webhookId": "bot-atencion-demo"}),
        _node("code-1", "Decidir respuesta", "n8n-nodes-base.code", 2,
              [240, 0], {"jsCode": js}),
        _node("resp-1", "Responder al chat", "n8n-nodes-base.respondToWebhook", 1.1,
              [480, 0], {"respondWith": "firstIncomingItem", "options": {}}),
    ]
    connections = {
        "Webhook · Mensaje": {"main": [_link("Decidir respuesta")]},
        "Decidir respuesta": {"main": [_link("Responder al chat")]},
    }
    return {
        "id": "botatenciondemo",
        "name": "Bot de atención · DEMO sin credenciales",
        "nodes": nodes, "connections": connections,
        "settings": {"executionOrder": "v1"}, "pinData": {},
        "meta": {"instanceId": "bot-atencion-demo"},
        "tags": [],
    }


@acomodar
def build_prod(js: str, negocio: str) -> dict:
    """Telegram → decidir → (IA | texto fijo | derivar a un asesor) + log."""
    chat_cliente = "={{ $('Decidir respuesta').item.json.chat_id }}"
    nodes = [
        _node("tg-in", "Telegram · Mensaje entrante", "n8n-nodes-base.telegramTrigger", 1.2,
              [0, 300], {"updates": ["message"], "additionalFields": {}},
              {"webhookId": "bot-atencion-telegram"}),
        _node("code-1", "Decidir respuesta", "n8n-nodes-base.code", 2,
              [240, 300], {"jsCode": js}),
        _node("sw-1", "¿Qué hacer?", "n8n-nodes-base.switch", 3.2,
              [480, 300],
              {"rules": {"values": [
                  _regla_texto("={{ $json.accion }}", "responder", "r1", "responder"),
                  _regla_texto("={{ $json.accion }}", "derivar", "r2", "derivar"),
              ]},
               "options": {"fallbackOutput": "extra",
                           "renameFallbackOutput": "silencio"}}),
        _node("if-1", "¿Respuesta de la base?", "n8n-nodes-base.if", 2.2,
              [720, 100],
              {"conditions": {
                  "options": {"caseSensitive": True, "leftValue": "",
                              "typeValidation": "strict", "version": 2},
                  "conditions": [{"id": "c1", "leftValue": "={{ $json.puntaje }}",
                                  "rightValue": 3,
                                  "operator": {"type": "number", "operation": "gte"}}],
                  "combinator": "and"},
               "options": {}},
              {"notes": "Saludos, aclaraciones y avisos se envían tal cual; "
                        "las respuestas de la base pasan por la IA para sonar naturales."}),
        _node("llm-1", "IA · Redactar respuesta", "@n8n/n8n-nodes-langchain.chainLlm", 1.7,
              [960, 0],
              {"promptType": "define", "text": PROMPT_USUARIO,
               "messages": {"messageValues": [
                   {"message": PROMPT_SISTEMA.format(negocio=negocio)}]}},
              {"onError": "continueErrorOutput",
               "notes": "Si la IA falla, la rama de error envía la respuesta "
                        "de la base sin reescribir: el cliente nunca se queda sin respuesta."}),
        _node("llm-m", "Modelo de IA", "@n8n/n8n-nodes-langchain.lmChatOpenAi", 1.2,
              [960, 200],
              {"model": {"__rl": True, "value": "gpt-4o-mini", "mode": "list"},
               "options": {"temperature": 0.2, "maxTokens": 300}},
              {"notes": "Intercambiable por cualquier otro modelo de chat de n8n "
                        "(Anthropic, Gemini, Ollama) sin tocar el resto del flujo."}),
        _node("tg-ia", "Telegram · Enviar respuesta IA", "n8n-nodes-base.telegram", 1.2,
              [1200, 0],
              {"chatId": chat_cliente, "text": "={{ $json.text }}",
               "additionalFields": {"appendAttribution": False}}),
        _node("tg-fija", "Telegram · Enviar respuesta fija", "n8n-nodes-base.telegram", 1.2,
              [1200, 200],
              {"chatId": chat_cliente,
               "text": "={{ $('Decidir respuesta').item.json.respuesta }}",
               "additionalFields": {"appendAttribution": False}}),
        _node("tg-cli", "Telegram · Avisar al cliente", "n8n-nodes-base.telegram", 1.2,
              [720, 400],
              {"chatId": chat_cliente, "text": "={{ $json.respuesta }}",
               "additionalFields": {"appendAttribution": False}}),
        _node("tg-eq", "Telegram · Avisar al equipo", "n8n-nodes-base.telegram", 1.2,
              [720, 560],
              {"chatId": "REEMPLAZAR_CHAT_EQUIPO", "text": "={{ $json.aviso_equipo }}",
               "additionalFields": {"appendAttribution": False}},
              {"notes": "ID del grupo de Telegram donde están los asesores."}),
        _node("noop-1", "Asesor a cargo · no responder", "n8n-nodes-base.noOp", 1,
              [720, 720], {}),
        _node("set-log", "Fila de registro", "n8n-nodes-base.set", 3.4,
              [480, 700],
              {"assignments": {"assignments": [
                  {"id": "l1", "name": "fecha", "type": "string",
                   "value": "={{ $now.toISO() }}"},
                  {"id": "l2", "name": "chat_id", "type": "string", "value": "={{ $json.chat_id }}"},
                  {"id": "l3", "name": "mensaje", "type": "string", "value": "={{ $json.texto }}"},
                  {"id": "l4", "name": "accion", "type": "string", "value": "={{ $json.accion }}"},
                  {"id": "l5", "name": "intencion", "type": "string", "value": "={{ $json.intencion }}"},
                  {"id": "l6", "name": "puntaje", "type": "number", "value": "={{ $json.puntaje }}"},
              ]}, "options": {}}),
        _node("gs-log", "Sheets · Registrar conversación", "n8n-nodes-base.googleSheets", 4.5,
              [720, 880],
              {"operation": "append",
               "documentId": {"__rl": True, "value": "REEMPLAZAR_ID_HOJA", "mode": "id"},
               "sheetName": {"__rl": True, "value": "Conversaciones", "mode": "name"},
               "columns": {"mappingMode": "autoMapInputData", "value": {}},
               "options": {}},
              {"notes": "Columnas: fecha, chat_id, mensaje, accion, intencion, puntaje"}),
    ]
    connections = {
        "Telegram · Mensaje entrante": {"main": [_link("Decidir respuesta")]},
        "Decidir respuesta": {"main": [_link("¿Qué hacer?", "Fila de registro")]},
        "¿Qué hacer?": {"main": [
            _link("¿Respuesta de la base?"),
            _link("Telegram · Avisar al cliente", "Telegram · Avisar al equipo"),
            _link("Asesor a cargo · no responder"),
        ]},
        "¿Respuesta de la base?": {"main": [
            _link("IA · Redactar respuesta"),
            _link("Telegram · Enviar respuesta fija"),
        ]},
        "IA · Redactar respuesta": {"main": [
            _link("Telegram · Enviar respuesta IA"),
            _link("Telegram · Enviar respuesta fija"),
        ]},
        "Modelo de IA": {"ai_languageModel": [
            _link("IA · Redactar respuesta", tipo="ai_languageModel")]},
        "Fila de registro": {"main": [_link("Sheets · Registrar conversación")]},
    }
    return {
        "id": "botatencionprod",
        "name": "Bot de atención · producción (Telegram + IA)",
        "nodes": nodes, "connections": connections,
        "settings": {"executionOrder": "v1"}, "pinData": {},
        "meta": {"instanceId": "bot-atencion-prod"},
        "tags": [],
    }


def main():
    js = codigo_nodo()
    negocio = json.loads(FAQ.read_text(encoding="utf-8"))["negocio"]
    salidas = {
        OUT / "bot_demo.json": json.dumps(build_demo(js), indent=2, ensure_ascii=False) + "\n",
        OUT / "bot_produccion.json": json.dumps(build_prod(js, negocio), indent=2, ensure_ascii=False) + "\n",
        MOTOR: motor_navegador(js),
    }
    for ruta, contenido in salidas.items():
        # newline="\n": en Windows saldría CRLF y el archivo parecería
        # modificado en cada build aunque no cambie nada.
        ruta.write_text(contenido, encoding="utf-8", newline="\n")
        print(f"ok  {ruta.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
