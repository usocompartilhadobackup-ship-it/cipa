# Protótipo Quiz CIPA Momesso na Vercel

Site estático (`index.html`) protegido por usuário e senha (`middleware.js`).
O navegador pede o login antes de mostrar qualquer coisa.

## Publicar pela linha de comando

Precisa do Node.js instalado. Dentro desta pasta:

```bash
npx vercel login
npx vercel link            # cria o projeto; aceite as opções sugeridas
npx vercel env add BASIC_AUTH_USER production
npx vercel env add BASIC_AUTH_PASSWORD production
npx vercel --prod
```

Nos dois `env add`, o terminal pede o valor: digite o usuário e depois a senha que você quer usar.

## Publicar pelo GitHub

1. Suba esta pasta para um repositório **privado** no GitHub.
2. Na Vercel: **Add New › Project**, importe o repositório e deixe o Framework como **Other**.
3. Antes de clicar em Deploy, abra **Environment Variables** e crie `BASIC_AUTH_USER` e `BASIC_AUTH_PASSWORD`.
4. Clique em **Deploy**.

## Trocar a senha

Em **Settings › Environment Variables**, altere `BASIC_AUTH_PASSWORD` e publique de novo
(`npx vercel --prod` ou **Redeploy** no painel). A senha nova só vale depois disso.

## Observações

- Sem as duas variáveis, o site responde "Site bloqueado". Ele nunca abre sem senha.
- Use usuário e senha sem acentos para evitar problemas em alguns navegadores.
- Este é o protótipo: nada fica salvo. Cada pessoa que abre vê a própria cópia, e tudo some ao recarregar.
