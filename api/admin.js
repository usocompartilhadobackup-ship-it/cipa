// API do Painel da CIPA e da Administração (aberta, sem login).
// Não existe nenhuma ação para liberar, resetar ou apagar respostas.
import { db } from "../lib/db.js";
import { json, erro, lerCorpo, ehUuid, texto, mensagemDoBanco, ErroUsuario } from "../lib/http.js";

function validarNome(nome, min, max, campo) {
  const n = texto(nome).replace(/\s+/g, " ");
  if (n.length < min || n.length > max) throw new ErroUsuario(`Informe ${campo} (de ${min} a ${max} letras).`);
  return n;
}
function validarMatricula(m) {
  const v = texto(m);
  if (!v) return null;
  if (!/^\d{1,10}$/.test(v)) throw new ErroUsuario("A matrícula deve ter só números.");
  return v;
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
    case "func-salvar": {
      const nome = validarNome(c.nome, 3, 120, "o nome completo");
      const matricula = validarMatricula(c.matricula);
      const setorId = exigirUuid(c.setorId, "setor");
      const ativo = c.ativo !== false;
      if (c.id) {
        const l = await sql`
          update quiz.funcionarios set nome = ${nome}, matricula = ${matricula}, setor_id = ${setorId}, ativo = ${ativo}, atualizado_em = now()
           where id = ${exigirUuid(c.id, "funcionário")} returning id`;
        if (!l.length) throw new ErroUsuario("Não encontrei esse funcionário.", 404);
        return { ok: true, mensagem: "Alterações salvas." };
      }
      await sql`insert into quiz.funcionarios (nome, matricula, setor_id, ativo) values (${nome}, ${matricula}, ${setorId}, ${ativo})`;
      return { ok: true, mensagem: `${nome} foi cadastrado.` };
    }
    case "func-ativo": {
      const l = await sql`update quiz.funcionarios set ativo = ${!!c.ativo}, atualizado_em = now() where id = ${exigirUuid(c.id, "funcionário")} returning nome`;
      if (!l.length) throw new ErroUsuario("Não encontrei esse funcionário.", 404);
      return { ok: true, mensagem: c.ativo ? `${l[0].nome} foi ativado.` : `${l[0].nome} foi inativado e saiu da lista do quiz.` };
    }
    case "func-excluir": {
      const l = await sql`delete from quiz.funcionarios where id = ${exigirUuid(c.id, "funcionário")} returning nome`;
      if (!l.length) throw new ErroUsuario("Não encontrei esse funcionário.", 404);
      return { ok: true, mensagem: `${l[0].nome} foi excluído.` };
    }
    case "importar": {
      if (!Array.isArray(c.linhas) || !c.linhas.length) throw new ErroUsuario("Nenhuma linha para importar.");
      if (c.linhas.length > 3000) throw new ErroUsuario("Importe no máximo 3.000 funcionários por vez.");
      const criarSetores = c.criarSetores !== false;
      return await sql.begin(async (tx) => {
        const setores = await tx`select id, nome from quiz.setores`;
        const porNome = new Map(setores.map((s) => [s.nome.trim().toLowerCase(), s.id]));
        const existentes = await tx`select lower(nome) as nome, matricula from quiz.funcionarios`;
        const nomes = new Set(existentes.map((f) => f.nome));
        const mats = new Set(existentes.map((f) => f.matricula).filter(Boolean));
        let criados = 0, ignorados = 0, setoresNovos = 0;
        for (const linha of c.linhas) {
          let nome, matricula, setorNome;
          try {
            nome = validarNome(linha.nome, 3, 120, "o nome");
            matricula = validarMatricula(linha.matricula);
            setorNome = validarNome(linha.setor, 2, 80, "o setor");
          } catch { ignorados++; continue; }
          if (nomes.has(nome.toLowerCase()) || (matricula && mats.has(matricula))) { ignorados++; continue; }
          let setorId = porNome.get(setorNome.toLowerCase());
          if (!setorId) {
            if (!criarSetores) { ignorados++; continue; }
            const [s] = await tx`insert into quiz.setores (nome) values (${setorNome}) returning id`;
            setorId = s.id; porNome.set(setorNome.toLowerCase(), setorId); setoresNovos++;
          }
          await tx`insert into quiz.funcionarios (nome, matricula, setor_id) values (${nome}, ${matricula}, ${setorId})`;
          nomes.add(nome.toLowerCase()); if (matricula) mats.add(matricula);
          criados++;
        }
        const partes = [`${criados} funcionário${criados === 1 ? " importado" : "s importados"}`];
        if (setoresNovos) partes.push(`${setoresNovos} setor${setoresNovos === 1 ? " novo" : "es novos"}`);
        if (ignorados) partes.push(`${ignorados} ignorado${ignorados === 1 ? "" : "s"}`);
        return { ok: true, criados, ignorados, setoresNovos, mensagem: partes.join(", ") + "." };
      });
    }
    case "config": {
      await sql`update quiz.config set exigir_matricula = ${!!c.exigirMatricula} where id = 1`;
      return { ok: true, mensagem: c.exigirMatricula ? "Agora o quiz pede a matrícula." : "O quiz não pede mais a matrícula." };
    }
    default:
      throw new ErroUsuario("Ação desconhecida.", 404);
  }
}

export default {
  async fetch(request) {
    const acao = new URL(request.url).searchParams.get("acao");
    try {
      const sql = db();
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
