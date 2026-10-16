// Conexão com o banco do Supabase pelo pooler em modo transação (porta 6543).
// A conexão vem da variável DATABASE_URL (configurada à mão) ou POSTGRES_URL
// (criada automaticamente pela integração Supabase ↔ Vercel). Nunca vai para o navegador.
import postgres from "postgres";

let conexao = null;

export function db() {
  if (!conexao) {
    const bruto = process.env.DATABASE_URL || process.env.POSTGRES_URL;
    if (!bruto) {
      const e = new Error("A conexão com o banco não está configurada na Vercel (DATABASE_URL ou integração com o Supabase).");
      e.config = true;
      throw e;
    }
    // Remove parâmetros extras da URL (ex.: ?sslmode=...&supa=...); o SSL é definido abaixo
    const url = new URL(bruto);
    url.search = "";
    conexao = postgres(url.toString(), {
      prepare: false,                 // obrigatório no pooler em modo transação
      max: 1,                         // recomendado para funções serverless
      ssl: process.env.DATABASE_SSL === "off" ? false : "require",
      idle_timeout: 20,
      connect_timeout: 10,
    });
  }
  return conexao;
}
