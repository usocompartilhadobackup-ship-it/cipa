// Protege o site inteiro com usuário e senha (Basic Auth).
// O usuário e a senha ficam nas variáveis de ambiente da Vercel:
//   BASIC_AUTH_USER e BASIC_AUTH_PASSWORD
// Sem essas variáveis, o site fica bloqueado (nunca abre sem senha).
import { next } from "@vercel/functions";

const REALM = "Quiz CIPA Momesso";

function decodificar(base64) {
  const binario = atob(base64);
  const bytes = Uint8Array.from(binario, (c) => c.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

function iguais(a, b) {
  // Comparação em tempo constante para não revelar a senha pelo tempo de resposta
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export default function middleware(request) {
  const usuario = process.env.BASIC_AUTH_USER;
  const senha = process.env.BASIC_AUTH_PASSWORD;

  if (!usuario || !senha) {
    return new Response(
      "Site bloqueado: configure BASIC_AUTH_USER e BASIC_AUTH_PASSWORD nas variáveis de ambiente da Vercel e publique de novo.",
      { status: 503, headers: { "content-type": "text/plain; charset=utf-8" } }
    );
  }

  const cabecalho = request.headers.get("authorization") || "";
  const [esquema, credencial] = cabecalho.split(" ");

  if (esquema === "Basic" && credencial) {
    try {
      const texto = decodificar(credencial);
      const i = texto.indexOf(":");
      if (i > -1 && iguais(texto.slice(0, i), usuario) && iguais(texto.slice(i + 1), senha)) {
        return next();
      }
    } catch (e) {
      // credencial malformada: cai no 401 abaixo
    }
  }

  return new Response("Acesso restrito. Informe o usuário e a senha.", {
    status: 401,
    headers: {
      "WWW-Authenticate": `Basic realm="${REALM}", charset="UTF-8"`,
      "content-type": "text/plain; charset=utf-8",
    },
  });
}
