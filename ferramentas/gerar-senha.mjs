// Gera o valor de ADMIN_SENHA_HASH para o login do painel.
// Uso: node ferramentas/gerar-senha.mjs
// Digite a senha quando pedir (ela não aparece na tela) e cole o resultado na Vercel:
// Settings > Environment Variables > ADMIN_SENHA_HASH (Production, Sensitive). Depois, faça um novo deploy.
import { gerarHash } from "../lib/auth.js";

process.stdout.write("Nova senha do painel: ");
const senha = await new Promise((ok) => {
  let s = "";
  const tty = process.stdin.isTTY;
  if (tty) process.stdin.setRawMode(true);
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (c) => {
    for (const ch of c) {
      if (ch === "\r" || ch === "\n") { if (tty) process.stdin.setRawMode(false); process.stdin.pause(); process.stdout.write("\n"); return ok(s); }
      if (ch === "\u0003") process.exit(1);
      if (ch === "\u007f" || ch === "\b") s = s.slice(0, -1); else s += ch;
    }
  });
});
if (senha.length < 8) { console.error("Use pelo menos 8 caracteres."); process.exit(1); }
console.log("\nADMIN_SENHA_HASH=" + gerarHash(senha));
