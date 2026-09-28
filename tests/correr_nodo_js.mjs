// Ejecuta el código del nodo Code de n8n fuera de n8n, simulando sus globals.
// Uso:  node tests/correr_nodo_js.mjs <entrada.json>
// La entrada es una lista de payloads (formato webhook o Telegram).
// Salida: JSON por stdout con el resultado de cada mensaje.

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');

const faq = readFileSync(join(ROOT, 'data', 'faq.json'), 'utf8');
const jsCode = readFileSync(join(ROOT, 'workflows', 'src', 'responder_mensaje.js'), 'utf8')
  .replace('__FAQ__', faq);

const payloads = JSON.parse(readFileSync(process.argv[2], 'utf8'));

// Igual que en n8n: el nodo corre una vez con todos los items y el estado
// persiste en workflowStaticData.
const staticData = {};
const $getWorkflowStaticData = () => staticData;
const $input = { all: () => payloads.map((json) => ({ json })) };

const ejecutarNodo = new Function('$input', '$getWorkflowStaticData', jsCode);
const salida = ejecutarNodo($input, $getWorkflowStaticData);

process.stdout.write(JSON.stringify(salida.map((s) => s.json)));
