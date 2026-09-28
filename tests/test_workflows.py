"""Revisa los workflows generados: que se puedan importar y no filtren secretos."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = {p.name: json.loads(p.read_text(encoding="utf-8"))
             for p in (ROOT / "workflows").glob("*.json")}


def test_existen_los_dos_workflows():
    assert set(WORKFLOWS) == {"bot_demo.json", "bot_produccion.json"}


@pytest.mark.parametrize("nombre", sorted(WORKFLOWS))
def test_conexiones_apuntan_a_nodos_existentes(nombre):
    wf = WORKFLOWS[nombre]
    nodos = {n["name"] for n in wf["nodes"]}
    assert len(nodos) == len(wf["nodes"]), "hay nodos con nombre repetido"
    for origen, salidas in wf["connections"].items():
        assert origen in nodos, f"conexión desde un nodo inexistente: {origen}"
        for ramas in salidas.values():
            for rama in ramas:
                for destino in rama:
                    assert destino["node"] in nodos, f"{origen} → {destino['node']}"


@pytest.mark.parametrize("nombre", sorted(WORKFLOWS))
def test_todo_nodo_esta_conectado(nombre):
    wf = WORKFLOWS[nombre]
    tocados = set(wf["connections"])
    for salidas in wf["connections"].values():
        for ramas in salidas.values():
            for rama in ramas:
                tocados.update(d["node"] for d in rama)
    sueltos = {n["name"] for n in wf["nodes"]} - tocados
    assert not sueltos, f"nodos sin conectar: {sueltos}"


@pytest.mark.parametrize("nombre", sorted(WORKFLOWS))
def test_no_hay_credenciales_ni_tokens(nombre):
    texto = json.dumps(WORKFLOWS[nombre])
    assert "credentials" not in texto
    assert not re.search(r"\d{8,10}:[A-Za-z0-9_-]{35}", texto), "token de bot de Telegram"
    assert not re.search(r"sk-[A-Za-z0-9]{20,}", texto), "API key"


def test_demo_no_necesita_credenciales():
    tipos = {n["type"] for n in WORKFLOWS["bot_demo.json"]["nodes"]}
    assert tipos <= {"n8n-nodes-base.webhook", "n8n-nodes-base.code",
                     "n8n-nodes-base.respondToWebhook"}


def test_el_codigo_del_nodo_lleva_la_base_de_conocimiento():
    faq = json.loads((ROOT / "data" / "faq.json").read_text(encoding="utf-8"))
    for wf in WORKFLOWS.values():
        code = next(n for n in wf["nodes"] if n["type"] == "n8n-nodes-base.code")
        js = code["parameters"]["jsCode"]
        assert "__FAQ__" not in js
        assert all(f["id"] in js for f in faq["faq"])


def test_si_la_ia_falla_igual_se_responde():
    wf = WORKFLOWS["bot_produccion.json"]
    ia = next(n for n in wf["nodes"] if n["name"] == "IA · Redactar respuesta")
    assert ia.get("onError") == "continueErrorOutput"
    rama_error = wf["connections"]["IA · Redactar respuesta"]["main"][1]
    assert rama_error[0]["node"] == "Telegram · Enviar respuesta fija"
