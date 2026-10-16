// API pública do quiz (sem login). O gabarito só sai do banco quando a pessoa termina.
import { createHash, randomBytes } from "node:crypto";
import { db } from "../lib/db.js";
import { json, erro, lerCorpo, ehUuid, texto, mensagemDoBanco, ErroUsuario } from "../lib/http.js";

const hash = (t) => createHash("sha256").update(t).digest("hex");

const MENSAGENS = {
  setor_invalido: ["Esse setor não está mais disponível. Escolha seu setor de novo.", 409],
  ja_respondeu: ["Você já respondeu o quiz. Cada pessoa responde uma única vez.", 409],
  sessao_invalida: ["Seu quiz foi aberto em outro aparelho. Digite seu nome de novo para continuar daqui.", 409],
  fora_de_ordem: ["Essa pergunta não é a próxima. Digite seu nome de novo para continuar.", 409],
  alternativa_invalida: ["Escolha uma das alternativas.", 400],
};

function respostaDeErro(r) {
  const [msg, status] = MENSAGENS[r.erro] || ["Não foi possível continuar. Tente de novo.", 400];
  return json({ erro: msg, codigo: r.erro }, status);
}

// "JOÃO  da silva" -> "João da Silva"
const MINUSCULAS = new Set(["da", "das", "de", "do", "dos", "e"]);
function nomeProprio(n) {
  return n.toLocaleLowerCase("pt-BR").split(" ")
    .map((p, i) => (i && MINUSCULAS.has(p) ? p : p.charAt(0).toLocaleUpperCase("pt-BR") + p.slice(1)))
    .join(" ");
}
function validarNome(bruto) {
  const n = texto(bruto).replace(/\s+/g, " ");
  if (n.length > 120) throw new ErroUsuario("Nome grande demais.");
  if (!/^[\p{L}][\p{L}'’.\- ]*$/u.test(n)) throw new ErroUsuario("Digite seu nome só com letras.");
  if (n.split(" ").filter((p) => /\p{L}{2,}/u.test(p)).length < 2) throw new ErroUsuario("Digite seu nome e sobrenome.");
  return nomeProprio(n);
}

export default {
  async fetch(request) {
    const acao = new URL(request.url).searchParams.get("acao");
    try {
      const sql = db();

      if (request.method === "GET" && acao === "inicio") {
        const [{ setores, perguntas }] = await sql`
          select quiz.setores_publicos() as setores, quiz.perguntas_publicas() as perguntas`;
        return json({ setores, perguntas });
      }

      if (request.method === "GET" && acao === "ranking") {
        const [{ ranking }] = await sql`select quiz.ranking_publico() as ranking`;
        return json({ ranking });
      }

      if (request.method === "POST" && acao === "iniciar") {
        const corpo = await lerCorpo(request);
        const nome = validarNome(corpo.nome);
        if (!ehUuid(corpo.setorId)) throw new ErroUsuario("Escolha seu setor.");
        const token = randomBytes(24).toString("base64url");
        const [{ r }] = await sql`select quiz.iniciar(${nome}, ${corpo.setorId}, ${hash(token)}) as r`;
        if (r.erro) return respostaDeErro(r);
        return json({ tentativaId: r.tentativa, token, nome: r.nome, setor: r.setor, respondidas: r.respondidas, iniciadaEm: r.iniciadaEm, agora: r.agora });
      }

      if (request.method === "POST" && acao === "responder") {
        const corpo = await lerCorpo(request);
        const letra = texto(corpo.letra).toUpperCase();
        if (!ehUuid(corpo.tentativaId) || !texto(corpo.token) || !/^q\d{1,3}$/.test(texto(corpo.perguntaId)) || !/^[A-D]$/.test(letra)) {
          throw new ErroUsuario("Escolha uma das alternativas.");
        }
        const [{ r }] = await sql`select quiz.responder(${corpo.tentativaId}, ${hash(texto(corpo.token))}, ${corpo.perguntaId}, ${letra}) as r`;
        if (r.erro) return respostaDeErro(r);
        return json(r);
      }

      return erro("Rota não encontrada.", 404);
    } catch (e) {
      const { msg, status } = mensagemDoBanco(e);
      return erro(msg, status);
    }
  },
};
