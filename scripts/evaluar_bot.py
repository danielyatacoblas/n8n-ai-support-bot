#!/usr/bin/env python3
"""Mide qué tan bien acierta el bot con conversaciones etiquetadas a mano.

    python scripts/evaluar_bot.py

Cada fila de data/conversaciones_prueba.csv trae el mensaje de un cliente y
la intención correcta ("esperado"). Los mensajes se procesan en orden y con
estado compartido, igual que en n8n: así también se prueba que el bot calle
cuando un asesor tiene el chat o que derive al segundo mensaje que no entiende.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.bot_faq import indexar, procesar_mensaje  # noqa: E402

FAQ = ROOT / "data" / "faq.json"
CONVERSACIONES = ROOT / "data" / "conversaciones_prueba.csv"


def evaluar() -> tuple[int, int, list[dict]]:
    faq_doc = json.loads(FAQ.read_text(encoding="utf-8"))
    indice = indexar(faq_doc["faq"])
    estado: dict = {}
    errores = []
    filas = list(csv.DictReader(CONVERSACIONES.open(encoding="utf-8")))
    for fila in filas:
        mensaje = {"chat_id": fila["chat_id"], "nombre": fila["nombre"],
                   "texto": fila["texto"], "fecha": int(fila["fecha"])}
        r = procesar_mensaje(mensaje, estado, faq_doc, indice)
        if r["intencion"] != fila["esperado"]:
            errores.append({"texto": fila["texto"], "esperado": fila["esperado"],
                            "obtenido": r["intencion"], "puntaje": r["puntaje"]})
    return len(filas) - len(errores), len(filas), errores


def main():
    aciertos, total, errores = evaluar()
    print(f"Mensajes evaluados: {total}")
    print(f"Aciertos:           {aciertos}  ({aciertos / total:.0%})")
    if errores:
        print("\nFallos:")
        for e in errores:
            print(f"  «{e['texto']}»\n    esperado={e['esperado']}  "
                  f"obtenido={e['obtenido']}  puntaje={e['puntaje']}")


if __name__ == "__main__":
    main()
