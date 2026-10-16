# Quiz da Segurança · CIPA Momesso

Contexto do projeto para o Claude Code. Leia inteiro antes de mexer em qualquer coisa.
Dono do projeto: **Emerson** (fala português; tem formação em desenvolvimento). Responda sempre em português do Brasil.

## O que é

Site em produção com duas partes:

- **Quiz** (`/`): o funcionário abre no celular, escolhe o próprio nome numa lista e responde 4 perguntas sobre as regras do estacionamento. Cada resposta é corrigida antes da próxima. Uma tentativa por pessoa. Quem acerta as 4 vê "PARABÉNS, VOCÊ ACERTOU TODAS AS PERGUNTAS! RETIRE SEU BRINDE COM O SETOR RESPONSÁVEL" e um comprovante com código de 6 caracteres.
- **Painel da CIPA** (`/painel`): Visão geral, Ranking, Entrega de brindes, Funcionários (inclui importação CSV), Setores e Configurações (exigir matrícula, link e QR Code).

Endereços de produção:

- Quiz: https://cipa-rosy.vercel.app/
- Painel: https://cipa-rosy.vercel.app/painel

**Quiz e painel não têm senha.** Foi decisão do Emerson. Não recoloque login sem ele pedir. O link do painel só deve ir para a CIPA.

## Integrações já feitas

### GitHub

- Repositório: `usocompartilhadobackup-ship-it/cipa`, branch `main`.
- Em 16/10/2026 o envio pela sessão anterior foi recusado (o app do Claude não estava instalado no GitHub). Por isso o remoto pode ainda ter a **versão antiga** (um `index.html` solto na raiz e um `middleware.js` com Basic Auth). Confira: se o `main` remoto não tem a pasta `api/`, este código precisa ser enviado.

### Vercel

- Time: `emerson10` (`team_rLkMg20Y8yoaNAmoOncoSmqc`). Usuário: `usocompartilhadobackup-5203`.
- Projeto: `cipa` (`prj_qUnmKGmF15bwen4i16u3lcdA0j4J`).
- Domínios: `cipa-rosy.vercel.app` (produção) e `cipa-emerson10.vercel.app`.
- Configuração: Framework **Other**, sem comando de build, Output Directory `public`. As funções em `api/` rodam em Node 24.x. `vercel.json` liga `cleanUrls` (então `/painel` serve `painel.html`) e cabeçalhos `noindex`.
- Variáveis de ambiente:
  - `DATABASE_URL` (Production, tipo **Sensitive**): conexão do Supabase pelo Transaction pooler. Valores Sensitive não podem ser lidos de volta; para trocar, crie de novo no painel da Vercel.
  - `BASIC_AUTH_USER` e `BASIC_AUTH_PASSWORD`: sobras do login antigo, **sem uso**. Podem ser apagadas.
- Proteção de deploy: Vercel Authentication no modo padrão. URLs de preview e de deploy pedem login da Vercel; o domínio de produção é público.
- Último deploy de produção conhecido: `dpl_6dXPhqAE118Zr6DsVwpZAeKfwjAy` (16/10/2026, enviado pela API, não pelo Git).
- Se o projeto estiver ligado ao repositório, todo push no `main` publica em produção.

### Supabase

- Projeto `quiz-cipa-momesso`, ref **`kdwbzlxorzbessofygcj`**, região `sa-east-1` (São Paulo), organização `vyovggkzfkdamitwldvp`, plano Free. No plano Free o projeto pode ser pausado depois de um tempo sem uso; reative pelo painel do Supabase.
- Tudo fica no schema **`quiz`**, que não é exposto pela API REST do Supabase (`anon` e `authenticated` não têm acesso). RLS está ligado e **sem políticas, de propósito**: só as funções da Vercel, com a conexão Postgres, acessam os dados.
- Migrations aplicadas: `quiz_cipa_tabelas`, `quiz_cipa_funcoes` e `quiz_cipa_regras_imutaveis`. Juntas equivalem a `supabase/01-banco.sql`.
- Conexão: **Transaction pooler, porta 6543** (Supabase → Connect → Transaction pooler). Usuário `postgres.kdwbzlxorzbessofygcj`. A senha não está em nenhum arquivo nem no histórico.

### Conectar o Claude Code nesta máquina

- O `.mcp.json` deste repositório já registra os servidores remotos da **Vercel** (`https://mcp.vercel.com`) e do **Supabase** (restrito ao projeto acima). Ao abrir o `claude`, aprove os dois e rode `/mcp` → **Authenticate** em cada um. Faça login com as contas do Emerson.
- GitHub: use o GitHub CLI (`gh auth login`) ou as credenciais do git desta máquina.
- Vercel CLI (opcional): `npm i -g vercel`, `vercel login` e depois `vercel link --yes --project cipa --scope emerson10`.

## Estrutura

```
api/quiz.js            API pública do quiz: ?acao=inicio (GET), iniciar, responder (POST)
api/admin.js           API do painel: ?acao=estado (GET), brinde, setor-salvar, setor-ativo,
                       setor-excluir, func-salvar, func-ativo, func-excluir, importar, config (POST)
lib/db.js              conexão postgres.js (prepare:false, max:1, ssl require) via DATABASE_URL ou POSTGRES_URL
lib/http.js            respostas JSON, leitura do corpo, mensagens de erro do banco em português
public/index.html      quiz (HTML + CSS + JS num arquivo só, mobile first)
public/painel.html     Painel da CIPA (HTML + CSS + JS num arquivo só; QR via qrcode-generator 1.4.4 no jsDelivr)
public/img/            logos da Momesso e da CIPA (PNG com fundo transparente)
public/robots.txt      bloqueia robôs (também bloqueia o WebFetch: teste com navegador ou curl)
supabase/01-banco.sql  banco completo, para recriar do zero num projeto novo
supabase/limpar-testes.sql  apaga só as respostas (uso único, antes de liberar o quiz)
ferramentas/servidor-local.mjs  simula a Vercel localmente (estáticos + as duas funções)
ferramentas/manual/    scripts que geram os manuais em PDF com prints reais (ver README de lá)
docs/                  Manual da CIPA e Guia do Funcionário em PDF
```

Funções Vercel no formato Web: `export default { async fetch(request) { ... } }`. Sem framework e sem etapa de build. Única dependência: `postgres@3.4.9`.

## Banco (schema `quiz`)

- Tabelas: `setores`, `funcionarios`, `perguntas`, `alternativas`, `tentativas`, `respostas`, `config` (linha única com `exigir_matricula`), `bloqueio_matricula`.
- Funções usadas pela API: `lista_publica()`, `perguntas_publicas()` (sem gabarito), `iniciar(funcionario, matricula, token_hash)`, `responder(tentativa, token_hash, pergunta, letra)`, `estado_painel()`, além de `resultado_json` e `gerar_codigo`.
- Gatilhos: `bloquear` impede DELETE e TRUNCATE em `tentativas` e `respostas` e UPDATE em `respostas`. `proteger_tentativa` só deixa concluir uma vez e registrar o brinde uma vez.
- Token por tentativa: a API gera um token aleatório, guarda só o sha256 e exige o token em cada resposta. Retomar gera um token novo e invalida o anterior.
- Matrícula: com `exigir_matricula` ligado, 5 erros seguidos bloqueiam aquele nome por 15 minutos.

## Regras que não podem ser quebradas

1. **Uma tentativa por funcionário e respostas imutáveis.** Não existe, e não deve existir, opção de liberar, refazer, resetar ou apagar respostas. O Emerson tirou isso de propósito para ninguém burlar. A exceção é o `limpar-testes.sql`, de uso único antes da divulgação.
2. O gabarito nunca vai para o navegador antes de a pessoa confirmar a resposta daquela pergunta.
3. **Nunca** coloque senha, string de conexão ou token em código, commit, log ou chat. Para rodar local, use variável de ambiente ou `.env.local` (já está no `.gitignore`).
4. Não apague nem altere dados de produção sem o Emerson confirmar explicitamente. Não rode `limpar-testes.sql` depois que o quiz começar de verdade.
5. Textos da interface em português do Brasil. Identidade visual: laranja Momesso (`#F07A1E`, botão `#D9640F`), verde da CIPA (`#23873A`), fontes Barlow e Barlow Condensed, faixa diagonal laranja e branca no topo, modo escuro pelo `prefers-color-scheme`.
6. Ao mudar `public/index.html` ou `public/painel.html`, mantenha os escapes `̀`, `﻿` e `�` como texto ASCII no código (algumas ferramentas trocam pelo caractere).

## Rodar localmente

Banco local de teste (recomendado para desenvolver):

```bash
npm install
createdb quiz_teste && psql -d quiz_teste -f supabase/01-banco.sql
DATABASE_URL=postgres://postgres@localhost:5432/quiz_teste DATABASE_SSL=off node ferramentas/servidor-local.mjs
# abra http://localhost:8787 (quiz) e http://localhost:8787/painel
```

Para apontar para o Supabase de verdade, defina `DATABASE_URL` com a string do Transaction pooler (sem `DATABASE_SSL=off`). Cuidado: aí os dados são os reais.

## Publicar

- Se o projeto da Vercel estiver ligado ao GitHub: commit e push no `main`.
- Pela CLI: `vercel deploy --prod` (depois do `vercel link`).
- Para conferir: `https://cipa-rosy.vercel.app/api/quiz?acao=inicio` deve devolver JSON com as 4 perguntas. Se aparecer "A conexão com o banco não está configurada", falta a `DATABASE_URL` na Vercel.

## Pendências (em 16/10/2026)

- [ ] Enviar este código para o GitHub (`main`).
- [ ] O Emerson está testando em produção. **Antes de divulgar**, rodar `supabase/limpar-testes.sql` no SQL Editor do Supabase (apaga só respostas; funcionários e setores ficam). Só com a confirmação dele.
- [ ] Cadastrar os setores e funcionários reais pelo painel (um por um ou CSV `nome;matricula;setor`).
- [ ] Opcional: apagar `BASIC_AUTH_USER` e `BASIC_AUTH_PASSWORD` da Vercel.

## Histórico de decisões

- Começou como um esboço HTML aprovado pelo Emerson. Virou Supabase + Vercel Functions sem framework (mais simples que o Next.js do plano inicial).
- O "liberar para responder de novo" foi trocado por um ranking (acertos, depois tempo).
- Houve um login com Basic Auth; foi removido a pedido. Quiz e painel ficaram abertos.
- Manuais em PDF gerados com prints reais e dados fictícios (pasta `docs/`).
