// Login do Painel da CIPA (um único usuário administrador).
// A senha nunca fica no código: a Vercel guarda só o hash em ADMIN_SENHA_HASH
// (gerado por ferramentas/gerar-senha.mjs) e o e-mail em ADMIN_EMAIL.
// A sessão é um cookie HttpOnly assinado com HMAC; trocar a senha derruba todas as sessões.
import { createHmac, randomBytes, scryptSync, timingSafeEqual } from "node:crypto";

const COOKIE = "cipa_admin";
const DURACAO_S = 12 * 60 * 60;
const SCRYPT = { N: 16384, r: 8, p: 1 };

export function gerarHash(senha) {
  const sal = randomBytes(16);
  const h = scryptSync(senha, sal, 32, SCRYPT);
  return `scrypt$${sal.toString("base64url")}$${h.toString("base64url")}`;
}

function config() {
  const email = (process.env.ADMIN_EMAIL || "").trim().toLowerCase();
  const hash = (process.env.ADMIN_SENHA_HASH || "").trim();
  if (!email || !/^scrypt\$[\w-]+\$[\w-]+$/.test(hash)) {
    const e = new Error("O login do painel não está configurado na Vercel (ADMIN_EMAIL e ADMIN_SENHA_HASH).");
    e.config = true;
    throw e;
  }
  return { email, hash };
}

const iguais = (a, b) => a.length === b.length && timingSafeEqual(a, b);

// Sempre calcula o scrypt, mesmo com e-mail errado, para não revelar qual campo errou pelo tempo
export function conferir(email, senha) {
  const cfg = config();
  const [, sal, esperado] = cfg.hash.split("$");
  const h = scryptSync(String(senha || ""), Buffer.from(sal, "base64url"), 32, SCRYPT);
  const senhaOk = iguais(h, Buffer.from(esperado, "base64url"));
  const emailOk = String(email || "").trim().toLowerCase() === cfg.email;
  return senhaOk && emailOk;
}

const assinar = (dados, chave) => createHmac("sha256", chave).update(dados).digest("base64url");

export function cookieDeSessao(request) {
  const { hash } = config();
  const dados = Buffer.from(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + DURACAO_S })).toString("base64url");
  return `${COOKIE}=${dados}.${assinar(dados, hash)}; ${atributos(request)}; Max-Age=${DURACAO_S}`;
}

export function cookieDeSaida(request) {
  return `${COOKIE}=; ${atributos(request)}; Max-Age=0`;
}

function atributos(request) {
  const local = ["localhost", "127.0.0.1"].includes(new URL(request.url).hostname);
  return `Path=/api/admin; HttpOnly; SameSite=Strict${local ? "" : "; Secure"}`;
}

export function sessaoValida(request) {
  const { hash } = config();
  const m = (request.headers.get("cookie") || "").match(new RegExp(`(?:^|;\\s*)${COOKIE}=([\\w-]+)\\.([\\w-]+)`));
  if (!m) return false;
  const [, dados, assinatura] = m;
  if (!iguais(Buffer.from(assinatura), Buffer.from(assinar(dados, hash)))) return false;
  try {
    return JSON.parse(Buffer.from(dados, "base64url").toString()).exp > Date.now() / 1000;
  } catch {
    return false;
  }
}

export function ipDe(request) {
  return (request.headers.get("x-forwarded-for") || "").split(",")[0].trim() || "local";
}
