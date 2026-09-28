"""Tests del motor del bot: una sección por cada decisión que toma."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.bot_faq import (EXPIRA_DERIVACION, extraer_mensaje,  # noqa: E402
                         motivo_derivacion, normalizar, procesar_mensaje,
                         terminos)

FAQ = json.loads((ROOT / "data" / "faq.json").read_text(encoding="utf-8"))
T0 = 1_760_000_000


def enviar(texto, estado, chat="1", fecha=T0, nombre="Ana"):
    return procesar_mensaje({"chat_id": chat, "texto": texto, "fecha": fecha,
                             "nombre": nombre}, estado, FAQ)


# ── texto ──────────────────────────────────────────────────────────────────

def test_normalizar_quita_tildes_signos_y_mayusculas():
    assert normalizar("¿Cuánto CUESTA el Envío?") == ["cuanto", "cuesta", "el", "envio"]


def test_tilde_combinante_se_trata_igual_que_la_precompuesta():
    """macOS envía 'á' como 'a' + tilde combinante; debe dar lo mismo."""
    assert normalizar("cuánto") == normalizar("cuánto") == ["cuanto"]


def test_terminos_aplica_sinonimos_y_raiz():
    assert terminos("cuánto cuestan los anteojos") == ["costo", "lente"]


def test_plural_y_singular_comparten_raiz():
    assert terminos("monturas") == terminos("montura")


# ── búsqueda ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("texto,esperado", [
    ("a qué hora abren", "horario"),
    ("aceptan yape", "pago"),
    ("tienen lunas para la computadora", "lunas_blue"),
    ("se me rompió la montura", "reparacion"),
    ("hacen delivery a provincia", "delivery"),
    ("venden pupilentes", "lentes_contacto"),
])
def test_responde_con_la_faq_correcta(texto, esperado):
    r = enviar(texto, {})
    assert r["accion"] == "responder"
    assert r["intencion"] == esperado
    assert r["puntaje"] >= 3


def test_respuesta_es_el_texto_de_la_base():
    r = enviar("aceptan yape", {})
    pago = next(f for f in FAQ["faq"] if f["id"] == "pago")
    assert r["respuesta"] == pago["respuesta"]


def test_contexto_para_la_ia_trae_como_maximo_tres_faqs():
    r = enviar("cuanto cuestan los lentes de contacto de color", {})
    assert 1 <= len(r["contexto"]) <= 3
    assert r["contexto"][0]["id"] == r["intencion"]


# ── saludos y casos simples ────────────────────────────────────────────────

def test_saludo_usa_el_primer_nombre():
    r = enviar("hola buenas tardes", {}, nombre="María José")
    assert r["intencion"] == "saludo"
    assert r["respuesta"].startswith("¡Hola María!")


def test_saludo_sin_nombre_no_deja_espacio_suelto():
    assert enviar("hola", {}, nombre="")["respuesta"].startswith("¡Hola!")


def test_mensaje_vacio_pide_texto():
    assert enviar("   ", {})["intencion"] == "no_texto"


def test_despedida():
    assert enviar("ok gracias", {})["intencion"] == "despedida"


# ── derivación a una persona ───────────────────────────────────────────────

@pytest.mark.parametrize("texto,motivo", [
    ("quiero hablar con un asesor", "pide_persona"),
    ("pásame con una persona real", "pide_persona"),
    ("quiero dejar un reclamo", "reclamo"),
    ("esto es una estafa", "reclamo"),
])
def test_detecta_motivo_de_derivacion(texto, motivo):
    assert motivo_derivacion(texto) == motivo


def test_asesoria_dentro_de_otra_palabra_no_deriva():
    """'asesoramiento' no es pedir un asesor: se compara por palabra completa."""
    assert motivo_derivacion("necesito asesoramiento de monturas") is None


def test_derivar_avisa_al_equipo_con_el_contexto():
    r = enviar("quiero hablar con un asesor", {}, chat="77", nombre="Luis")
    assert r["accion"] == "derivar"
    assert "77" in r["aviso_equipo"] and "Luis" in r["aviso_equipo"]
    assert "pide_persona" in r["aviso_equipo"]


def test_bot_calla_mientras_el_asesor_tiene_el_chat():
    estado = {}
    enviar("asesor", estado)
    r = enviar("aceptan yape?", estado, fecha=T0 + 60)
    assert r["accion"] == "silencio"
    assert r["respuesta"] == ""


def test_otros_chats_siguen_atendidos_por_el_bot():
    estado = {}
    enviar("asesor", estado, chat="1")
    assert enviar("aceptan yape?", estado, chat="2")["accion"] == "responder"


def test_la_derivacion_expira_a_las_24_horas():
    estado = {}
    enviar("asesor", estado)
    r = enviar("aceptan yape?", estado, fecha=T0 + EXPIRA_DERIVACION)
    assert r["accion"] == "responder"


def test_menu_devuelve_el_chat_al_bot():
    estado = {}
    enviar("asesor", estado)
    assert enviar("menu", estado, fecha=T0 + 60)["intencion"] == "inicio"
    assert enviar("aceptan yape?", estado, fecha=T0 + 120)["accion"] == "responder"


# ── cuando no entiende ─────────────────────────────────────────────────────

def test_primera_vez_que_no_entiende_pide_aclarar():
    r = enviar("quién ganó el partido", {})
    assert r["accion"] == "responder"
    assert r["intencion"] == "aclarar"


def test_segunda_vez_seguida_deriva():
    estado = {}
    enviar("quién ganó el partido", estado)
    r = enviar("y el clima?", estado)
    assert r["accion"] == "derivar"
    assert r["intencion"] == "sin_respuesta"


def test_un_acierto_reinicia_el_contador_de_fallos():
    estado = {}
    enviar("quién ganó el partido", estado)
    enviar("aceptan yape", estado)
    assert enviar("y el clima?", estado)["intencion"] == "aclarar"


# ── formatos de entrada ────────────────────────────────────────────────────

def test_extrae_mensaje_de_telegram():
    m = extraer_mensaje({"message": {"chat": {"id": 555}, "from": {"first_name": "Rosa"},
                                     "text": "hola", "date": T0}})
    assert m == {"chat_id": "555", "nombre": "Rosa", "texto": "hola", "fecha": T0}


def test_extrae_mensaje_del_webhook_de_la_demo():
    m = extraer_mensaje({"headers": {}, "body": {"chat_id": "9", "texto": "hola"}})
    assert m["chat_id"] == "9" and m["texto"] == "hola" and m["fecha"] == 0


def test_foto_sin_texto_de_telegram():
    m = extraer_mensaje({"message": {"chat": {"id": 1}, "photo": [{}], "date": T0}})
    assert enviar(m["texto"], {})["intencion"] == "no_texto"


def test_extrae_update_de_telegram_reenviado_por_webhook():
    """Un update de Telegram que llega por el nodo Webhook viene dentro de body."""
    m = extraer_mensaje({"headers": {}, "body": {"message": {
        "chat": {"id": 8}, "from": {"first_name": "Leo"}, "text": "hola", "date": T0}}})
    assert m == {"chat_id": "8", "nombre": "Leo", "texto": "hola", "fecha": T0}
