// API pública do quiz (sem login). O gabarito nunca sai do banco antes da resposta.
import { createHash, randomBytes } from "node:crypto";
import { db } from "../lib/db.js";
import { json, erro, lerCorpo, ehUuid, texto, mensagemDoBanco, ErroUsuario } from "../lib/http.js";

const hash = (t) => createHash("sha256").update(t).digest("hex");

const MENSAGENS = {
  nao_encontrado: ["Seu nome não está mais na lista. Fale com um membro da CIPA.", 404],
  ja_respondeu: ["Você já respondeu o quiz. Cada pessoa responde uma única vez.", 409],
  sem_matricula: ["Seu cadastro está sem matrícula. Procure a CIPA para atualizar.", 409],
  sessao_invalida: ["Seu quiz foi aberto em outro aparelho. Escolha seu nome de novo para continuar daqui.", 409],
  fora_de_ordem: ["Essa pergunta não é a próxima. Escolha seu nome de novo para continuar.", 409],
  alternativa_invalida: ["Escolha uma das alternativas.", 400],
};

function respostaDeErro(r) {
  if (r.erro === "matricula_errada") {
    return erro(`Matrícula não confere. Confira e tente de novo (${r.restam} tentativa${r.restam === 1 ? "" : "s"} antes de bloquear por 15 minutos).`, 400);
  }
  if (r.erro === "bloqueado") {
    const hora = new Date(r.ate).toLocaleTimeString("pt-BR", { timeZone: "America/Sao_Paulo", hour: "2-digit", minute: "2-digit" });
    return erro(`Muitas tentativas com a matrícula errada. Tente de novo depois das ${hora}.`, 429);
  }
  const [msg, status] = MENSAGENS[r.erro] || ["Não foi possível continuar. Tente de novo.", 400];
  return json({ erro: msg, codigo: r.erro }, status);
}

export default {
  async fetch(request) {
    const acao = new URL(request.url).searchParams.get("acao");
    try {
      const sql = db();

      if (request.method === "GET" && acao === "inicio") {
        const [{ lista, perguntas, cfg }] = await sql`
          select quiz.lista_publica() as lista, quiz.perguntas_publicas() as perguntas,
                 (select exigir_matricula from quiz.config where id = 1) as cfg`;
        return json({ funcionarios: lista, perguntas, exigirMatricula: cfg });
      }

      if (request.method === "POST" && acao === "iniciar") {
        const corpo = await lerCorpo(request);
        if (!ehUuid(corpo.funcionarioId)) throw new ErroUsuario("Escolha seu nome na lista.");
        const matricula = texto(corpo.matricula) || null;
        const token = randomBytes(24).toString("base64url");
        const [{ r }] = await sql`select quiz.iniciar(${corpo.funcionarioId}, ${matricula}, ${hash(token)}) as r`;
        if (r.erro) return respostaDeErro(r);
        return json({ tentativaId: r.tentativa, token, nome: r.nome, setor: r.setor, respondidas: r.respondidas });
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
