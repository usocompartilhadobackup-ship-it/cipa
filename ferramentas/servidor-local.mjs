// Simula a Vercel localmente: serve public/ e as funções api/quiz.js e api/admin.js.
// Uso: DATABASE_URL=... [DATABASE_SSL=off] node ferramentas/servidor-local.mjs [porta]
import http from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PORTA = Number(process.argv[2] || process.env.PORT || 8787);

if (!process.env.DATABASE_URL && !process.env.POSTGRES_URL) {
  console.error("Defina DATABASE_URL (banco local de teste ou Supabase pelo Transaction pooler).");
  process.exit(1);
}

const quiz = (await import(path.join(RAIZ, "api/quiz.js"))).default;
const admin = (await import(path.join(RAIZ, "api/admin.js"))).default;

const TIPOS = { ".html": "text/html; charset=utf-8", ".png": "image/png", ".txt": "text/plain", ".css": "text/css", ".js": "text/javascript" };

async function enviar(res, resposta) {
  res.writeHead(resposta.status, Object.fromEntries(resposta.headers));
  res.end(Buffer.from(await resposta.arrayBuffer()));
}

http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORTA}`);
  const partes = [];
  for await (const c of req) partes.push(c);
  const request = new Request(url, {
    method: req.method,
    headers: req.headers,
    body: ["GET", "HEAD"].includes(req.method) ? undefined : Buffer.concat(partes),
  });
  try {
    if (url.pathname === "/api/quiz") return enviar(res, await quiz.fetch(request));
    if (url.pathname === "/api/admin") return enviar(res, await admin.fetch(request));
    const arq = url.pathname === "/" ? "/index.html" : url.pathname === "/painel" ? "/painel.html" : url.pathname;
    const caminho = path.join(RAIZ, "public", path.normalize(arq));
    if (!caminho.startsWith(path.join(RAIZ, "public"))) throw new Error("fora de public");
    const dados = await readFile(caminho);
    res.writeHead(200, { "content-type": TIPOS[path.extname(caminho)] || "application/octet-stream" });
    res.end(dados);
  } catch {
    res.writeHead(404);
    res.end("não encontrado");
  }
}).listen(PORTA, () => console.log(`Quiz em http://localhost:${PORTA}  ·  Painel em http://localhost:${PORTA}/painel`));
