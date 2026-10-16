export function json(dados, status = 200, extra = {}) {
  return new Response(JSON.stringify(dados), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", ...extra },
  });
}

export function erro(mensagem, status = 400, extra = {}) {
  return json({ erro: mensagem }, status, extra);
}

export async function lerCorpo(request) {
  const texto = await request.text();
  if (texto.length > 200_000) throw new ErroUsuario("Conteúdo grande demais.");
  if (!texto) return {};
  try {
    const dados = JSON.parse(texto);
    if (!dados || typeof dados !== "object" || Array.isArray(dados)) throw new Error();
    return dados;
  } catch {
    throw new ErroUsuario("Requisição inválida.");
  }
}

export class ErroUsuario extends Error {
  constructor(mensagem, status = 400) {
    super(mensagem);
    this.status = status;
  }
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export const ehUuid = (v) => typeof v === "string" && UUID.test(v);
export const texto = (v) => (typeof v === "string" ? v.trim() : "");

// Converte erros do Postgres em mensagens que fazem sentido para quem usa o painel
export function mensagemDoBanco(e) {
  if (e instanceof ErroUsuario) return { msg: e.message, status: e.status };
  const c = e && e.constraint_name;
  if (e && e.code === "23505") {
    if (c === "setores_nome_unico") return { msg: "Já existe um setor com esse nome.", status: 409 };
    if (c === "funcionarios_matricula_unica") return { msg: "Já existe um funcionário com essa matrícula.", status: 409 };
    return { msg: "Esse registro já existe.", status: 409 };
  }
  if (e && e.code === "23503") {
    if (c === "tentativas_funcionario_id_fkey") return { msg: "Quem já respondeu o quiz não pode ser excluído, só inativado.", status: 409 };
    if (c === "funcionarios_setor_id_fkey") return { msg: "Setor com funcionários não pode ser excluído, só inativado.", status: 409 };
    return { msg: "Esse registro está em uso e não pode ser excluído.", status: 409 };
  }
  if (e && e.code === "23514") return { msg: "Dados inválidos. Confira o nome e a matrícula (só números).", status: 400 };
  if (e && e.code === "P0001") return { msg: e.message, status: 409 };
  if (e && e.config) return { msg: e.message, status: 503 };
  console.error(e);
  return { msg: "Não foi possível falar com o banco de dados. Tente de novo em instantes.", status: 503 };
}
