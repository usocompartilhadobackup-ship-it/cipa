# Gerador dos manuais em PDF

Gera `Manual-Quiz-da-Seguranca-CIPA.pdf` e `Guia-do-Funcionario-Quiz-da-Seguranca.pdf` com prints reais
do site, usando um banco **local** com dados fictícios. Nada aqui toca no Supabase de produção.

## Requisitos

- PostgreSQL local (16+) com o usuário `postgres` e o `psql` no PATH
- Node 20+ e Python 3 com `playwright` e `pillow` (`pip install playwright pillow` e `playwright install chromium`)
- `pdftoppm` (poppler) só se quiser conferir as páginas em imagem

## Passo a passo (a partir da raiz do repositório)

```bash
# 1. dependências dos prints: fontes Barlow e biblioteca do QR Code
cd ferramentas/manual && mkdir -p deps && cd deps && npm init -y >/dev/null \
  && npm install qrcode-generator@1.4.4 @fontsource/barlow@5.0.13 @fontsource/barlow-condensed@5.0.13 && cd ../../..

# 2. banco local com dados fictícios (cria/zera o banco quiz_manual)
sh ferramentas/manual/resetar.sh

# 3. site local apontando para esse banco (deixe rodando em outro terminal)
npm install
DATABASE_URL=postgres://postgres@localhost:5432/quiz_manual DATABASE_SSL=off node ferramentas/servidor-local.mjs

# 4. prints e PDFs
cd ferramentas/manual
python3 prints.py "$PWD/prints" "$PWD/deps"
python3 gerar.py          # os PDFs saem em ferramentas/manual/saida/
```

Os prints abrem as páginas como se fossem `https://cipa-rosy.vercel.app` (para o link e o QR Code saírem
com o endereço oficial), mas tudo é atendido pelo servidor local.

Para rodar de novo do zero, repita o passo 2 antes do 4: o próprio roteiro responde o quiz por dois
funcionários fictícios, e cada pessoa só responde uma vez.

Os textos do manual ficam em `gerar.py`. As posições dos marcadores numerados são medidas
automaticamente em `prints.py` e gravadas em `prints/caixas.json`.
