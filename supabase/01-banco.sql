-- =====================================================================
-- Quiz da Segurança CIPA Momesso: banco de dados (tabelas e regras)
-- Projeto novo: rode este arquivo UMA VEZ no SQL Editor do Supabase e
-- depois o 02-funcoes.sql.
-- Tudo fica no schema "quiz", que não é exposto pela API pública do
-- Supabase: só as funções da Vercel, com a senha do banco, acessam.
--
-- Não há cadastro prévio de funcionários: a CIPA cadastra os setores no
-- painel e o funcionário digita o nome e escolhe o setor ao entrar.
-- Nome + setor identificam a pessoa (uma tentativa para cada par).
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

-- Chave do nome para comparar sem maiúsculas, acentos e espaços repetidos
-- ("João  da Silva" e "joao da silva" são a mesma pessoa no mesmo setor)
create function quiz.chave_nome(p text) returns text
language sql immutable parallel safe as $$
  select lower(regexp_replace(btrim(translate(p,
    'ÁÀÂÃÄáàâãäÉÈÊËéèêëÍÌÎÏíìîïÓÒÔÕÖóòôõöÚÙÛÜúùûüÇçÑñ',
    'AAAAAaaaaaEEEEeeeeIIIIiiiiOOOOOoooooUUUUuuuuCcNn')), '\s+', ' ', 'g'));
$$;

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

-- Participantes: criados quando a pessoa começa o quiz
create table quiz.funcionarios (
  id          uuid primary key default gen_random_uuid(),
  nome        text not null check (length(btrim(nome)) between 3 and 120),
  nome_chave  text generated always as (quiz.chave_nome(nome)) stored,
  setor_id    uuid not null references quiz.setores(id) on delete restrict,
  criado_em   timestamptz not null default now(),
  constraint funcionarios_nome_setor_unico unique (setor_id, nome_chave)
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
  -- Regra 1: uma tentativa por pessoa (nome + setor), garantida pelo banco
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

-- Login do painel: 5 senhas erradas seguidas bloqueiam o endereço por 15 minutos
create table quiz.login_falhas (
  ip             text primary key,
  falhas         int not null default 0,
  bloqueado_ate  timestamptz
);
alter table quiz.login_falhas enable row level security;

alter table quiz.setores      enable row level security;
alter table quiz.funcionarios enable row level security;
alter table quiz.perguntas    enable row level security;
alter table quiz.alternativas enable row level security;
alter table quiz.tentativas   enable row level security;
alter table quiz.respostas    enable row level security;

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
-- Perguntas e alternativas (as 4 do quiz)
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

-- Depois deste arquivo, rode o 02-funcoes.sql (funções do quiz e do painel).
