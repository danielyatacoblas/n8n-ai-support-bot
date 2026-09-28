"""Paridad: el nodo Code de n8n (JS) y el motor Python deben decidir igual.

Si alguien cambia responder_mensaje.js sin cambiar bot_faq.py (o al revés),
este test falla y dice en qué mensaje divergen. Requiere Node.js; si no está
instalado, se salta.
"""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.bot_faq import extraer_mensaje, indexar, procesar_mensaje  # noqa: E402

FAQ = json.loads((ROOT / "data" / "faq.json").read_text(encoding="utf-8"))
RUNNER = ROOT / "tests" / "correr_nodo_js.mjs"

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="Node.js no está instalado")


def _payloads() -> list[dict]:
    """Las conversaciones de prueba, la mitad como webhook y la mitad como Telegram."""
    salida = []
    filas = csv.DictReader((ROOT / "data" / "conversaciones_prueba.csv").open(encoding="utf-8"))
    for i, f in enumerate(filas):
        if i % 2:
            salida.append({"message": {"chat": {"id": int(f["chat_id"])},
                                       "from": {"first_name": f["nombre"]},
                                       "text": f["texto"], "date": int(f["fecha"])}})
        else:
            salida.append({"body": {"chat_id": f["chat_id"], "nombre": f["nombre"],
                                    "texto": f["texto"], "fecha": f["fecha"]}})
    return salida


def _correr_js(payloads: list[dict], tmp_path: Path) -> list[dict]:
    entrada = tmp_path / "entrada.json"
    entrada.write_text(json.dumps(payloads, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(["node", str(RUNNER), str(entrada)],
                          capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        pytest.fail(f"el nodo JS falló:\n{proc.stderr}")
    return json.loads(proc.stdout)


def _correr_python(payloads: list[dict]) -> list[dict]:
    estado: dict = {}
    indice = indexar(FAQ["faq"])
    return [procesar_mensaje(extraer_mensaje(p), estado, FAQ, indice) for p in payloads]


def test_js_y_python_deciden_igual_en_todas_las_conversaciones(tmp_path):
    payloads = _payloads()
    py = _correr_python(payloads)
    js = _correr_js(payloads, tmp_path)
    assert len(py) == len(js)
    for i, (p, j) in enumerate(zip(py, js)):
        assert p == j, f"divergen en el mensaje {i}: «{payloads[i]}»\n python={p}\n js    ={j}"


def test_paridad_con_textos_raros(tmp_path):
    """Tildes combinantes, emojis, signos y mayúsculas no deben separar las copias."""
    textos = ["CUÁNTO CUESTAN LOS LENTES???", "cuánto demoran",
              "hola 👋", "   ", "¿¿envíos a provincia??", "{negocio} asesor",
              "Ñandú quiere lentes de sol", "123 456"]
    payloads = [{"body": {"chat_id": str(900 + i), "texto": t, "fecha": 1760000000}}
                for i, t in enumerate(textos)]
    assert _correr_python(payloads) == _correr_js(payloads, tmp_path)
