// Nodo Code de n8n: "Decidir respuesta"
// Espejo en JavaScript de src/bot_faq.py (misma lógica, misma salida).
// La paridad entre ambos la verifica tests/test_paridad_js.py.
//
// La base de conocimiento NO se escribe aquí: scripts/build_workflow.py
// reemplaza el marcador de abajo por el contenido de data/faq.json al construir los
// workflows. Así el negocio edita un solo archivo y no toca código.

const FAQ_DOC = __FAQ__;

const UMBRAL = 3;
const PREFIJO = 5;
const MAX_CONTEXTO = 3;
const EXPIRA_DERIVACION = 24 * 60 * 60;

const STOPWORDS = new Set([
  'a', 'al', 'algo', 'alguna', 'alguno', 'con', 'de', 'del', 'el', 'en',
  'es', 'esta', 'estan', 'hay', 'la', 'las', 'le', 'les', 'lo', 'los', 'me',
  'mi', 'mis', 'o', 'para', 'por', 'puedo', 'pueden', 'que', 'quiero', 'se',
  'si', 'son', 'su', 'sus', 'tengo', 'tiene', 'tienen', 'un', 'una', 'uno',
  'y', 'ya', 'yo', 'hacen', 'hace', 'como', 'cual', 'sirve', 'necesito',
]);

const SINONIMOS = {
  cuanto: 'costo', cuesta: 'costo', cuestan: 'costo',
  precio: 'costo', precios: 'costo', vale: 'costo', valen: 'costo',
  cobran: 'costo',
  abren: 'horario', hora: 'horario', abiertos: 'horario',
  anteojos: 'lente', gafas: 'lente', lentes: 'lente',
  pupilentes: 'pupilente',
  arreglan: 'reparar', arreglar: 'reparar', arreglarla: 'reparar',
  arreglarlo: 'reparar', rompio: 'reparar', roto: 'reparar',
  rota: 'reparar',
  agendar: 'cita', reservar: 'cita', turno: 'cita',
  mandar: 'envio', envian: 'envio', casa: 'domicilio',
  demoran: 'entrega', demora: 'entrega', listos: 'entrega',
  entregan: 'entrega',
  ofertas: 'promocion', descuentos: 'promocion',
  hijo: 'nino', hija: 'nino', ninos: 'nino', ninas: 'nino',
  nina: 'nino', medirme: 'examen',
};

const DERIVAR = {
  pide_persona: ['asesor', 'humano', 'persona real', 'hablar con alguien',
    'hablar con una persona', 'operador'],
  reclamo: ['reclamo', 'queja', 'denuncia', 'estafa', 'devuelvan mi dinero',
    'pesimo', 'mala atencion'],
};

const SALUDOS = new Set(['hola', 'buenas', 'buenos', 'dias', 'tardes', 'noches',
  'hey', 'saludos', 'ola', 'que', 'tal']);
const DESPEDIDAS = new Set(['gracias', 'ok', 'listo', 'perfecto', 'genial',
  'muchas', 'chau', 'adios']);

const TEXTOS = {
  inicio: '¡Hola! Soy el asistente de {negocio}. Pregúntame por precios, ' +
    'horarios, citas, garantías o envíos. Si prefieres hablar con ' +
    'una persona, escribe «asesor».',
  saludo: '¡Hola{nombre}! ¿En qué te puedo ayudar? Puedo contarte sobre ' +
    'precios, horarios, citas, garantías o envíos.',
  despedida: '¡Con gusto! Si necesitas algo más, aquí estoy.',
  no_texto: 'Por ahora solo puedo leer mensajes de texto. ¿Me escribes ' +
    'tu consulta?',
  aclarar: 'No encontré una respuesta exacta. ¿Puedes contármelo con ' +
    'otras palabras? Por ejemplo: «cuánto cuestan los lentes» o ' +
    '«a qué hora abren».',
  derivar: 'Te comunico con un asesor de {negocio}. Te escribirá por ' +
    'este mismo chat en unos minutos.',
};

const AVISO_EQUIPO = 'Chat {chat_id} ({nombre}) necesita un asesor · motivo: {motivo} · último mensaje: «{texto}»';

const formatear = (plantilla, valores) =>
  plantilla.replace(/\{(\w+)\}/g, (_, k) => valores[k]);

// ── texto ──

function normalizar(texto) {
  return (texto || '').normalize('NFD').replace(/[̀-ͯ]/g, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, ' ').split(' ').filter(Boolean);
}

const raiz = (palabra) => palabra.slice(0, PREFIJO);

function terminos(texto) {
  const salida = [];
  for (const p of normalizar(texto)) {
    if (STOPWORDS.has(p)) continue;
    const r = raiz(SINONIMOS[p] || p);
    if (!salida.includes(r)) salida.push(r);
  }
  return salida;
}

// ── búsqueda en la base de conocimiento ──

function indexar(faq) {
  return faq.map((f) => {
    const clave = new Set();
    for (const k of f.palabras_clave) terminos(k).forEach((t) => clave.add(t));
    const ejemplos = new Set(terminos(f.pregunta));
    for (const e of f.ejemplos) terminos(e).forEach((t) => ejemplos.add(t));
    return { faq: f, clave, ejemplos };
  });
}

function puntuar(consulta, entrada) {
  let puntos = 0;
  for (const t of consulta) {
    if (entrada.clave.has(t)) puntos += 3;
    else if (entrada.ejemplos.has(t)) puntos += 1;
  }
  return puntos;
}

function buscar(texto, indice) {
  const consulta = terminos(texto);
  return indice
    .map((e, i) => ({ p: puntuar(consulta, e), i, f: e.faq }))
    .filter((x) => x.p > 0)
    .sort((a, b) => (b.p - a.p) || (a.i - b.i));
}

function motivoDerivacion(texto) {
  const frase = ' ' + normalizar(texto).join(' ') + ' ';
  for (const [motivo, patrones] of Object.entries(DERIVAR)) {
    if (patrones.some((p) => frase.includes(' ' + p + ' '))) return motivo;
  }
  return null;
}

// ── entrada desde n8n ──

function extraerMensaje(payload) {
  // El webhook de n8n envuelve el JSON recibido en "body"; el trigger de
  // Telegram no. Se aceptan los dos para poder reenviar updates por webhook.
  if (payload.body && typeof payload.body === 'object') payload = payload.body;
  const msg = payload.message;
  if (msg && typeof msg === 'object') {
    return {
      chat_id: String((msg.chat || {}).id ?? ''),
      nombre: String((msg.from || {}).first_name ?? ''),
      texto: String(msg.text ?? ''),
      fecha: Math.trunc(Number(msg.date) || 0),
    };
  }
  return {
    chat_id: String(payload.chat_id ?? ''),
    nombre: String(payload.nombre ?? ''),
    texto: String(payload.texto ?? ''),
    fecha: Math.trunc(Number(payload.fecha) || 0),
  };
}

// ── decisión ──

function procesarMensaje(mensaje, estado, faqDoc, indice) {
  estado.derivados = estado.derivados || {};
  estado.fallos = estado.fallos || {};
  indice = indice || indexar(faqDoc.faq);
  const negocio = faqDoc.negocio;

  const chat = mensaje.chat_id;
  const texto = (mensaje.texto || '').trim();
  const nombre = (mensaje.nombre || '').trim();
  const fecha = mensaje.fecha || Math.floor(Date.now() / 1000);

  const resultado = {
    accion: 'responder', chat_id: chat, texto,
    intencion: '', puntaje: 0, respuesta: '',
    contexto: [], aviso_equipo: '',
  };

  const responder = (intencion, respuesta, puntaje = 0, contexto = []) =>
    Object.assign(resultado, { intencion, respuesta, puntaje, contexto });

  const derivar = (motivo) => {
    estado.derivados[chat] = fecha;
    delete estado.fallos[chat];
    return Object.assign(resultado, {
      accion: 'derivar', intencion: motivo,
      respuesta: formatear(TEXTOS.derivar, { negocio }),
      aviso_equipo: formatear(AVISO_EQUIPO, {
        chat_id: chat, nombre: nombre || 'sin nombre', motivo, texto,
      }),
    });
  };

  // 1. Volver al bot siempre es posible
  if (['/start', 'menu', 'menú'].includes(texto.toLowerCase())) {
    delete estado.derivados[chat];
    delete estado.fallos[chat];
    return responder('inicio', formatear(TEXTOS.inicio, { negocio }));
  }

  // 2. Si un asesor tiene el chat, el bot no se mete
  if (chat in estado.derivados) {
    if (fecha - estado.derivados[chat] < EXPIRA_DERIVACION) {
      return Object.assign(resultado, { accion: 'silencio', intencion: 'en_manos_de_asesor' });
    }
    delete estado.derivados[chat];
  }

  if (!texto) return responder('no_texto', TEXTOS.no_texto);

  // 3. Pedidos de persona o reclamos: nunca los contesta una máquina
  const motivo = motivoDerivacion(texto);
  if (motivo) return derivar(motivo);

  const palabras = normalizar(texto);
  if (palabras.length && palabras.every((p) => SALUDOS.has(p))) {
    return responder('saludo', formatear(TEXTOS.saludo, {
      nombre: nombre ? ' ' + nombre.split(/\s+/)[0] : '',
    }));
  }
  if (palabras.length && palabras.every((p) => DESPEDIDAS.has(p))) {
    return responder('despedida', TEXTOS.despedida);
  }

  // 4. Buscar en la base de conocimiento
  const candidatos = buscar(texto, indice);
  const contexto = candidatos.slice(0, MAX_CONTEXTO).map((c) => ({
    id: c.f.id, pregunta: c.f.pregunta, respuesta: c.f.respuesta,
  }));

  if (candidatos.length && candidatos[0].p >= UMBRAL) {
    delete estado.fallos[chat];
    return responder(candidatos[0].f.id, candidatos[0].f.respuesta, candidatos[0].p, contexto);
  }

  // 5. No entendió: una vez pide aclarar, la segunda deriva
  estado.fallos[chat] = (estado.fallos[chat] || 0) + 1;
  if (estado.fallos[chat] >= 2) return derivar('sin_respuesta');
  return responder('aclarar', TEXTOS.aclarar,
    candidatos.length ? candidatos[0].p : 0, contexto);
}

// ── Ejecución en n8n ──
// (todo lo de arriba se reutiliza tal cual en chat_demo/motor.js)

const estado = $getWorkflowStaticData('global');
const indice = indexar(FAQ_DOC.faq);

return $input.all().map((item) => ({
  json: procesarMensaje(extraerMensaje(item.json), estado, FAQ_DOC, indice),
}));
