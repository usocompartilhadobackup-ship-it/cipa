// API do Painel da CIPA. Tudo exige login, menos as ações login e sair.
// Não existe nenhuma ação para liberar, resetar ou apagar respostas.
import { db } from "../lib/db.js";
import { json, erro, lerCorpo, ehUuid, texto, mensagemDoBanco, ErroUsuario } from "../lib/http.js";
import { conferir, cookieDeSessao, cookieDeSaida, sessaoValida, ipDe } from "../lib/auth.js";

function validarNome(nome, min, max, campo) {
  const n = texto(nome).replace(/\s+/g, " ");
  if (n.length < min || n.length > max) throw new ErroUsuario(`Informe ${campo} (de ${min} a ${max} letras).`);
  return n;
}
function exigirUuid(v, oque = "registro") {
  if (!ehUuid(v)) throw new ErroUsuario(`Não encontrei esse ${oque}.`);
  return v;
}

async function acaoPost(sql, acao, c) {
  switch (acao) {
    case "brinde": {
      const id = exigirUuid(c.tentativaId, "comprovante");
      const por = "CIPA";
      const linhas = await sql`
        update quiz.tentativas set brinde_em = now(), brinde_por = ${por}
         where id = ${id} and status = 'concluida' and acertos = total and brinde_em is null
        returning nome_snapshot`;
      if (!linhas.length) throw new ErroUsuario("Esse brinde já foi entregue ou a pessoa não acertou todas.", 409);
      return { ok: true, mensagem: `Entrega registrada para ${linhas[0].nome_snapshot}.` };
    }
    case "setor-salvar": {
      const nome = validarNome(c.nome, 2, 80, "o nome do setor");
      if (c.id) {
        const l = await sql`update quiz.setores set nome = ${nome} where id = ${exigirUuid(c.id, "setor")} returning id`;
        if (!l.length) throw new ErroUsuario("Não encontrei esse setor.", 404);
        return { ok: true, mensagem: "Setor renomeado." };
      }
      await sql`insert into quiz.setores (nome) values (${nome})`;
      return { ok: true, mensagem: `Setor ${nome} criado.` };
    }
    case "setor-ativo": {
      const l = await sql`update quiz.setores set ativo = ${!!c.ativo} where id = ${exigirUuid(c.id, "setor")} returning nome`;
      if (!l.length) throw new ErroUsuario("Não encontrei esse setor.", 404);
      return { ok: true, mensagem: `Setor ${l[0].nome} ${c.ativo ? "ativado" : "inativado"}.` };
    }
    case "setor-excluir": {
      const l = await sql`delete from quiz.setores where id = ${exigirUuid(c.id, "setor")} returning nome`;
      if (!l.length) throw new ErroUsuario("Não encontrei esse setor.", 404);
      return { ok: true, mensagem: `Setor ${l[0].nome} excluído.` };
    }
    default:
      throw new ErroUsuario("Ação desconhecida.", 404);
  }
}

async function login(sql, request) {
  const c = await lerCorpo(request);
  const ip = ipDe(request);
  const [b] = await sql`select bloqueado_ate from quiz.login_falhas where ip = ${ip} and bloqueado_ate > now()`;
  if (b) {
    const hora = new Date(b.bloqueado_ate).toLocaleTimeString("pt-BR", { timeZone: "America/Sao_Paulo", hour: "2-digit", minute: "2-digit" });
    return erro(`Muitas tentativas erradas. Tente de novo depois das ${hora}.`, 429);
  }
  if (conferir(c.email, c.senha)) {
    await sql`delete from quiz.login_falhas where ip = ${ip}`;
    return json({ ok: true }, 200, { "set-cookie": cookieDeSessao(request) });
  }
  const [f] = await sql`
    insert into quiz.login_falhas (ip, falhas) values (${ip}, 1)
    on conflict (ip) do update set
      falhas = case when quiz.login_falhas.falhas + 1 >= 5 then 0 else quiz.login_falhas.falhas + 1 end,
      bloqueado_ate = case when quiz.login_falhas.falhas + 1 >= 5 then now() + interval '15 minutes' else null end
    returning falhas, bloqueado_ate`;
  if (f.bloqueado_ate) return erro("Muitas tentativas erradas. O acesso foi bloqueado por 15 minutos.", 429);
  const restam = 5 - f.falhas;
  return erro(`E-mail ou senha incorretos. ${restam} tentativa${restam === 1 ? "" : "s"} antes de bloquear por 15 minutos.`, 401);
}

export default {
  async fetch(request) {
    const acao = new URL(request.url).searchParams.get("acao");
    try {
      const sql = db();
      if (request.method === "POST" && acao === "login") return await login(sql, request);
      if (request.method === "POST" && acao === "sair") return json({ ok: true }, 200, { "set-cookie": cookieDeSaida(request) });
      if (!sessaoValida(request)) return json({ erro: "Entre com o e-mail e a senha da CIPA.", login: true }, 401);

      if (request.method === "GET" && acao === "estado") {
        const [{ estado }] = await sql`select quiz.estado_painel() as estado`;
        return json({ ...estado, papel: "admin" });
      }
      if (request.method === "POST") {
        const corpo = await lerCorpo(request);
        return json(await acaoPost(sql, acao, corpo));
      }
      return erro("Rota não encontrada.", 404);
    } catch (e) {
      const { msg, status } = mensagemDoBanco(e);
      return erro(msg, status);
    }
  },
};
