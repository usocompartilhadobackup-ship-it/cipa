-- =====================================================================
-- Quiz da Segurança CIPA Momesso: funções do quiz e do painel
-- Pode ser rodado de novo sem perder dados (create or replace).
-- O gabarito só sai do banco depois que a pessoa termina o quiz.
-- =====================================================================

create or replace function quiz.gerar_codigo() returns text
language plpgsql volatile as $$
declare
  letras text := 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';  -- sem 0/O/1/I
  b bytea := uuid_send(gen_random_uuid());
  r text := '';
begin
  for i in 0..5 loop
    r := r || substr(letras, (get_byte(b, i) % 32) + 1, 1);
  end loop;
  return r;
end $$;

-- Setores que aparecem para o funcionário escolher
create or replace function quiz.setores_publicos() returns jsonb
language sql stable set search_path = quiz, pg_temp as $$
  select coalesce(jsonb_agg(jsonb_build_object('id', id, 'nome', nome) order by nome), '[]'::jsonb)
  from setores where ativo;
$$;

-- Perguntas sem a resposta certa e sem a frase de acerto
create or replace function quiz.perguntas_publicas() returns jsonb
language sql stable set search_path = quiz, pg_temp as $$
  select coalesce(jsonb_agg(jsonb_build_object(
           'id', p.id, 'ordem', p.ordem, 'texto', p.texto, 'icone', p.icone,
           'opcoes', (select jsonb_object_agg(a.letra, a.texto) from alternativas a where a.pergunta_id = p.id)
         ) order by p.ordem), '[]'::jsonb)
  from perguntas p;
$$;

-- Ranking público: só quem acertou todas, do mais rápido ao mais lento
create or replace function quiz.ranking_publico() returns jsonb
language sql stable set search_path = quiz, pg_temp as $$
  select coalesce(jsonb_agg(jsonb_build_object(
           'id', t.id, 'nome', t.nome_snapshot, 'setor', t.setor_snapshot,
           'ms', round(extract(epoch from t.concluida_em - t.iniciada_em) * 1000)::bigint
         ) order by t.concluida_em - t.iniciada_em, t.concluida_em), '[]'::jsonb)
  from tentativas t
  where t.status = 'concluida' and t.acertos = t.total;
$$;

create or replace function quiz.resultado_json(p_tentativa uuid) returns jsonb
language sql stable set search_path = quiz, pg_temp as $$
  select jsonb_build_object(
    'id', t.id, 'nome', t.nome_snapshot, 'setor', t.setor_snapshot,
    'acertos', t.acertos, 'total', t.total, 'codigo', t.codigo, 'concluidaEm', t.concluida_em,
    'ms', round(extract(epoch from t.concluida_em - t.iniciada_em) * 1000)::bigint,
    'revisao', (
      select jsonb_agg(jsonb_build_object(
               'texto', p.texto, 'marcada', r.letra, 'textoMarcada', am.texto,
               'certa', a.letra, 'textoCerto', a.texto, 'acertou', r.letra = a.letra,
               'frase', case when r.letra = a.letra then p.frase_acerto end) order by p.ordem)
      from perguntas p
      join alternativas a on a.pergunta_id = p.id and a.correta
      left join respostas r on r.pergunta_id = p.id and r.tentativa_id = t.id
      left join alternativas am on am.pergunta_id = p.id and am.letra = r.letra))
  from tentativas t where t.id = p_tentativa;
$$;

-- Identifica a pessoa por nome + setor (cria na primeira vez) e inicia ou
-- retoma a tentativa. Gera um token novo a cada vez.
create or replace function quiz.iniciar(p_nome text, p_setor uuid, p_token_hash text) returns jsonb
language plpgsql set search_path = quiz, pg_temp as $$
declare
  s quiz.setores;
  f quiz.funcionarios;
  t quiz.tentativas;
begin
  select * into s from setores where id = p_setor;
  if not found or not s.ativo then
    return jsonb_build_object('erro', 'setor_invalido');
  end if;

  insert into funcionarios (nome, setor_id) values (btrim(p_nome), s.id)
  on conflict on constraint funcionarios_nome_setor_unico do nothing;
  select * into f from funcionarios where setor_id = s.id and nome_chave = chave_nome(p_nome);

  select * into t from tentativas where funcionario_id = f.id;
  if found and t.status = 'concluida' then
    return jsonb_build_object('erro', 'ja_respondeu');
  end if;

  insert into tentativas (funcionario_id, nome_snapshot, setor_snapshot, token_hash)
  values (f.id, f.nome, s.nome, p_token_hash)
  on conflict on constraint tentativas_uma_por_funcionario
  do update set token_hash = excluded.token_hash
  returning * into t;

  return jsonb_build_object(
    'tentativa', t.id, 'nome', t.nome_snapshot, 'setor', t.setor_snapshot,
    'iniciadaEm', t.iniciada_em, 'agora', now(),
    'respondidas', coalesce((select jsonb_agg(r.pergunta_id) from respostas r where r.tentativa_id = t.id), '[]'::jsonb));
end $$;

-- Registra a resposta sem revelar se acertou. Na última, corrige tudo,
-- conclui e devolve o resultado com a revisão e o ranking.
create or replace function quiz.responder(p_tentativa uuid, p_token_hash text, p_pergunta text, p_letra text) returns jsonb
language plpgsql set search_path = quiz, pg_temp as $$
declare
  t         quiz.tentativas;
  prox      quiz.perguntas;
  alt       quiz.alternativas;
  n_resp    int;
  n_perg    int;
  v_acertos int;
  v_codigo  text;
begin
  select * into t from tentativas where id = p_tentativa for update;
  if not found or t.token_hash is distinct from p_token_hash then
    return jsonb_build_object('erro', 'sessao_invalida');
  end if;
  if t.status = 'concluida' then
    return jsonb_build_object('erro', 'ja_respondeu');
  end if;

  select p.* into prox from perguntas p
   where not exists (select 1 from respostas r where r.tentativa_id = t.id and r.pergunta_id = p.id)
   order by p.ordem limit 1;
  if prox.id is distinct from p_pergunta then
    return jsonb_build_object('erro', 'fora_de_ordem', 'proxima', prox.id);
  end if;

  select * into alt from alternativas where pergunta_id = p_pergunta and letra = upper(p_letra);
  if not found then
    return jsonb_build_object('erro', 'alternativa_invalida');
  end if;

  insert into respostas (tentativa_id, pergunta_id, letra, correta)
  values (t.id, p_pergunta, alt.letra, alt.correta);

  select count(*) into n_resp from respostas where tentativa_id = t.id;
  select count(*) into n_perg from perguntas;
  if n_resp < n_perg then
    return jsonb_build_object('concluida', false);
  end if;

  -- Correção final: compara todas as respostas com o gabarito
  select count(*) into v_acertos
    from respostas r
    join alternativas a on a.pergunta_id = r.pergunta_id and a.letra = r.letra and a.correta
   where r.tentativa_id = t.id;

  if v_acertos = n_perg then
    loop
      v_codigo := gerar_codigo();
      exit when not exists (select 1 from tentativas where codigo = v_codigo);
    end loop;
  end if;

  update tentativas
     set status = 'concluida', acertos = v_acertos, total = n_perg,
         concluida_em = now(), codigo = v_codigo
   where id = t.id;

  return jsonb_build_object('concluida', true, 'resultado', resultado_json(t.id), 'ranking', ranking_publico());
end $$;

-- Tudo o que o Painel da CIPA precisa, numa consulta só
create or replace function quiz.estado_painel() returns jsonb
language sql stable set search_path = quiz, pg_temp as $$
  select jsonb_build_object(
    'setores', coalesce((select jsonb_agg(jsonb_build_object('id', id, 'nome', nome, 'ativo', ativo) order by nome) from setores), '[]'::jsonb),
    'funcionarios', coalesce((select jsonb_agg(jsonb_build_object('id', id, 'nome', nome, 'setorId', setor_id) order by nome) from funcionarios), '[]'::jsonb),
    'tentativas', coalesce((select jsonb_agg(jsonb_build_object(
        'id', t.id, 'funcionarioId', t.funcionario_id, 'status', t.status,
        'acertos', t.acertos, 'total', t.total, 'iniciadaEm', t.iniciada_em, 'concluidaEm', t.concluida_em,
        'codigo', t.codigo, 'nome', t.nome_snapshot, 'setor', t.setor_snapshot,
        'brindeEm', t.brinde_em, 'brindePor', t.brinde_por,
        'respostas', coalesce((select jsonb_object_agg(r.pergunta_id, jsonb_build_object('l', r.letra, 'em', r.respondida_em))
                                 from respostas r where r.tentativa_id = t.id), '{}'::jsonb)))
      from tentativas t), '[]'::jsonb),
    'perguntas', coalesce((select jsonb_agg(jsonb_build_object(
        'id', p.id, 'ordem', p.ordem, 'texto', p.texto, 'curto', p.curto, 'icone', p.icone,
        'opcoes', (select jsonb_object_agg(a.letra, a.texto) from alternativas a where a.pergunta_id = p.id),
        'correta', (select a.letra from alternativas a where a.pergunta_id = p.id and a.correta)) order by p.ordem)
      from perguntas p), '[]'::jsonb),
    'agora', now());
$$;

revoke all on all tables in schema quiz from public;
revoke all on all functions in schema quiz from public;
do $$
begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    execute 'revoke all on all tables in schema quiz from anon';
    execute 'revoke all on all functions in schema quiz from anon';
  end if;
  if exists (select 1 from pg_roles where rolname = 'authenticated') then
    execute 'revoke all on all tables in schema quiz from authenticated';
    execute 'revoke all on all functions in schema quiz from authenticated';
  end if;
end $$;
