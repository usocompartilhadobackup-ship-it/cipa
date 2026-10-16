# Quiz da Segurança CIPA Momesso

- **Quiz** (para os funcionários): `https://cipa-rosy.vercel.app/`
- **Painel da CIPA e Administração**: `https://cipa-rosy.vercel.app/painel`

O site é aberto, sem senha. Quem tiver o link do painel consegue cadastrar funcionários,
mudar configurações e registrar a entrega de brindes, então compartilhe o link do painel
só com quem cuida do quiz.

Tudo fica salvo no Supabase (projeto `quiz-cipa-momesso`). As regras importantes são
garantidas pelo próprio banco:

- cada funcionário responde uma única vez;
- respostas registradas não podem ser alteradas nem apagadas;
- a resposta certa só sai do banco depois que a pessoa responde.

## Estrutura

```
api/quiz.js        API do quiz (lista de nomes, iniciar, responder)
api/admin.js       API do painel (estado, cadastros, brindes, configuração)
lib/               conexão com o banco e utilidades
public/            páginas (index.html = quiz, painel.html = painel) e logos
supabase/          SQL do banco e script para limpar testes
```

## Ligação com o Supabase

A API lê a conexão da variável `DATABASE_URL` ou `POSTGRES_URL` (esta é criada
automaticamente quando o projeto do Supabase é conectado à Vercel pela integração).
Use sempre a conexão do **pooler em modo transação** (porta 6543).

## Antes de liberar para os funcionários

As respostas dos testes ficam gravadas e não dá para apagar pelo painel. Quando terminar
de testar, rode `supabase/limpar-testes.sql` no SQL Editor do Supabase. Ele apaga só as
respostas: funcionários e setores continuam. Depois que o quiz começar de verdade, não rode mais.

## Banco do zero

Se um dia precisar recriar o banco em outro projeto, rode `supabase/01-banco.sql` no
SQL Editor de um projeto novo.
