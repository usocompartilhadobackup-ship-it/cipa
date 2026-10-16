"""Tira os prints do manual a partir da cópia local do site.

As páginas são abertas como se fossem https://cipa-rosy.vercel.app (o link e o QR Code saem
com o endereço oficial), mas tudo é atendido pelo servidor local com dados fictícios.
"""
import asyncio, os, sys, json
from playwright.async_api import async_playwright

LOCAL = "http://localhost:8787"
SITE = "https://cipa-rosy.vercel.app"
OUT = sys.argv[1]
DEPS = sys.argv[2]
os.makedirs(OUT, exist_ok=True)

FONTES = {
    "barlow-400": "@fontsource/barlow/files/barlow-latin-400-normal.woff2",
    "barlow-500": "@fontsource/barlow/files/barlow-latin-500-normal.woff2",
    "barlow-600": "@fontsource/barlow/files/barlow-latin-600-normal.woff2",
    "barlow-700": "@fontsource/barlow/files/barlow-latin-700-normal.woff2",
    "barlowc-600": "@fontsource/barlow-condensed/files/barlow-condensed-latin-600-normal.woff2",
    "barlowc-700": "@fontsource/barlow-condensed/files/barlow-condensed-latin-700-normal.woff2",
    "barlowc-800": "@fontsource/barlow-condensed/files/barlow-condensed-latin-800-normal.woff2",
}
CSS = ""
for chave in FONTES:
    familia = "Barlow Condensed" if chave.startswith("barlowc") else "Barlow"
    peso = chave.split("-")[1]
    CSS += f"@font-face{{font-family:'{familia}';font-style:normal;font-weight:{peso};font-display:block;src:url(https://fonts.gstatic.com/local/{chave}.woff2) format('woff2');}}\n"


async def rotas(ctx):
    async def tratar(route):
        u = route.request.url
        if u.startswith("https://fonts.googleapis.com/"):
            return await route.fulfill(body=CSS, content_type="text/css")
        if u.startswith("https://fonts.gstatic.com/local/"):
            chave = u.rsplit("/", 1)[1].replace(".woff2", "")
            return await route.fulfill(path=os.path.join(DEPS, "node_modules", FONTES[chave]), content_type="font/woff2")
        if "qrcode-generator" in u:
            return await route.fulfill(path=os.path.join(DEPS, "node_modules/qrcode-generator/qrcode.js"), content_type="text/javascript")
        if u.startswith(SITE):
            resp = await route.fetch(url=LOCAL + u[len(SITE):])
            return await route.fulfill(response=resp)
        return await route.abort()
    await ctx.route("**/*", tratar)


async def esperar_fontes(pg):
    await pg.evaluate("document.fonts.ready")
    await pg.wait_for_timeout(250)


async def foto(pg, nome, **kw):
    await esperar_fontes(pg)
    await pg.screenshot(path=os.path.join(OUT, nome), **kw)
    print("ok", nome)


CAIXAS = {}
JS_CAIXAS = """([sels, full]) => {
  const W = full ? document.documentElement.scrollWidth : innerWidth;
  const H = full ? document.documentElement.scrollHeight : innerHeight;
  const out = {};
  for (const [k, s] of Object.entries(sels)) {
    const el = document.querySelector(s);
    if (!el) { out[k] = null; continue; }
    const r = el.getBoundingClientRect();
    const dx = full ? scrollX : 0, dy = full ? scrollY : 0;
    out[k] = { x: (r.left + dx) / W, y: (r.top + dy) / H, w: r.width / W, h: r.height / H };
  }
  return out;
}"""


async def marcar(pg, nome, seletores, full=False):
    CAIXAS[nome] = await pg.evaluate(JS_CAIXAS, [seletores, full])
    faltando = [k for k, v in CAIXAS[nome].items() if v is None]
    if faltando:
        print("AVISO: sem elemento", nome, faltando)


async def api_admin(pg, acao, corpo):
    return await pg.evaluate(
        """async ([acao, corpo]) => (await fetch('/api/admin?acao=' + acao, {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(corpo)})).json()""",
        [acao, corpo])


async def responder(pg, letra, tirar=None, tirar_antes=None):
    await pg.click(f'label.opt[data-letra="{letra}"]')
    if tirar_antes:
        await pg.mouse.move(5, 5)
        await foto(pg, tirar_antes)
        await marcar(pg, tirar_antes, {"1": "label.opt.sel", "2": "#conf"})
    await pg.click("#conf")
    await pg.wait_for_selector(".retorno")
    if tirar:
        await foto(pg, tirar)
    await pg.click("#prox")


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--lang=pt-BR"])

        # ---------------- Quiz no celular ----------------
        cel = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                  is_mobile=True, has_touch=True, color_scheme="light", locale="pt-BR",
                                  timezone_id="America/Sao_Paulo")
        await rotas(cel)
        pg = await cel.new_page()
        await pg.goto(SITE + "/")
        await pg.wait_for_selector(".nome-btn")
        await foto(pg, "q-01-lista.png")
        await marcar(pg, "q-01-lista.png", {"1": "#busca", "2": ".nome-btn:not([disabled])", "3": ".chip.feito"})
        await foto(pg, "q-01-lista-inteira.png", full_page=True)

        await pg.fill("#busca", "diego")
        await pg.wait_for_timeout(150)
        await foto(pg, "q-02-busca.png")

        # Diego acerta tudo
        await pg.click('.nome-btn:has-text("Diego Alves")')
        await pg.wait_for_selector("label.opt")
        await pg.mouse.move(5, 5)
        await foto(pg, "q-03-pergunta.png")
        await responder(pg, "B", tirar="q-05-acerto.png", tirar_antes="q-04-selecionada.png")
        await pg.wait_for_selector('.contagem:has-text("Pergunta 2")')
        await responder(pg, "B")
        await pg.wait_for_selector('.contagem:has-text("Pergunta 3")')
        await responder(pg, "C")
        await pg.wait_for_selector('.contagem:has-text("Pergunta 4")')
        await pg.click('label.opt[data-letra="B"]')
        await pg.click("#conf")
        await pg.wait_for_selector(".retorno")
        await foto(pg, "q-06-ultima.png")
        await pg.click("#prox")
        await pg.wait_for_selector(".vitoria")
        await foto(pg, "q-07-parabens.png", full_page=True)
        await marcar(pg, "q-07-parabens.png", {"1": ".vitoria .retire", "2": ".comprovante .codigo"}, True)

        # Rafael erra duas
        await pg.click('[data-act="inicio"]')
        await pg.wait_for_selector(".nome-btn")
        await pg.click('.nome-btn:has-text("Rafael Oliveira")')
        await pg.wait_for_selector("label.opt")
        await responder(pg, "A", tirar="q-08-erro.png")
        await pg.wait_for_selector('.contagem:has-text("Pergunta 2")')
        await responder(pg, "B")
        await pg.wait_for_selector('.contagem:has-text("Pergunta 3")')
        await responder(pg, "C")
        await pg.wait_for_selector('.contagem:has-text("Pergunta 4")')
        await responder(pg, "A")
        await pg.wait_for_selector(".derrota")
        await foto(pg, "q-09-resultado.png", full_page=True)

        # Já respondeu (lista atualizada)
        await pg.click('[data-act="inicio"]')
        await pg.wait_for_selector(".nome-btn")
        await pg.fill("#busca", "a")
        await pg.fill("#busca", "")
        await foto(pg, "q-10-lista-depois.png")

        # Tela de matrícula (liga a opção, tira o print e desliga)
        await api_admin(pg, "config", {"exigirMatricula": True})
        await pg.reload()
        await pg.wait_for_selector(".nome-btn")
        await pg.click('.nome-btn:has-text("Larissa Fernandes")')
        await pg.wait_for_selector("#mat")
        await pg.fill("#mat", "4009")
        await foto(pg, "q-11-matricula.png")
        await api_admin(pg, "config", {"exigirMatricula": False})
        await cel.close()
        import subprocess
        subprocess.run(["psql", "-h", os.environ.get("PGHOST", "localhost"), "-p", os.environ.get("PGPORT", "5432"),
                        "-U", os.environ.get("PGUSER", "postgres"), "-d", os.environ.get("BANCO_MANUAL", "quiz_manual"), "-q",
                        "-v", "ON_ERROR_STOP=1", "-f", os.path.join(os.path.dirname(os.path.abspath(__file__)), "ajustar-tempos.sql")],
                       check=True)

        # ---------------- Painel no computador ----------------
        pc = await b.new_context(viewport={"width": 1280, "height": 820}, device_scale_factor=2,
                                 color_scheme="light", locale="pt-BR", timezone_id="America/Sao_Paulo")
        await rotas(pc)
        pg = await pc.new_page()
        await pg.goto(SITE + "/painel")
        await pg.wait_for_selector(".tiles")
        await foto(pg, "p-01-visao.png", full_page=True)
        await marcar(pg, "p-01-visao.png", {"1": ".nav-grupo", "2": ".tiles", "3": ".grid2 > section:nth-child(1)",
                                            "4": ".grid2 > section:nth-child(2)", "5": ".pilha > section.bloco",
                                            "6": "#atualizado"}, True)

        await pg.click('.nav-item[data-s="ranking"]')
        await pg.wait_for_selector("#rk-tabela table")
        await pg.click('tr[data-act="rk-abrir"]:has-text("Fernanda Costa")')
        await pg.wait_for_selector("tr.det")
        await pg.mouse.move(5, 5)
        await foto(pg, "p-02-ranking.png", full_page=True)
        await marcar(pg, "p-02-ranking.png", {"1": ".barra-ferr", "2": '[data-act="csv"]', "3": "tr.det",
                                              "4": "#rk-tabela .pill.warn", "5": ".nota-regra"}, True)

        await pg.click('.nav-item[data-s="brindes"]')
        await pg.wait_for_selector("#br-lista")
        await pg.click('.cartao:has-text("Marcos Vinícius") [data-act="br-registrar"]')
        await pg.wait_for_selector('[data-act="br-ok"]')
        await pg.mouse.move(5, 5)
        await foto(pg, "p-03-brindes.png", full_page=True)
        await marcar(pg, "p-03-brindes.png", {"1": "#br-busca", "2": ".cartao .codigo", "3": ".confirma",
                                              "4": ".cartao:not(.entregue):nth-child(2) [data-act=\"br-registrar\"]",
                                              "5": ".cartao.entregue .pill.ok"}, True)
        await pg.click('[data-act="br-cancelar"]')
        await pg.fill("#br-busca", "MT4")
        await pg.wait_for_timeout(150)
        await foto(pg, "p-04-brindes-busca.png")
        await pg.fill("#br-busca", "")

        await pg.click('.nav-item[data-s="funcionarios"]')
        await pg.wait_for_selector("#fn-tabela table")
        await pg.mouse.move(5, 5)
        await foto(pg, "p-05-funcionarios.png", full_page=True)
        await marcar(pg, "p-05-funcionarios.png", {"1": '[data-act="fn-novo"]', "2": '[data-act="fn-importar"]',
                                                   "3": ".barra-ferr",
                                                   "4": "#fn-tabela tbody tr:first-child td:nth-child(5) .pill",
                                                   "5": "#fn-tabela tbody tr:first-child .lk-acoes"}, True)
        await pg.click('[data-act="fn-novo"]')
        await pg.wait_for_selector("#form-fn")
        await pg.fill("#fn-nome", "Mariana Lopes")
        await pg.fill("#fn-mat", "1055")
        await pg.select_option("#fn-st", label="Produção")
        await pg.mouse.move(5, 5)
        await foto(pg, "p-06-func-novo.png")
        await pg.click('[data-act="fn-fechar"]')
        await pg.click('[data-act="fn-importar"]')
        await pg.wait_for_selector("#fn-csv")
        await pg.fill("#fn-csv", "nome;matricula;setor\nMariana Lopes;1055;Produção\nPaulo Henrique Dias;7002;Segurança Patrimonial\nJuliana Martins;1033;Produção")
        await pg.click('[data-act="fn-previa"]')
        await pg.wait_for_selector('[data-act="fn-importar-ok"]')
        # O Chromium de teste mostra o botão de arquivo em inglês; troca pela aparência em português
        await pg.evaluate("""() => {
          const i = document.querySelector('#fn-arquivo');
          const d = document.createElement('div');
          d.className = 'campo'; d.id = 'fn-arquivo-falso';
          d.style.cssText = 'display:flex;align-items:center;gap:8px;font:13.3px system-ui,Arial,sans-serif;color:#000';
          d.innerHTML = '<span style="border:1px solid #767676;border-radius:3px;background:#efefef;padding:1px 6px">Escolher arquivo</span><span>Nenhum arquivo escolhido</span>';
          i.style.display = 'none'; i.after(d);
        }""")
        await pg.mouse.move(5, 5)
        await foto(pg, "p-07-func-importar.png", full_page=True)
        await marcar(pg, "p-07-func-importar.png", {"1": "#fn-arquivo-falso", "2": "#fn-csv", "3": 'label.check:has(#fn-criar)',
                                                    "4": '[data-act="fn-previa"]', "5": ".form-painel .tabela",
                                                    "6": '[data-act="fn-importar-ok"]', "corte": ".form-painel"}, True)
        await pg.click('[data-act="fn-fechar"]')

        await pg.click('.nav-item[data-s="setores"]')
        await pg.wait_for_selector("#form-st")
        await pg.mouse.move(5, 5)
        await foto(pg, "p-08-setores.png", full_page=True)
        await marcar(pg, "p-08-setores.png", {"1": "#form-st", "2": "#bo-main tbody tr:first-child .lk-acoes"}, True)

        await pg.click('.nav-item[data-s="config"]')
        await pg.wait_for_selector("#qr canvas")
        await pg.mouse.move(5, 5)
        await foto(pg, "p-09-config.png", full_page=True)
        await marcar(pg, "p-09-config.png", {"1": ".switch", "2": ".link-box", "3": "#qr",
                                             "4": '[data-act="qr-baixar"]'}, True)

        # Painel no celular (só a visão geral, para mostrar o menu no topo)
        pcm = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                  is_mobile=True, has_touch=True, color_scheme="light", locale="pt-BR",
                                  timezone_id="America/Sao_Paulo")
        await rotas(pcm)
        pg2 = await pcm.new_page()
        await pg2.goto(SITE + "/painel")
        await pg2.wait_for_selector(".tiles")
        await foto(pg2, "p-10-painel-celular.png")
        await b.close()
        with open(os.path.join(OUT, "caixas.json"), "w", encoding="utf-8") as f:
            json.dump(CAIXAS, f, ensure_ascii=False, indent=1)


asyncio.run(main())
