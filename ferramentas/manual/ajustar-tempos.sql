-- Dá tempos realistas para quem respondeu pelo robô durante os prints
alter table quiz.tentativas disable trigger user;
alter table quiz.respostas disable trigger user;

with v(mat, hora, dur) as (values ('2024', '10:22', 88), ('1048', '10:35', 97))
update quiz.tentativas t
   set iniciada_em  = ('2026-10-16 ' || v.hora || ':00-03')::timestamptz,
       concluida_em = ('2026-10-16 ' || v.hora || ':00-03')::timestamptz + make_interval(secs => v.dur)
  from v join quiz.funcionarios f on f.matricula = v.mat
 where t.funcionario_id = f.id;

update quiz.respostas r
   set respondida_em = t.iniciada_em
       + make_interval(secs => extract(epoch from (t.concluida_em - t.iniciada_em)) * (substr(r.pergunta_id, 2)::int) / 4.0)
  from quiz.tentativas t join quiz.funcionarios f on f.id = t.funcionario_id
 where t.id = r.tentativa_id and f.matricula in ('2024', '1048');

alter table quiz.tentativas enable trigger user;
alter table quiz.respostas enable trigger user;
