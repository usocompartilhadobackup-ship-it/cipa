-- =====================================================================
-- ATENÇÃO: apaga TODAS as respostas do quiz e os participantes.
-- Use só uma vez, depois dos testes e ANTES de liberar o link para os
-- funcionários. Os setores continuam cadastrados.
-- Depois que o quiz começar de verdade, não rode este arquivo.
-- =====================================================================
begin;
alter table quiz.respostas  disable trigger user;
alter table quiz.tentativas disable trigger user;

delete from quiz.respostas;
delete from quiz.tentativas;
delete from quiz.funcionarios;

alter table quiz.respostas  enable trigger user;
alter table quiz.tentativas enable trigger user;
commit;
