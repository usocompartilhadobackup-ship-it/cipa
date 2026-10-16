-- =====================================================================
-- Quiz da Segurança CIPA Momesso: banco de dados
-- Rode este arquivo UMA VEZ no SQL Editor do Supabase (projeto novo).
-- Tudo fica no schema "quiz", que não é exposto pela API pública do
-- Supabase: só as funções da Vercel, com a senha do banco, acessam.
-- =====================================================================

create schema if not exists quiz;
revoke all on schema quiz from public;
do $$
begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    execute 'revoke all on schema quiz from anon';
  end if;
  if exists (select 1 from pg_roles where rolname = 'authenticated') then
    execute 'revoke all on schema quiz from authenticated';
  end if;
end $$;

-- ---------------------------------------------------------------------
-- Tabelas
-- ---------------------------------------------------------------------
create table quiz.setores (
  id         uuid primary key default gen_random_uuid(),
  nome       text not null check (length(btrim(nome)) between 2 and 80),
  ativo      boolean not null default true,
  criado_em  timestamptz not null default now()
);
create unique index setores_nome_unico on quiz.setores (lower(btrim(nome)));

create table quiz.funcionarios (
  id             uuid primary key default gen_random_uuid(),
  nome           text not null check (length(btrim(nome)) between 3 and 120),
  matricula      text check (matricula ~ '^[0-9]{1,10}$'),
  setor_id       uuid not null references quiz.setores(id) on delete restrict,
  ativo          boolean not null default true,
  criado_em      timestamptz not null default now(),
  atualizado_em  timestamptz not null default now(),
  constraint funcionarios_matricula_unica unique (matricula)
);

create table quiz.perguntas (
  id            text primary key,
  ordem         int not null unique,
  texto         text not null,
  curto         text not null,
  icone         text not null,
  frase_acerto  text not null
);

create table quiz.alternativas (
  pergunta_id  text not null references quiz.perguntas(id) on delete cascade,
  letra        char(1) not null check (letra in ('A','B','C','D')),
  texto        text not null,
  correta      boolean not null default false,
  primary key (pergunta_id, letra)
);
create unique index alternativas_uma_correta on quiz.alternativas (pergunta_id) where correta;

create table quiz.tentativas (
  id              uuid primary key default gen_random_uuid(),
  funcionario_id  uuid not null references quiz.funcionarios(id) on delete restrict,
  status          text not null default 'em_andamento' check (status in ('em_andamento','concluida')),
  acertos         int,
  total           int,
  iniciada_em     timestamptz not null default now(),
  concluida_em    timestamptz,
  codigo          text unique,
  token_hash      text,
  nome_snapshot   text not null,
  setor_snapshot  text not null,
  brinde_em       timestamptz,
  brinde_por      text,
  -- Regra 1: uma tentativa por funcionário, garantida pelo banco
  constraint tentativas_uma_por_funcionario unique (funcionario_id)
);

create table quiz.respostas (
  tentativa_id   uuid not null references quiz.tentativas(id) on delete restrict,
  pergunta_id    text not null references quiz.perguntas(id) on delete restrict,
  letra          char(1) not null,
  correta        boolean not null,
  respondida_em  timestamptz not null default now(),
  -- Regra 2: cada pergunta é respondida uma única vez
  primary key (tentativa_id, pergunta_id)
);

create table quiz.config (
  id                int primary key default 1 check (id = 1),
  exigir_matricula  boolean not null default false
);
insert into quiz.config default values;

-- Contador de matrícula errada (bloqueia 15 min depois de 5 erros)
create table quiz.bloqueio_matricula (
  funcionario_id  uuid primary key references quiz.funcionarios(id) on delete cascade,
  falhas          int not null default 0,
  bloqueado_ate   timestamptz
);

alter table quiz.setores            enable row level security;
alter table quiz.funcionarios       enable row level security;
alter table quiz.perguntas          enable row level security;
alter table quiz.alternativas       enable row level security;
alter table quiz.tentativas         enable row level security;
alter table quiz.respostas          enable row level security;
alter table quiz.config             enable row level security;
alter table quiz.bloqueio_matricula enable row level security;

-- ---------------------------------------------------------------------
-- Regra 3: tentativas e respostas registradas são imutáveis.
-- Não existe "liberar de novo": nem o sistema nem o painel conseguem
-- apagar ou alterar uma resposta.
-- ---------------------------------------------------------------------
create function quiz.bloquear() returns trigger
language plpgsql as $$
begin
  raise exception 'Operação bloqueada: respostas e tentativas registradas não podem ser alteradas nem apagadas.';
end $$;

create trigger respostas_imutaveis    before update or delete on quiz.respostas  for each row       execute function quiz.bloquear();
create trigger respostas_sem_truncate before truncate          on quiz.respostas  for each statement execute function quiz.bloquear();
create trigger tentativas_sem_delete  before delete            on quiz.tentativas for each row       execute function quiz.bloquear();
create trigger tentativas_sem_truncate before truncate         on quiz.tentativas for each statement execute function quiz.bloquear();

create function quiz.proteger_tentativa() returns trigger
language plpgsql as $$
begin
  if new.id <> old.id or new.funcionario_id <> old.funcionario_id or new.iniciada_em <> old.iniciada_em
     or new.nome_snapshot <> old.nome_snapshot or new.setor_snapshot <> old.setor_snapshot then
    raise exception 'Os dados da tentativa não podem ser alterados.';
  end if;

  if old.status = 'concluida' then
    if new.status <> 'concluida' or new.acertos is distinct from old.acertos or new.total is distinct from old.total
       or new.concluida_em is distinct from old.concluida_em or new.codigo is distinct from old.codigo
       or new.token_hash is distinct from old.token_hash then
      raise exception 'Tentativa concluída não pode ser alterada.';
    end if;
    if old.brinde_em is not null
       and (new.brinde_em is distinct from old.brinde_em or new.brinde_por is distinct from old.brinde_por) then
      raise exception 'A entrega do brinde já foi registrada.';
    end if;
    if new.brinde_em is not null and old.brinde_em is null and old.acertos is distinct from old.total then
      raise exception 'Só quem acertou todas as perguntas tem direito ao brinde.';
    end if;
  else
    if new.brinde_em is not null or new.brinde_por is not null then
      raise exception 'O quiz ainda não foi concluído.';
    end if;
    if new.status = 'concluida' and (new.acertos is null or new.total is null or new.concluida_em is null) then
      raise exception 'Conclusão incompleta.';
    end if;
  end if;
  return new;
end $$;

create trigger tentativas_protegidas before update on quiz.tentativas
  for each row execute function quiz.proteger_tentativa();

-- ---------------------------------------------------------------------
-- Funções do quiz (o gabarito nunca sai do banco antes da resposta)
-- ---------------------------------------------------------------------
create function quiz.gerar_codigo() returns text
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

-- Lista do quiz: só funcionários ativos, sem matrícula nem acertos
create function quiz.lista_publica() returns jsonb
language sql stable set search_path = quiz, pg_temp as $$
  select coalesce(jsonb_agg(jsonb_build_object(
           'id', f.id, 'nome', f.nome, 'setor', s.nome,
           'situacao', coalesce(t.status, 'disponivel')) order by f.nome), '[]'::jsonb)
  from funcionarios f
  join setores s on s.id = f.setor_id
  left join tentativas t on t.funcionario_id = f.id
  where f.ativo;
$$;

-- Perguntas sem a resposta certa e sem a frase de acerto
create function quiz.perguntas_publicas() returns jsonb
language sql stable set search_path = quiz, pg_temp as $$
  select coalesce(jsonb_agg(jsonb_build_object(
           'id', p.id, 'ordem', p.ordem, 'texto', p.texto, 'icone', p.icone,
           'opcoes', (select jsonb_object_agg(a.letra, a.texto) from alternativas a where a.pergunta_id = p.id)
         ) order by p.ordem), '[]'::jsonb)
  from perguntas p;
$$;

create function quiz.resultado_json(p_tentativa uuid) returns jsonb
language sql stable set search_path = quiz, pg_temp as $$
  select jsonb_build_object(
    'nome', t.nome_snapshot, 'setor', t.setor_snapshot,
    'acertos', t.acertos, 'total', t.total, 'codigo', t.codigo, 'concluidaEm', t.concluida_em,
    'revisao', (
      select jsonb_agg(jsonb_build_object(
               'texto', p.texto, 'marcada', r.letra, 'certa', a.letra,
               'textoCerto', a.texto, 'acertou', r.letra = a.letra) order by p.ordem)
      from perguntas p
      join alternativas a on a.pergunta_id = p.id and a.correta
      left join respostas r on r.pergunta_id = p.id and r.tentativa_id = t.id))
  from tentativas t where t.id = p_tentativa;
$$;

-- Inicia ou retoma a tentativa do funcionário (gera um token novo a cada vez)
create function quiz.iniciar(p_funcionario uuid, p_matricula text, p_token_hash text) returns jsonb
language plpgsql set search_path = quiz, pg_temp as $$
declare
  f   record;
  cfg quiz.config;
  t   quiz.tentativas;
  b   quiz.bloqueio_matricula;
begin
  select fu.id, fu.nome, fu.matricula, fu.ativo, s.nome as setor into f
    from funcionarios fu join setores s on s.id = fu.setor_id
   where fu.id = p_funcionario;
  if not found or not f.ativo then
    return jsonb_build_object('erro', 'nao_encontrado');
  end if;

  select * into t from tentativas where funcionario_id = f.id;
  if found and t.status = 'concluida' then
    return jsonb_build_object('erro', 'ja_respondeu');
  end if;

  select * into cfg from config where id = 1;
  if cfg.exigir_matricula then
    if f.matricula is null then
      return jsonb_build_object('erro', 'sem_matricula');
    end if;
    insert into bloqueio_matricula (funcionario_id) values (f.id) on conflict do nothing;
    select * into b from bloqueio_matricula where funcionario_id = f.id for update;
    if b.bloqueado_ate is not null and b.bloqueado_ate > now() then
      return jsonb_build_object('erro', 'bloqueado', 'ate', b.bloqueado_ate);
    end if;
    if p_matricula is distinct from f.matricula then
      update bloqueio_matricula
         set falhas = case when falhas + 1 >= 5 then 0 else falhas + 1 end,
             bloqueado_ate = case when falhas + 1 >= 5 then now() + interval '15 minutes' else null end
       where funcionario_id = f.id
       returning * into b;
      if b.bloqueado_ate is not null then
        return jsonb_build_object('erro', 'bloqueado', 'ate', b.bloqueado_ate);
      end if;
      return jsonb_build_object('erro', 'matricula_errada', 'restam', 5 - b.falhas);
    end if;
    update bloqueio_matricula set falhas = 0, bloqueado_ate = null where funcionario_id = f.id;
  end if;

  insert into tentativas (funcionario_id, nome_snapshot, setor_snapshot, token_hash)
  values (f.id, f.nome, f.setor, p_token_hash)
  on conflict on constraint tentativas_uma_por_funcionario
  do update set token_hash = excluded.token_hash
  returning * into t;

  return jsonb_build_object(
    'tentativa', t.id, 'nome', t.nome_snapshot, 'setor', t.setor_snapshot,
    'respondidas', coalesce((select jsonb_agg(r.pergunta_id) from respostas r where r.tentativa_id = t.id), '[]'::jsonb));
end $$;

-- Registra a resposta, corrige no banco e, na última, valida tudo de novo
create function quiz.responder(p_tentativa uuid, p_token_hash text, p_pergunta text, p_letra text) returns jsonb
language plpgsql set search_path = quiz, pg_temp as $$
declare
  t         quiz.tentativas;
  prox      quiz.perguntas;
  alt       quiz.alternativas;
  certa     quiz.alternativas;
  n_resp    int;
  n_perg    int;
  v_acertos int;
  v_codigo  text;
  base      jsonb;
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
  select * into certa from alternativas where pergunta_id = p_pergunta and correta;

  insert into respostas (tentativa_id, pergunta_id, letra, correta)
  values (t.id, p_pergunta, alt.letra, alt.correta);

  base := jsonb_build_object(
    'acertou', alt.correta, 'letraCorreta', certa.letra, 'textoCorreto', certa.texto,
    'frase', case when alt.correta then prox.frase_acerto end);

  select count(*) into n_resp from respostas where tentativa_id = t.id;
  select count(*) into n_perg from perguntas;
  if n_resp < n_perg then
    return base || jsonb_build_object('concluida', false);
  end if;

  -- Validação final: recalcula os acertos comparando com o gabarito
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

  return base || jsonb_build_object('concluida', true, 'resultado', resultado_json(t.id));
end $$;

-- Tudo o que o Painel da CIPA precisa, numa consulta só
create function quiz.estado_painel() returns jsonb
language sql stable set search_path = quiz, pg_temp as $$
  select jsonb_build_object(
    'setores', coalesce((select jsonb_agg(jsonb_build_object('id', id, 'nome', nome, 'ativo', ativo) order by nome) from setores), '[]'::jsonb),
    'funcionarios', coalesce((select jsonb_agg(jsonb_build_object(
        'id', id, 'nome', nome, 'matricula', matricula, 'setorId', setor_id, 'ativo', ativo) order by nome) from funcionarios), '[]'::jsonb),
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
    'config', (select jsonb_build_object('exigirMatricula', exigir_matricula) from config where id = 1),
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

-- ---------------------------------------------------------------------
-- As 4 perguntas
-- ---------------------------------------------------------------------
insert into quiz.perguntas (id, ordem, texto, curto, icone, frase_acerto) values
 ('q1', 1, 'Qual é a velocidade máxima permitida no estacionamento da empresa?', 'Velocidade máxima', 'velocidade',
  'Acertou! Aqui, a pressa fica do lado de fora!'),
 ('q2', 2, 'Como os carros devem ser estacionados na empresa?', 'Como estacionar o carro', 'carro',
  'Boa! Estacionar de ré é seguir a orientação de segurança da empresa!'),
 ('q3', 3, 'Por onde os pedestres devem circular no estacionamento?', 'Caminho do pedestre', 'pedestre',
  'Muito bem! Caminho seguro é longe da circulação dos veículos!'),
 ('q4', 4, 'Como o motociclista deve sair da empresa com a moto, conforme a regra interna?', 'Saída de moto', 'moto',
  'Acertou! Respeitar o trajeto correto também é cuidar da segurança!');

insert into quiz.alternativas (pergunta_id, letra, texto, correta) values
 ('q1', 'A', '30 km/h', false),
 ('q1', 'B', '20 km/h', true),
 ('q1', 'C', '40 km/h', false),
 ('q2', 'A', 'De frente', false),
 ('q2', 'B', 'De ré', true),
 ('q2', 'C', 'De qualquer jeito', false),
 ('q3', 'A', 'Pelo meio do estacionamento', false),
 ('q3', 'B', 'Entre os carros', false),
 ('q3', 'C', 'Pelas laterais, junto ao canto, conforme a orientação da empresa', true),
 ('q4', 'A', 'Acelerando pelo portão de entrada', false),
 ('q4', 'B', 'Seguindo pela saída indicada ou empurrando a moto pelo portão de entrada', true),
 ('q4', 'C', 'Circulando por qualquer caminho', false);
