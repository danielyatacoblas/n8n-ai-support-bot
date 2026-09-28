"""Motor del bot de atención: decide si responder, derivar o callar.

Es la misma lógica que corre en el nodo Code de n8n
(workflows/src/responder_mensaje.js). Vive también en Python para poder
probarla sin levantar n8n; tests/test_paridad_js.py verifica que ambas copias
den exactamente el mismo resultado.

Toda la puntuación usa enteros a propósito: con decimales, Python y
JavaScript pueden redondear distinto y la paridad se rompería por un 0.0001.
"""
from __future__ import annotations

import re
import time
import unicodedata

UMBRAL = 3               # puntaje mínimo para responder con una FAQ
PREFIJO = 5              # largo de la raíz con la que se comparan palabras
MAX_CONTEXTO = 3         # FAQs que se pasan a la IA como contexto
EXPIRA_DERIVACION = 24 * 60 * 60   # segundos que el asesor mantiene el chat

STOPWORDS = {
    "a", "al", "algo", "alguna", "alguno", "con", "de", "del", "el", "en",
    "es", "esta", "estan", "hay", "la", "las", "le", "les", "lo", "los", "me",
    "mi", "mis", "o", "para", "por", "puedo", "pueden", "que", "quiero", "se",
    "si", "son", "su", "sus", "tengo", "tiene", "tienen", "un", "una", "uno",
    "y", "ya", "yo", "hacen", "hace", "como", "cual", "sirve", "necesito",
}

# Cada sinónimo se reemplaza por la palabra que usa la base de conocimiento.
SINONIMOS = {
    "cuanto": "costo", "cuesta": "costo", "cuestan": "costo",
    "precio": "costo", "precios": "costo", "vale": "costo", "valen": "costo",
    "cobran": "costo",
    "abren": "horario", "hora": "horario", "abiertos": "horario",
    "anteojos": "lente", "gafas": "lente", "lentes": "lente",
    "pupilentes": "pupilente",
    "arreglan": "reparar", "arreglar": "reparar", "arreglarla": "reparar",
    "arreglarlo": "reparar", "rompio": "reparar", "roto": "reparar",
    "rota": "reparar",
    "agendar": "cita", "reservar": "cita", "turno": "cita",
    "mandar": "envio", "envian": "envio", "casa": "domicilio",
    "demoran": "entrega", "demora": "entrega", "listos": "entrega",
    "entregan": "entrega",
    "ofertas": "promocion", "descuentos": "promocion",
    "hijo": "nino", "hija": "nino", "ninos": "nino", "ninas": "nino",
    "nina": "nino", "medirme": "examen",
}

DERIVAR = {
    "pide_persona": ["asesor", "humano", "persona real", "hablar con alguien",
                     "hablar con una persona", "operador"],
    "reclamo": ["reclamo", "queja", "denuncia", "estafa", "devuelvan mi dinero",
                "pesimo", "mala atencion"],
}

SALUDOS = {"hola", "buenas", "buenos", "dias", "tardes", "noches", "hey",
           "saludos", "ola", "que", "tal"}
DESPEDIDAS = {"gracias", "ok", "listo", "perfecto", "genial", "muchas",
              "chau", "adios"}

TEXTOS = {
    "inicio": ("¡Hola! Soy el asistente de {negocio}. Pregúntame por precios, "
               "horarios, citas, garantías o envíos. Si prefieres hablar con "
               "una persona, escribe «asesor»."),
    "saludo": ("¡Hola{nombre}! ¿En qué te puedo ayudar? Puedo contarte sobre "
               "precios, horarios, citas, garantías o envíos."),
    "despedida": "¡Con gusto! Si necesitas algo más, aquí estoy.",
    "no_texto": ("Por ahora solo puedo leer mensajes de texto. ¿Me escribes "
                 "tu consulta?"),
    "aclarar": ("No encontré una respuesta exacta. ¿Puedes contármelo con "
                "otras palabras? Por ejemplo: «cuánto cuestan los lentes» o "
                "«a qué hora abren»."),
    "derivar": ("Te comunico con un asesor de {negocio}. Te escribirá por "
                "este mismo chat en unos minutos."),
}

AVISO_EQUIPO = "Chat {chat_id} ({nombre}) necesita un asesor · motivo: {motivo} · último mensaje: «{texto}»"


# ── texto ──────────────────────────────────────────────────────────────────

def normalizar(texto: str) -> list[str]:
    """Minúsculas, sin tildes, solo letras y números, separado en palabras."""
    t = unicodedata.normalize("NFD", texto or "")
    t = re.sub("[̀-ͯ]", "", t).lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return t.split()


def raiz(palabra: str) -> str:
    """Compara por los primeros letras: 'lentes' y 'lente' cuentan igual."""
    return palabra[:PREFIJO]


def terminos(texto: str) -> list[str]:
    """Palabras útiles para buscar: sin relleno, con sinónimos y en raíz."""
    salida = []
    for p in normalizar(texto):
        if p in STOPWORDS:
            continue
        r = raiz(SINONIMOS.get(p, p))
        if r not in salida:
            salida.append(r)
    return salida


# ── búsqueda en la base de conocimiento ───────────────────────────────────

def indexar(faq: list[dict]) -> list[dict]:
    """Precalcula las raíces de cada FAQ una sola vez."""
    indice = []
    for f in faq:
        clave = set()
        for k in f["palabras_clave"]:
            clave.update(terminos(k))
        ejemplos = set(terminos(f["pregunta"]))
        for e in f["ejemplos"]:
            ejemplos.update(terminos(e))
        indice.append({"faq": f, "clave": clave, "ejemplos": ejemplos})
    return indice


def puntuar(consulta: list[str], entrada: dict) -> int:
    """3 puntos por palabra clave, 1 por palabra que aparece en los ejemplos."""
    puntos = 0
    for t in consulta:
        if t in entrada["clave"]:
            puntos += 3
        elif t in entrada["ejemplos"]:
            puntos += 1
    return puntos


def buscar(texto: str, indice: list[dict]) -> list[tuple[int, dict]]:
    """FAQs con puntaje > 0, de mejor a peor. En empate gana la primera."""
    consulta = terminos(texto)
    puntajes = [(puntuar(consulta, e), i, e["faq"]) for i, e in enumerate(indice)]
    puntajes = [p for p in puntajes if p[0] > 0]
    puntajes.sort(key=lambda p: (-p[0], p[1]))
    return [(p, f) for p, _, f in puntajes]


def motivo_derivacion(texto: str) -> str | None:
    frase = " " + " ".join(normalizar(texto)) + " "
    for motivo, patrones in DERIVAR.items():
        if any(" " + p + " " in frase for p in patrones):
            return motivo
    return None


# ── entrada desde n8n ─────────────────────────────────────────────────────

def extraer_mensaje(payload: dict) -> dict:
    """Acepta el formato de Telegram o el del webhook de la demo."""
    # El webhook de n8n envuelve el JSON recibido en "body"; el trigger de
    # Telegram no. Se aceptan los dos para poder reenviar updates por webhook.
    if isinstance(payload.get("body"), dict):
        payload = payload["body"]
    msg = payload.get("message")
    if isinstance(msg, dict):
        return {
            "chat_id": str(msg.get("chat", {}).get("id", "")),
            "nombre": str(msg.get("from", {}).get("first_name", "")),
            "texto": str(msg.get("text", "")),
            "fecha": int(msg.get("date") or 0),
        }
    return {
        "chat_id": str(payload.get("chat_id", "")),
        "nombre": str(payload.get("nombre", "")),
        "texto": str(payload.get("texto", "")),
        "fecha": int(payload.get("fecha") or 0),
    }


# ── decisión ──────────────────────────────────────────────────────────────

def procesar_mensaje(mensaje: dict, estado: dict, faq_doc: dict,
                     indice: list[dict] | None = None) -> dict:
    """Decide qué hacer con un mensaje y actualiza el estado de la conversación.

    estado = {"derivados": {chat_id: fecha}, "fallos": {chat_id: n}}
    """
    estado.setdefault("derivados", {})
    estado.setdefault("fallos", {})
    indice = indice if indice is not None else indexar(faq_doc["faq"])
    negocio = faq_doc["negocio"]

    chat = mensaje["chat_id"]
    texto = (mensaje.get("texto") or "").strip()
    nombre = (mensaje.get("nombre") or "").strip()
    fecha = mensaje.get("fecha") or int(time.time())

    resultado = {"accion": "responder", "chat_id": chat, "texto": texto,
                 "intencion": "", "puntaje": 0, "respuesta": "",
                 "contexto": [], "aviso_equipo": ""}

    def responder(intencion, respuesta, puntaje=0, contexto=None):
        resultado.update(intencion=intencion, respuesta=respuesta,
                         puntaje=puntaje, contexto=contexto or [])
        return resultado

    def derivar(motivo):
        estado["derivados"][chat] = fecha
        estado["fallos"].pop(chat, None)
        resultado.update(
            accion="derivar", intencion=motivo,
            respuesta=TEXTOS["derivar"].format(negocio=negocio),
            aviso_equipo=AVISO_EQUIPO.format(
                chat_id=chat, nombre=nombre or "sin nombre",
                motivo=motivo, texto=texto))
        return resultado

    # 1. Volver al bot siempre es posible
    if texto.lower() in ("/start", "menu", "menú"):
        estado["derivados"].pop(chat, None)
        estado["fallos"].pop(chat, None)
        return responder("inicio", TEXTOS["inicio"].format(negocio=negocio))

    # 2. Si un asesor tiene el chat, el bot no se mete
    if chat in estado["derivados"]:
        if fecha - estado["derivados"][chat] < EXPIRA_DERIVACION:
            resultado.update(accion="silencio", intencion="en_manos_de_asesor")
            return resultado
        estado["derivados"].pop(chat)

    if not texto:
        return responder("no_texto", TEXTOS["no_texto"])

    # 3. Pedidos de persona o reclamos: nunca los contesta una máquina
    motivo = motivo_derivacion(texto)
    if motivo:
        return derivar(motivo)

    palabras = normalizar(texto)
    if palabras and all(p in SALUDOS for p in palabras):
        return responder("saludo", TEXTOS["saludo"].format(
            nombre=(" " + nombre.split()[0]) if nombre else ""))
    if palabras and all(p in DESPEDIDAS for p in palabras):
        return responder("despedida", TEXTOS["despedida"])

    # 4. Buscar en la base de conocimiento
    candidatos = buscar(texto, indice)
    contexto = [{"id": f["id"], "pregunta": f["pregunta"],
                 "respuesta": f["respuesta"]}
                for _, f in candidatos[:MAX_CONTEXTO]]

    if candidatos and candidatos[0][0] >= UMBRAL:
        puntaje, mejor = candidatos[0]
        estado["fallos"].pop(chat, None)
        return responder(mejor["id"], mejor["respuesta"], puntaje, contexto)

    # 5. No entendió: una vez pide aclarar, la segunda deriva
    estado["fallos"][chat] = estado["fallos"].get(chat, 0) + 1
    if estado["fallos"][chat] >= 2:
        return derivar("sin_respuesta")
    return responder("aclarar", TEXTOS["aclarar"],
                     candidatos[0][0] if candidatos else 0, contexto)
