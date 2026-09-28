"""Umbral de calidad: si un cambio baja el acierto del bot, la CI lo frena."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from evaluar_bot import evaluar  # noqa: E402

MINIMO = 0.90


def test_acierto_minimo_sobre_conversaciones_etiquetadas():
    aciertos, total, errores = evaluar()
    assert aciertos / total >= MINIMO, (
        f"acierto {aciertos}/{total} por debajo del {MINIMO:.0%}. Fallos: {errores}")


def test_nunca_contesta_un_reclamo():
    """Un reclamo mal clasificado es el peor error posible: no se tolera ninguno."""
    _, _, errores = evaluar()
    assert not [e for e in errores if e["esperado"] in ("reclamo", "pide_persona")]
