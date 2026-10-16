-- Dados fictícios só para os prints do manual (banco local de teste)
do $$
declare
  r record; fid uuid; sid uuid; t uuid; j jsonb; i int;
begin
  for r in select * from (values
    ('Ana Paula Ribeiro',      '1012', 'Produção',       'BBCB', '08:04', 72,  true),
    ('Carlos Eduardo Souza',   '1027', 'Produção',       'BBCA', '08:11', 80,  false),
    ('Juliana Martins',        '1033', 'Produção',       'BBBB', '08:26', 95,  false),
    ('Rafael Oliveira',        '1048', 'Produção',       null,   null,    null, false),
    ('Bruno Henrique Lima',    '2011', 'Expedição',      'BACB', '08:40', 101, false),
    ('Fernanda Costa',         '2019', 'Expedição',      'BBCB', '08:47', 85,  true),
    ('Diego Alves',            '2024', 'Expedição',      null,   null,    null, false),
    ('Marcos Vinícius Pereira','3005', 'Manutenção',     'BBCB', '09:02', 91,  false),
    ('Thiago Rocha',           '3014', 'Manutenção',     'BB',   '11:20', null, false),
    ('Patrícia Gomes',         '4002', 'Qualidade',      'BBCB', '09:15', 108, false),
    ('Larissa Fernandes',      '4009', 'Qualidade',      null,   null,    null, false),
    ('Renata Carvalho',        '5001', 'Administrativo', 'BBCB', '09:33', 125, false),
    ('Lucas Barbosa',          '5007', 'Administrativo', 'ABCC', '09:51', 77,  false),
    ('Camila Duarte',          '5012', 'Administrativo', null,   null,    null, false),
    ('Gustavo Teixeira',       '6003', 'Logística',      'CACB', '10:08', 66,  false),
    ('Aline Moreira',          '6010', 'Logística',      null,   null,    null, false)
  ) as v(nome, mat, setor, resp, hora, dur, entregue)
  loop
    select id into sid from quiz.setores where nome = r.setor;
    if sid is null then
      insert into quiz.setores (nome) values (r.setor) returning id into sid;
    end if;
    insert into quiz.funcionarios (nome, matricula, setor_id) values (r.nome, r.mat, sid) returning id into fid;
    if r.resp is not null then
      j := quiz.iniciar(fid, null, 'h' || r.mat)::jsonb;
      t := (j ->> 'tentativa')::uuid;
      for i in 1 .. length(r.resp) loop
        perform quiz.responder(t, 'h' || r.mat, 'q' || i, substr(r.resp, i, 1));
      end loop;
    end if;
  end loop;
end $$;

-- Ajusta horários para parecerem respostas reais da manhã de hoje
alter table quiz.tentativas disable trigger user;
alter table quiz.respostas disable trigger user;

with base as (
  select t.id, v.hora, v.dur, v.entregue
    from quiz.tentativas t
    join quiz.funcionarios f on f.id = t.funcionario_id
    join (values
      ('1012','08:04',72,true), ('1027','08:11',80,false), ('1033','08:26',95,false),
      ('2011','08:40',101,false), ('2019','08:47',85,true), ('3005','09:02',91,false),
      ('3014','11:20',null,false), ('4002','09:15',108,false), ('5001','09:33',125,false),
      ('5007','09:51',77,false), ('6003','10:08',66,false)
    ) as v(mat, hora, dur, entregue) on v.mat = f.matricula
)
update quiz.tentativas t
   set iniciada_em  = ('2026-10-16 ' || b.hora || ':00-03')::timestamptz,
       concluida_em = case when t.status = 'concluida'
                           then ('2026-10-16 ' || b.hora || ':00-03')::timestamptz + make_interval(secs => b.dur) end,
       brinde_em    = case when b.entregue then ('2026-10-16 ' || b.hora || ':00-03')::timestamptz + interval '2 hours 10 minutes' end,
       brinde_por   = case when b.entregue then 'CIPA' end
  from base b
 where b.id = t.id;

update quiz.respostas r
   set respondida_em = t.iniciada_em
       + make_interval(secs => coalesce(extract(epoch from (t.concluida_em - t.iniciada_em)), 80)
                               * (substr(r.pergunta_id, 2)::int) / 4.0)
  from quiz.tentativas t
 where t.id = r.tentativa_id;

alter table quiz.tentativas enable trigger user;
alter table quiz.respostas enable trigger user;

select f.nome, t.status, t.acertos, t.total, t.codigo, t.brinde_em is not null as entregue
  from quiz.tentativas t join quiz.funcionarios f on f.id = t.funcionario_id
 order by t.iniciada_em;
