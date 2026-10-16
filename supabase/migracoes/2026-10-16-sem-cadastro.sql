-- =====================================================================
-- Migração de 16/10/2026: fim do cadastro prévio de funcionários.
-- Leva um banco criado pela versão anterior do 01-banco.sql ao modelo
-- novo. Depois dela, rode o 02-funcoes.sql.
--
-- Mantém setores, participantes, tentativas, respostas e brindes.
-- Remove só o que era da matrícula (coluna sempre vazia em produção,
-- configuração e contador de bloqueio) e a situação ativo/inativo do
-- funcionário, que deixa de existir. Cria o controle de login do painel.
-- =====================================================================
begin;

drop function if exists quiz.iniciar(uuid, text, text);
drop function if exists quiz.lista_publica();

drop table if exists quiz.bloqueio_matricula;
drop table if exists quiz.config;

alter table quiz.funcionarios
  drop constraint if exists funcionarios_matricula_unica,
  drop column if exists matricula,
  drop column if exists ativo,
  drop column if exists atualizado_em;

create or replace function quiz.chave_nome(p text) returns text
language sql immutable parallel safe as $$
  select lower(regexp_replace(btrim(translate(p,
    'ÁÀÂÃÄáàâãäÉÈÊËéèêëÍÌÎÏíìîïÓÒÔÕÖóòôõöÚÙÛÜúùûüÇçÑñ',
    'AAAAAaaaaaEEEEeeeeIIIIiiiiOOOOOoooooUUUUuuuuCcNn')), '\s+', ' ', 'g'));
$$;

alter table quiz.funcionarios
  add column nome_chave text generated always as (quiz.chave_nome(nome)) stored;
alter table quiz.funcionarios
  add constraint funcionarios_nome_setor_unico unique (setor_id, nome_chave);

-- Login do painel: 5 senhas erradas seguidas bloqueiam o endereço por 15 minutos
create table quiz.login_falhas (
  ip             text primary key,
  falhas         int not null default 0,
  bloqueado_ate  timestamptz
);
alter table quiz.login_falhas enable row level security;

commit;
