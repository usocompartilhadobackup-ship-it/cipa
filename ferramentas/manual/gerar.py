"""Gera o Manual da CIPA e o Guia do Funcionário em PDF (HTML impresso pelo Chromium)."""
import asyncio, json, os, sys
from PIL import Image
from playwright.async_api import async_playwright

BASE = os.path.dirname(os.path.abspath(__file__))
PRINTS = os.path.join(BASE, "prints")
IMG = os.path.join(BASE, "img")
DEPS = os.path.join(BASE, "deps", "node_modules")
LOGOS = os.path.join(BASE, "..", "..", "public", "img")
SAIDA = os.path.join(BASE, "saida")
os.makedirs(IMG, exist_ok=True)
os.makedirs(SAIDA, exist_ok=True)

CAIXAS = json.load(open(os.path.join(PRINTS, "caixas.json"), encoding="utf-8"))
LINK_QUIZ = "https://cipa-rosy.vercel.app/"
LINK_QUIZ_TXT = "cipa-rosy.vercel.app"
LINK_PAINEL_TXT = "cipa-rosy.vercel.app/painel"


# ---------------------------------------------------------------- imagens
def preparar(nome, corte=None, largura=None):
    """Recorta (frações de altura), reduz e salva PNG de 256 cores. Retorna (caminho, proporção, corte)."""
    im = Image.open(os.path.join(PRINTS, nome)).convert("RGB")
    topo, base = corte or (0, 1)
    im = im.crop((0, round(im.height * topo), im.width, round(im.height * base)))
    if largura and im.width > largura:
        im = im.resize((largura, round(im.height * largura / im.width)), Image.LANCZOS)
    destino = os.path.join(IMG, nome.replace(".png", f"-{int(topo*1000)}-{int(base*1000)}.png"))
    im.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(destino, optimize=True)
    return destino, im.height / im.width, (topo, base)


def marcadores(nome, corte, quais=None, modos=None):
    """Posição de cada marcador: canto (padrão), esq, dir ou cima do elemento."""
    caixas = CAIXAS.get(nome, {})
    topo, base = corte
    modos = modos or {}
    out = []
    for k, c in caixas.items():
        if not k.isdigit() or c is None or (quais and k not in quais):
            continue
        x, w = c["x"], c["w"]
        y, h = (c["y"] - topo) / (base - topo), c["h"] / (base - topo)
        modo = modos.get(k, "canto")
        if modo == "esq":
            out.append((k, x, y + h / 2, "translate(-118%, -50%)"))
        elif modo == "dir":
            out.append((k, x + w, y + h / 2, "translate(18%, -50%)"))
        elif modo == "fim":
            out.append((k, x + w, y + h / 2, "translate(-125%, -50%)"))
        elif modo == "cima":
            out.append((k, x + w / 2, y, "translate(-50%, -112%)"))
        else:
            out.append((k, max(x, 0.034), max(y, 0.03), ""))
    return out


def figura(nome, larg_mm, tipo="pc", corte=None, legenda=None, marcas=True, quais=None, px=None, classe="", modos=None):
    caminho, prop, corte = preparar(nome, corte, px or (1800 if tipo == "pc" else 780))
    pontos = marcadores(nome, corte, quais, modos) if marcas else []
    pins = "".join(f'<span class="pin" style="left:{x*100:.2f}%;top:{y*100:.2f}%{";transform:" + t if t else ""}">{k}</span>' for k, x, y, t in pontos)
    leg = f'<figcaption>{legenda}</figcaption>' if legenda else ""
    return (f'<figure class="fig {tipo} {classe}" style="width:{larg_mm}mm">'
            f'<div class="tela"><img src="file://{caminho}" alt="">{pins}</div>{leg}</figure>')


def lista_marcas(itens):
    return '<ol class="marcas">' + "".join(f'<li><span class="pin">{n}</span><div>{t}</div></li>' for n, t in itens) + "</ol>"


# ---------------------------------------------------------------- estilo
FONTES = "".join(
    f"@font-face{{font-family:'{fam}';font-weight:{peso};src:url(file://{DEPS}/@fontsource/{pasta}/files/{pasta}-latin-{peso}-normal.woff2) format('woff2');}}"
    for fam, pasta, pesos in [("Barlow", "barlow", (400, 500, 600, 700)), ("Barlow Condensed", "barlow-condensed", (600, 700, 800))]
    for peso in pesos)

CSS = FONTES + """
@page { size: A4; margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body { font-family: 'Barlow', sans-serif; color: #2B1E14; font-size: 10.6pt; line-height: 1.45; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.pg { width: 210mm; height: 297mm; position: relative; overflow: hidden; page-break-after: always; break-after: page; background: #fff; }
.pg:last-child { page-break-after: auto; break-after: auto; }
.faixa { position: absolute; top: 0; left: 0; right: 0; height: 4mm; background: repeating-linear-gradient(-45deg, #F07A1E 0 3mm, #fff 3mm 6mm); }
.conteudo { position: absolute; top: 13mm; left: 17mm; right: 17mm; bottom: 17mm; }
.rodape { position: absolute; left: 17mm; right: 17mm; bottom: 8mm; display: flex; justify-content: space-between; align-items: center; font-size: 8.5pt; color: #7A6455; border-top: 0.3mm solid #F1E2D4; padding-top: 2.5mm; }
.rodape b { color: #BF560A; font-weight: 700; }
.olho { font: 600 9pt/1.2 'Barlow', sans-serif; letter-spacing: .12em; text-transform: uppercase; color: #BF560A; margin: 0 0 1.5mm; }
h1 { font: 800 30pt/0.95 'Barlow Condensed', sans-serif; text-transform: uppercase; margin: 0 0 3mm; letter-spacing: .005em; }
h2 { font: 700 16pt/1.05 'Barlow Condensed', sans-serif; text-transform: uppercase; margin: 5mm 0 2mm; letter-spacing: .01em; }
h3 { font: 700 12.5pt/1.1 'Barlow Condensed', sans-serif; text-transform: uppercase; margin: 0 0 1.2mm; letter-spacing: .02em; }
p { margin: 0 0 2.4mm; }
.intro { font-size: 11.5pt; color: #4A3628; max-width: 160mm; margin-bottom: 4mm; }
.mut { color: #7A6455; }
strong { font-weight: 700; }
.fig { margin: 0; }
.tela { position: relative; line-height: 0; }
.fig img { width: 100%; display: block; }
.fig.pc .tela { border: 0.3mm solid #E4CDBA; border-radius: 2.5mm; overflow: visible; box-shadow: 0 1.5mm 4mm rgba(90,45,10,.13); }
.fig.pc img { border-radius: 2.2mm; }
.fig.cel .tela { border: 2.2mm solid #2B1E14; border-radius: 6mm; box-shadow: 0 1.5mm 4mm rgba(0,0,0,.18); background: #2B1E14; }
.fig.cel img { border-radius: 3.8mm; }
figcaption { font-size: 9pt; color: #7A6455; margin-top: 2.2mm; line-height: 1.35; }
figcaption b { color: #2B1E14; }
.pin { position: absolute; transform: translate(-78%, -78%); width: 5.4mm; height: 5.4mm; border-radius: 50%; background: #2B1E14; color: #fff; border: 0.6mm solid #fff; box-shadow: 0 0.4mm 1.2mm rgba(0,0,0,.35); font: 700 9.5pt/4.3mm 'Barlow Condensed', sans-serif; text-align: center; line-height: 4.25mm; z-index: 2; }
.fig.cel .pin { width: 5mm; height: 5mm; font-size: 9pt; line-height: 3.85mm; transform: translate(-70%, -70%); }
.marcas { list-style: none; padding: 0; margin: 4mm 0 0; display: grid; gap: 2.2mm; }
.marcas.duas { grid-template-columns: 1fr 1fr; column-gap: 7mm; }
.marcas li { display: flex; gap: 3mm; align-items: flex-start; }
.marcas .pin { position: static; transform: none; flex: none; margin-top: 0.3mm; width: 5.6mm; height: 5.6mm; line-height: 4.45mm; }
.marcas li div { min-width: 0; }
.linha { display: flex; gap: 6mm; align-items: flex-start; }
.linha.centro { justify-content: center; }
.passo { display: flex; flex-direction: column; gap: 3mm; }
.passo .num { display: inline-flex; align-items: center; gap: 2mm; font: 700 11pt/1 'Barlow Condensed', sans-serif; text-transform: uppercase; letter-spacing: .04em; color: #BF560A; }
.passo .num i { font-style: normal; width: 6.5mm; height: 6.5mm; border-radius: 50%; background: #D9640F; color: #fff; display: grid; place-items: center; font-size: 11pt; }
.passo .txt { font-size: 9.6pt; line-height: 1.4; }
.passo .txt h3 { font-size: 12pt; margin-bottom: 1mm; }
.caixa { background: #FFF6EE; border: 0.3mm solid #F6DCC4; border-radius: 3mm; padding: 4mm 5mm; }
.caixa.alerta { background: #FCEBE8; border-color: #F3C8C1; }
.caixa.ok { background: #E9F5EC; border-color: #C8E6CF; }
.caixa h3 { margin-bottom: 1.5mm; }
.caixa p:last-child, .caixa ul:last-child { margin-bottom: 0; }
ul.lista { margin: 0 0 2mm; padding-left: 5mm; }
ul.lista li { margin-bottom: 1.2mm; }
ol.passos { margin: 0; padding: 0; list-style: none; counter-reset: p; display: grid; gap: 2.4mm; }
ol.passos li { counter-increment: p; display: flex; gap: 3mm; align-items: flex-start; }
ol.passos li::before { content: counter(p); flex: none; width: 6mm; height: 6mm; border-radius: 50%; background: #D9640F; color: #fff; font: 700 10pt/6mm 'Barlow Condensed', sans-serif; text-align: center; margin-top: 0.1mm; }
.grade2 { display: grid; grid-template-columns: 1fr 1fr; gap: 5mm; }
.grade3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4mm; }
.regra { background: #FFF6EE; border-radius: 3mm; padding: 4mm; border: 0.3mm solid #F6DCC4; }
.regra .grande { font: 800 24pt/1 'Barlow Condensed', sans-serif; color: #D9640F; display: block; margin-bottom: 1.5mm; }
.regra .t { font-weight: 700; display: block; margin-bottom: 0.8mm; }
.regra .d { font-size: 9.2pt; color: #6B5545; }
table.quem { width: 100%; border-collapse: collapse; font-size: 9.8pt; }
table.quem th { text-align: left; font: 600 8.5pt/1.2 'Barlow', sans-serif; letter-spacing: .08em; text-transform: uppercase; color: #7A6455; background: #FBF2E9; padding: 2.5mm 3mm; }
table.quem td { padding: 2.8mm 3mm; border-top: 0.3mm solid #F1E2D4; vertical-align: top; }
table.quem td:first-child { font-weight: 700; }
.url { font-family: 'Barlow', sans-serif; font-weight: 700; color: #BF560A; }
.sumario { list-style: none; padding: 0; margin: 0; display: grid; gap: 1.6mm; }
.sumario li { display: flex; align-items: baseline; gap: 2mm; }
.sumario li .pt { flex: 1; border-bottom: 0.35mm dotted #D9C3AE; transform: translateY(-1mm); }
.sumario li.parte { font: 700 11.5pt/1.2 'Barlow Condensed', sans-serif; text-transform: uppercase; letter-spacing: .03em; color: #BF560A; margin-top: 1.8mm; }
.sumario li.parte .pt { border: 0; }
.faq { display: grid; gap: 3.2mm; }
.faq div h3 { font-size: 11.5pt; margin-bottom: 0.8mm; }
.faq div p { font-size: 9.8pt; margin: 0; }
.tag { display: inline-block; font-size: 8pt; font-weight: 700; padding: 0.6mm 2.4mm; border-radius: 99mm; vertical-align: 0.3mm; }
.tag.ok { background: #E6F4E9; color: #23873A; }
.tag.warn { background: #FFEEDF; color: #BF560A; }
.tag.neutro { background: #F1E2D4; color: #7A6455; }
.capa { background: #FFF8F2; }
.capa .faixa { height: 9mm; background: repeating-linear-gradient(-45deg, #F07A1E 0 6mm, #FFF8F2 6mm 12mm); }
.capa .logos { position: absolute; top: 22mm; left: 18mm; right: 18mm; display: flex; justify-content: space-between; align-items: center; }
.capa .logos img.m { height: 11mm; }
.capa .logos img.c { height: 22mm; }
.capa .titulo { position: absolute; top: 62mm; left: 18mm; width: 104mm; }
.capa .titulo h1 { font-size: 50pt; line-height: .9; margin-bottom: 6mm; }
.capa .titulo .sub { font-size: 13pt; color: #4A3628; line-height: 1.4; }
.capa .celular { position: absolute; top: 58mm; right: 18mm; width: 64mm; transform: rotate(3deg); }
.capa .acessos { position: absolute; left: 18mm; right: 18mm; bottom: 34mm; display: grid; grid-template-columns: 1fr 1fr; gap: 5mm; }
.capa .acessos > div { background: #fff; border: 0.3mm solid #F1E2D4; border-radius: 3.5mm; padding: 5mm 6mm; }
.capa .acessos .rot { font: 600 8.5pt/1.2 'Barlow', sans-serif; letter-spacing: .1em; text-transform: uppercase; color: #7A6455; margin-bottom: 1.5mm; }
.capa .acessos .url { font-size: 14pt; display: block; margin-bottom: 1.2mm; }
.capa .acessos .d { font-size: 9.5pt; color: #6B5545; }
.capa .data { position: absolute; left: 18mm; right: 18mm; bottom: 14mm; display: flex; justify-content: space-between; font-size: 9.5pt; color: #7A6455; }
.secao-capa { background: #D9640F; color: #fff; }
.secao-capa .faixa { height: 9mm; background: repeating-linear-gradient(-45deg, #fff 0 6mm, #D9640F 6mm 12mm); opacity: .9; }
.secao-capa .bloco { position: absolute; left: 18mm; right: 18mm; top: 92mm; }
.secao-capa .olho { color: #FFE2C8; font-size: 11pt; }
.secao-capa h1 { font-size: 54pt; color: #fff; margin-bottom: 6mm; }
.secao-capa p { font-size: 13pt; max-width: 140mm; color: #FFF3E8; }
.secao-capa .itens { margin-top: 10mm; display: flex; flex-wrap: wrap; gap: 3mm; }
.secao-capa .itens span { border: 0.4mm solid rgba(255,255,255,.65); border-radius: 99mm; padding: 1.6mm 4.5mm; font-weight: 600; font-size: 10.5pt; }
.qr { width: 32mm; height: 32mm; background: #fff; padding: 2mm; border-radius: 2mm; border: 0.3mm solid #E4CDBA; }
.qr svg { width: 100%; height: 100%; display: block; }
"""


def pagina(conteudo, n, titulo_rodape, classe=""):
    rod = f'<div class="rodape"><span><b>CIPA Momesso</b> · {titulo_rodape}</span><span>{n}</span></div>' if n else ""
    return f'<section class="pg {classe}"><div class="faixa"></div><div class="conteudo">{conteudo}</div>{rod}</section>'


def documento(titulo, paginas):
    return (f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>{titulo}</title>'
            f'<style>{CSS}</style><script src="file://{DEPS}/qrcode-generator/qrcode.js"></script></head><body>'
            + "".join(paginas) +
            """<script>document.querySelectorAll('.qr[data-link]').forEach(function(el){var q=qrcode(0,'M');q.addData(el.dataset.link);q.make();el.innerHTML=q.createSvgTag({scalable:true,margin:0});});</script>"""
            "</body></html>")


LOGO_M = f"file://{LOGOS}/logo-momesso.png"
LOGO_C = f"file://{LOGOS}/logo-cipa.png"


# ---------------------------------------------------------------- blocos de conteúdo (quiz)
def passo(num, titulo, texto, fig):
    return (f'<div class="passo"><span class="num"><i>{num}</i>{"Passo " + str(num)}</span>'
            f'<div class="txt"><h3>{titulo}</h3>{texto}</div>{fig}</div>')


LARG_CEL = 51


def paginas_quiz(rodape, n0, para_funcionario):
    voce = para_funcionario
    p1 = (
        '<p class="olho">' + ("Guia do funcionário" if voce else "Parte 1 · O quiz") + '</p>'
        '<h1>' + ("Como responder o quiz" if voce else "Como o funcionário responde") + '</h1>'
        '<p class="intro">' + (
            "O quiz tem 4 perguntas sobre as regras de circulação no estacionamento da empresa. Funciona no celular, sem senha e sem instalar nada. Você responde uma única vez."
            if voce else
            "O funcionário abre o link do quiz no celular, sem senha e sem instalar nada. São 4 perguntas sobre as regras do estacionamento, com uma única tentativa por pessoa. Esta é a tela que ele vê, passo a passo."
        ) + '</p>'
        '<div class="linha">'
        + passo(1, "Escolha seu nome",
                "<p>Digite parte do nome ou do setor na busca e toque no seu nome. Quem já respondeu aparece com a etiqueta <span class='tag neutro'>Já respondeu</span> e não pode ser escolhido de novo.</p>",
                figura("q-01-lista.png", LARG_CEL, "cel", modos={"1": "esq", "2": "esq", "3": "cima"}, legenda="<b>1</b> Busca &nbsp;·&nbsp; <b>2</b> Nome disponível &nbsp;·&nbsp; <b>3</b> Já respondeu"))
        + passo(2, "Marque e confirme",
                "<p>Leia a pergunta, toque na alternativa e depois em <b>Confirmar resposta</b>. Depois de confirmar, não dá para trocar.</p>",
                figura("q-04-selecionada.png", LARG_CEL, "cel", modos={"1": "esq", "2": "esq"}, legenda="<b>1</b> Alternativa marcada &nbsp;·&nbsp; <b>2</b> Confirmar"))
        + passo(3, "Veja se acertou",
                "<p>A resposta é conferida na hora. Em verde, a certa; em vermelho, a que foi marcada errada. Toque em <b>Próxima pergunta</b> para seguir.</p>",
                figura("q-05-acerto.png", LARG_CEL, "cel", legenda="Resposta certa, com a explicação da regra"))
        + '</div>'
    )
    p2 = (
        '<div class="linha">'
        + passo(3, "Quando erra",
                "<p>Se a resposta estiver errada, o quiz mostra qual era a certa e segue para a próxima pergunta. Não dá para responder de novo.</p>",
                figura("q-08-erro.png", LARG_CEL, "cel", legenda="Resposta incorreta, com a certa em verde"))
        + passo(4, "Acertou todas: brinde",
                "<p>Quem acerta as 4 vê a tela de <b>Parabéns</b> com um comprovante e um <b>código</b>. É essa tela que deve ser mostrada na hora de retirar o brinde.</p>",
                figura("q-07-parabens.png", LARG_CEL, "cel", modos={"1": "esq", "2": "esq"}, legenda="<b>1</b> Aviso do brinde &nbsp;·&nbsp; <b>2</b> Código do comprovante"))
        + passo(4, "Não acertou todas",
                "<p>Quem erra alguma vê quantas acertou e a lista com as respostas certas. A participação fica registrada, mas sem brinde.</p>",
                figura("q-09-resultado.png", LARG_CEL, "cel", corte=(0, 0.83), legenda="Resultado com a revisão das respostas"))
        + '</div>'
        + '<div class="caixa" style="margin-top:6mm"><h3>' + ("Na hora de retirar o brinde" if voce else "Comprovante do brinde") + '</h3><p>'
        + ("Mostre a tela de Parabéns (ou um print dela) para um membro da CIPA. Eles conferem o seu nome e o código antes de entregar."
           if voce else
           "O código do comprovante é único para cada pessoa. A CIPA confere esse código na aba <b>Entrega de brindes</b> do painel antes de entregar (veja a página da aba).")
        + '</p></div>'
    )
    dicas_func = (
        '<div class="faq">'
        '<div><h3>Fechei o navegador no meio do quiz</h3><p>Abra o link de novo e toque no seu nome: ele aparece como <span class="tag warn">Continuar</span> e você segue de onde parou. As respostas que já deu não mudam.</p></div>'
        '<div><h3>Comecei em um celular e quero terminar em outro</h3><p>Pode. Escolha seu nome no outro celular e continue. O primeiro aparelho deixa de valer.</p></div>'
        '<div><h3>Não encontrei meu nome</h3><p>Fale com um membro da CIPA. Só aparecem na lista as pessoas cadastradas por eles.</p></div>'
        '<div><h3>O quiz pediu minha matrícula</h3><p>A CIPA pode ligar essa confirmação. Digite sua matrícula e toque em <b>Começar o quiz</b>. Depois de 5 tentativas erradas, o nome fica bloqueado por 15 minutos.</p></div>'
        '<div><h3>Errei uma pergunta. Posso fazer de novo?</h3><p>Não. Cada pessoa responde uma única vez, e as respostas ficam registradas.</p></div>'
        '</div>'
    )
    p3 = (
        '<p class="olho">' + ("Guia do funcionário" if voce else "Parte 1 · O quiz") + '</p>'
        '<h2 style="margin-top:0">Outras telas que podem aparecer</h2>'
        '<div class="linha" style="margin-top:3mm">'
        + figura("q-11-matricula.png", LARG_CEL, "cel", corte=(0, 0.64),
                 legenda="<b>Confirmação de matrícula</b>, só quando a CIPA liga essa opção")
        + figura("q-10-lista-depois.png", LARG_CEL, "cel", corte=(0, 0.82),
                 legenda="<b>Já respondeu</b>: o nome fica bloqueado e não abre mais o quiz")
        + figura("q-02-busca.png", LARG_CEL, "cel", corte=(0, 0.64),
                 legenda="<b>Busca</b>: digite parte do nome ou do setor")
        + '</div>'
        '<h2>Dúvidas comuns</h2>' + dicas_func
    )
    paginas = [pagina(p1, n0, rodape), pagina(p2, n0 + 1, rodape), pagina(p3, n0 + 2, rodape)]
    return paginas


# ---------------------------------------------------------------- Manual da CIPA
def manual_cipa():
    R = "Manual do Quiz da Segurança"
    pgs = []

    # Capa
    capa = (
        f'<div class="logos"><img class="m" src="{LOGO_M}"><img class="c" src="{LOGO_C}"></div>'
        '<div class="titulo"><p class="olho">CIPA Momesso · Uso interno</p>'
        '<h1>Manual do Quiz da Segurança</h1>'
        '<p class="sub">Como funciona o quiz dos funcionários e cada aba do Painel da CIPA: acompanhamento, ranking, entrega de brindes e cadastros.</p></div>'
        + f'<div class="celular">{figura("q-01-lista.png", 64, "cel", marcas=False)}</div>'
        '<div class="acessos">'
        f'<div><div class="rot">Quiz · para os funcionários</div><span class="url">{LINK_QUIZ_TXT}</span><div class="d">Pode divulgar para todos. Funciona no celular, sem senha.</div></div>'
        f'<div><div class="rot">Painel da CIPA · só para a comissão</div><span class="url">{LINK_PAINEL_TXT}</span><div class="d">Não tem senha: compartilhe só com quem cuida do quiz.</div></div>'
        '</div>'
        '<div class="data"><span>Quiz da Segurança · regras do estacionamento</span><span>Outubro de 2026</span></div>'
    )
    pgs.append(f'<section class="pg capa"><div class="faixa"></div>{capa}</section>')

    # Antes de começar
    sumario = [
        ("Início", 0, True),
        ("Antes de começar", 2, False),
        ("Parte 1 · O quiz do funcionário", 3, True),
        ("Como o funcionário responde", 4, False), ("Resultado e comprovante", 5, False), ("Outras telas e dúvidas", 6, False),
        ("Parte 2 · O Painel da CIPA", 7, True),
        ("Como o painel é organizado", 8, False), ("Visão geral", 9, False), ("Ranking", 10, False),
        ("Entrega de brindes", 11, False), ("Funcionários", 12, False), ("Cadastrar e importar funcionários", 13, False),
        ("Setores", 14, False), ("Configurações", 15, False), ("Antes de divulgar e dúvidas comuns", 16, False),
    ]
    def col(itens):
        return '<ol class="sumario">' + "".join(
            f'<li class="{"parte" if parte else ""}"><span>{t}</span><span class="pt"></span><span>{"" if parte else n}</span></li>'
            for t, n, parte in itens) + "</ol>"
    sum_html = f'<div class="grade2" style="gap:9mm">{col(sumario[:6])}{col(sumario[6:])}</div>'
    antes = (
        '<p class="olho">Visão rápida</p><h1>Antes de começar</h1>'
        '<p class="intro">O sistema tem duas partes: o <b>quiz</b>, que os funcionários respondem pelo celular, e o <b>Painel da CIPA</b>, onde a comissão acompanha os resultados, entrega os brindes e cuida dos cadastros. Tudo fica salvo automaticamente.</p>'
        '<div class="grade3" style="grid-template-columns:repeat(4,1fr);gap:3.5mm">'
        '<div class="regra"><span class="grande">4</span><span class="t">perguntas</span><span class="d">Sobre as regras de circulação no estacionamento.</span></div>'
        '<div class="regra"><span class="grande">1</span><span class="t">tentativa</span><span class="d">Cada pessoa responde uma única vez. Não há como liberar de novo.</span></div>'
        '<div class="regra"><span class="grande">Na hora</span><span class="t">correção</span><span class="d">Cada resposta é conferida antes de passar para a próxima.</span></div>'
        '<div class="regra"><span class="grande">4 de 4</span><span class="t">ganha brinde</span><span class="d">Quem acerta todas recebe um comprovante com código.</span></div>'
        '</div>'
        '<h2>Quem usa o quê</h2>'
        '<table class="quem"><thead><tr><th style="width:24%">Quem</th><th style="width:36%">Endereço</th><th>Para quê</th></tr></thead><tbody>'
        f'<tr><td>Funcionários</td><td><span class="url">{LINK_QUIZ_TXT}</span></td><td>Responder o quiz no celular. Sem senha.</td></tr>'
        f'<tr><td>Membros da CIPA</td><td><span class="url">{LINK_PAINEL_TXT}</span></td><td>Acompanhar resultados, entregar brindes, cadastrar funcionários e setores. Funciona no computador e no celular.</td></tr>'
        '</tbody></table>'
        '<div class="caixa alerta" style="margin-top:5mm"><h3>Atenção: o painel não tem senha</h3>'
        '<p>Quem tiver o link do painel consegue cadastrar e excluir funcionários, mudar as configurações e registrar brindes. Envie esse link <b>só para os membros da CIPA</b>. Para os funcionários, use o <b>Guia do Funcionário</b>, que traz apenas o link do quiz.</p></div>'
        '<h2>Sumário</h2>' + sum_html
    )
    pgs.append(pagina(antes, 2, R))

    # Parte 1
    pgs.append(
        '<section class="pg secao-capa"><div class="faixa"></div><div class="bloco"><p class="olho">Parte 1</p>'
        '<h1>O quiz do funcionário</h1><p>O que o funcionário vê no celular, do momento em que escolhe o nome até a tela do brinde.</p>'
        '<div class="itens"><span>Escolher o nome</span><span>Responder</span><span>Resultado</span><span>Comprovante</span></div></div></section>')
    pgs += paginas_quiz(R, 4, False)

    # Parte 2
    pgs.append(
        '<section class="pg secao-capa"><div class="faixa"></div><div class="bloco"><p class="olho">Parte 2</p>'
        '<h1>O Painel da CIPA</h1><p>Onde a comissão acompanha a participação, confere o ranking, entrega os brindes e mantém os cadastros em dia.</p>'
        '<div class="itens"><span>Visão geral</span><span>Ranking</span><span>Entrega de brindes</span><span>Funcionários</span><span>Setores</span><span>Configurações</span></div></div></section>')

    # Organização do painel
    org = (
        '<p class="olho">Parte 2 · Painel da CIPA</p><h1>Como o painel é organizado</h1>'
        f'<p class="intro">Abra <span class="url">{LINK_PAINEL_TXT}</span> no computador ou no celular. Não pede senha. O menu fica à esquerda no computador e no topo da tela no celular.</p>'
        '<div class="linha">'
        '<div style="flex:1">'
        '<h2 style="margin-top:0">As abas</h2>'
        '<table class="quem"><thead><tr><th style="width:38%">Aba</th><th>Para que serve</th></tr></thead><tbody>'
        '<tr><td colspan="2" style="font:700 9pt/1 Barlow;letter-spacing:.1em;text-transform:uppercase;color:#BF560A;padding-top:3.5mm">Painel da CIPA</td></tr>'
        '<tr><td>Visão geral</td><td>Números do quiz, top 5, acerto por pergunta e participação por setor.</td></tr>'
        '<tr><td>Ranking</td><td>Todos que já responderam, com acertos, tempo e respostas de cada um.</td></tr>'
        '<tr><td>Entrega de brindes</td><td>Conferir o código e registrar quem já retirou o brinde.</td></tr>'
        '<tr><td colspan="2" style="font:700 9pt/1 Barlow;letter-spacing:.1em;text-transform:uppercase;color:#BF560A;padding-top:3.5mm">Administração</td></tr>'
        '<tr><td>Funcionários</td><td>Cadastrar, editar, inativar e importar funcionários por planilha.</td></tr>'
        '<tr><td>Setores</td><td>Criar, renomear e inativar setores.</td></tr>'
        '<tr><td>Configurações</td><td>Exigir matrícula, copiar o link do quiz e baixar o QR Code.</td></tr>'
        '</tbody></table>'
        '<div class="caixa" style="margin-top:5mm"><h3>Os números se atualizam sozinhos</h3>'
        '<p>Nas abas Visão geral, Ranking e Entrega de brindes, o painel busca os dados novos a cada 20 segundos. O horário da última atualização aparece no canto da tela. O número laranja ao lado de <b>Entrega de brindes</b> mostra quantos brindes ainda faltam entregar.</p></div>'
        '</div>'
        + figura("p-10-painel-celular.png", 52, "cel", corte=(0, 0.78), legenda="O painel no celular: o menu vira uma faixa no topo, que você arrasta para o lado")
        + '</div>'
    )
    pgs.append(pagina(org, 8, R))

    # Visão geral
    visao = (
        '<p class="olho">Painel da CIPA · Aba 1</p><h1>Visão geral</h1>'
        '<p class="intro">É a primeira tela do painel. Mostra, em um só lugar, como o quiz está indo.</p>'
        + figura("p-01-visao.png", 172, "pc", corte=(0, 0.965), modos={"1": "fim", "6": "esq"})
        + lista_marcas([
            ("1", "<b>Menu</b>: troca de aba. O número laranja mostra os brindes que faltam entregar."),
            ("2", "<b>Números do quiz</b>: ativos, quantos responderam, quantos acertaram todas, brindes entregues e quem começou e não terminou."),
            ("3", "<b>Top 5 do ranking</b>: os melhores colocados. <b>Ver ranking completo</b> abre a aba Ranking."),
            ("4", "<b>Acerto por pergunta</b>: porcentagem de acerto de cada regra e quantos marcaram cada alternativa. Mostra o que a equipe conhece menos."),
            ("5", "<b>Participação por setor</b>: quantos responderam em cada setor, a porcentagem e a média de acertos."),
            ("6", "<b>Atualizado às</b>: horário da última atualização automática."),
        ]).replace('class="marcas"', 'class="marcas duas"')
    )
    pgs.append(pagina(visao, 9, R))

    # Ranking
    ranking = (
        '<p class="olho">Painel da CIPA · Aba 2</p><h1>Ranking</h1>'
        '<p class="intro">Lista todos que já terminaram o quiz, do maior para o menor número de acertos. Em caso de empate, fica na frente quem respondeu mais rápido.</p>'
        + figura("p-02-ranking.png", 172, "pc", corte=(0, 0.965), modos={"2": "cima", "4": "dir", "5": "esq"})
        + lista_marcas([
            ("1", "<b>Busca e filtros</b>: procure pelo nome, filtre por setor ou marque <b>Só quem acertou todas</b>."),
            ("2", "<b>Exportar CSV</b>: baixa o ranking para abrir no Excel, com código e data de entrega do brinde."),
            ("3", "<b>Respostas da pessoa</b>: clique numa linha para ver o que ela marcou em cada pergunta, o horário e o código do comprovante. Clique de novo para fechar."),
            ("4", "<b>Brinde</b>: <span class='tag warn'>A entregar</span> ou <span class='tag ok'>Entregue</span>. Quem não acertou todas aparece com um traço."),
            ("5", "As respostas registradas <b>não podem ser alteradas, apagadas nem liberadas</b> para responder de novo."),
        ]).replace('class="marcas"', 'class="marcas duas"')
        + '<p class="mut" style="margin-top:3mm;font-size:9.4pt"><b>Tempo</b> é o intervalo entre escolher o nome e confirmar a última resposta.</p>'
    )
    pgs.append(pagina(ranking, 10, R))

    # Brindes
    brindes = (
        '<p class="olho">Painel da CIPA · Aba 3</p><h1>Entrega de brindes</h1>'
        '<p class="intro">Aqui ficam todos que acertaram as 4 perguntas. Use esta aba no momento de entregar o brinde, para não entregar duas vezes nem para quem não tem direito.</p>'
        + figura("p-03-brindes.png", 176, "pc", corte=(0, 0.93), modos={"3": "cima", "4": "dir", "5": "cima"})
        + '<div class="grade2" style="margin-top:5mm;grid-template-columns:1.05fr 1fr">'
        '<div><h3>Passo a passo da entrega</h3><ol class="passos">'
        '<li><div>Peça para a pessoa mostrar no celular a tela de <b>Parabéns</b> com o código.</div></li>'
        '<li><div>Digite o código (ou o nome) na busca <b>(1)</b>. Só aparece quem combina.</div></li>'
        '<li><div>Confira se o nome e o código <b>(2)</b> batem com a tela do celular.</div></li>'
        '<li><div>Clique em <b>Registrar entrega</b> <b>(4)</b> e depois em <b>Confirmar entrega</b> <b>(3)</b>.</div></li>'
        '<li><div>Pronto: a pessoa passa para <b>Já entregues</b> <b>(5)</b>, com data, hora e "por CIPA".</div></li>'
        '</ol></div>'
        '<div class="caixa alerta" style="align-self:start"><h3>Confira antes de confirmar</h3>'
        '<p>A entrega registrada <b>não pode ser desfeita</b> pelo painel. Se clicar em Registrar por engano, use <b>Cancelar</b> antes de confirmar.</p>'
        '<p>Se você buscar o nome de alguém que errou alguma pergunta, ele aparece em <b>Sem direito a brinde</b>, com quantas acertou.</p></div>'
        '</div>'
    )
    pgs.append(pagina(brindes, 11, R))

    # Funcionários
    func = (
        '<p class="olho">Administração · Aba 4</p><h1>Funcionários</h1>'
        '<p class="intro">A lista de quem pode responder o quiz. <b>Só os funcionários ativos aparecem no quiz.</b> Cada linha mostra também a situação da pessoa no quiz.</p>'
        + figura("p-05-funcionarios.png", 176, "pc", corte=(0, 0.66), modos={"1": "cima", "2": "cima", "4": "esq", "5": "esq"})
        + lista_marcas([
            ("1", "<b>Novo funcionário</b>: abre o formulário de cadastro (próxima página)."),
            ("2", "<b>Importar CSV</b>: cadastra muitos de uma vez a partir de uma planilha (próxima página)."),
            ("3", "<b>Busca e filtros</b>: por nome, matrícula, setor e situação (ativos ou inativos)."),
            ("4", "<b>Quiz</b>: <span class='tag neutro'>Não respondeu</span>, <span class='tag warn'>Em andamento</span> ou quantas acertou, como <span class='tag ok'>4 de 4</span>."),
            ("5", "<b>Ações</b>: <b>Editar</b> nome, matrícula, setor e situação; <b>Inativar</b> tira a pessoa da lista do quiz; <b>Excluir</b> só aparece para quem ainda não respondeu."),
        ]).replace('class="marcas"', 'class="marcas duas"')
        + '<div class="caixa" style="margin-top:4mm"><h3>Inativar ou excluir?</h3><p>Quem já respondeu o quiz não pode ser excluído, para não sumir do ranking: aparece "Não exclui". Se a pessoa saiu da empresa, use <b>Inativar</b>. Ela sai da lista do quiz e continua no ranking com o nome e o setor da época em que respondeu.</p></div>'
    )
    pgs.append(pagina(func, 12, R))

    # Cadastrar / importar
    cad = (
        '<p class="olho">Administração · Aba 4</p><h1>Cadastrar e importar</h1>'
        '<div class="grade2" style="grid-template-columns:1fr 1fr;gap:7mm;align-items:start">'
        '<div><h2 style="margin-top:0">Um por um</h2><ol class="passos">'
        '<li><div>Clique em <b>Novo funcionário</b>.</div></li>'
        '<li><div>Preencha o <b>nome completo</b>, a <b>matrícula</b> (só números, opcional) e escolha o <b>setor</b>.</div></li>'
        '<li><div>Deixe <b>Ativo</b> marcado para a pessoa aparecer no quiz e clique em <b>Cadastrar funcionário</b>.</div></li>'
        '</ol><p class="mut" style="font-size:9.3pt;margin-top:2.5mm">A matrícula é obrigatória só se a opção "Exigir matrícula" estiver ligada em Configurações. O setor precisa existir antes (aba Setores).</p></div>'
        '<div><h2 style="margin-top:0">Vários de uma vez (planilha)</h2><ol class="passos">'
        '<li><div>No Excel, monte três colunas: <b>nome</b>, <b>matricula</b> e <b>setor</b>. O botão <b>Baixar modelo</b> traz um exemplo pronto.</div></li>'
        '<li><div>Salve com <b>Salvar como › CSV UTF-8</b>.</div></li>'
        '<li><div>Clique em <b>Importar CSV</b>, escolha o arquivo <b>(1)</b> ou cole o conteúdo <b>(2)</b> e clique em <b>Pré-visualizar</b> <b>(4)</b>.</div></li>'
        '<li><div>Confira a prévia <b>(5)</b> e clique em <b>Importar</b> <b>(6)</b>.</div></li>'
        '</ol></div>'
        '</div>'
        + '<div style="margin-top:5mm">' + figura("p-07-func-importar.png", 176, "pc", corte=(0, CAIXAS["p-07-func-importar.png"]["corte"]["y"] + CAIXAS["p-07-func-importar.png"]["corte"]["h"] + 0.012), modos={k: "esq" for k in "123456"}) + '</div>'
        '<div class="grade2" style="margin-top:4mm;gap:6mm">'
        '<div><h3>O que a prévia mostra</h3><p style="font-size:9.6pt"><span class="tag ok">Será cadastrado</span> entra normalmente. <span class="tag warn">Será cadastrado com setor novo</span> cria o setor junto, se a opção <b>(3)</b> estiver marcada. <span class="tag neutro">Já cadastrado, será ignorado</span> evita duplicar quem já existe (mesmo nome ou matrícula).</p></div>'
        '<div><h3>Linhas com problema</h3><p style="font-size:9.6pt">Linhas sem nome ou sem setor, ou com letras na matrícula, aparecem em vermelho e não são importadas. Corrija na planilha e importe de novo: quem já entrou é ignorado.</p></div>'
        '</div>'
    )
    pgs.append(pagina(cad, 13, R))

    # Setores
    setores = (
        '<p class="olho">Administração · Aba 5</p><h1>Setores</h1>'
        '<p class="intro">O setor aparece embaixo do nome na lista do quiz, ajuda o funcionário a se achar e é usado nos filtros e na participação por setor.</p>'
        + figura("p-08-setores.png", 176, "pc", corte=(0, 0.9), modos={"1": "esq", "2": "esq"})
        + lista_marcas([
            ("1", "<b>Novo setor</b>: digite o nome e clique em <b>Adicionar setor</b>. Não aceita nome repetido."),
            ("2", "<b>Ações</b>: <b>Renomear</b> muda o nome em todos os funcionários; <b>Inativar</b> tira o setor da lista de escolha no cadastro; <b>Excluir</b> só aparece para setor sem nenhum funcionário."),
        ])
        + '<div class="caixa" style="margin-top:5mm"><h3>Dica</h3><p>Na importação por planilha, os setores que ainda não existem podem ser criados automaticamente. Não é preciso cadastrar todos antes.</p></div>'
    )
    pgs.append(pagina(setores, 14, R))

    # Configurações
    config = (
        '<p class="olho">Administração · Aba 6</p><h1>Configurações</h1>'
        '<p class="intro">Ajustes do quiz e o material para divulgar o link.</p>'
        + figura("p-09-config.png", 176, "pc", corte=(0, 0.86), modos={"1": "esq", "2": "esq", "3": "esq", "4": "cima"})
        + lista_marcas([
            ("1", "<b>Exigir matrícula para responder</b>: depois de escolher o nome, o funcionário precisa digitar a matrícula. Impede que alguém responda no lugar de outra pessoa. Com 5 erros seguidos, o nome fica bloqueado por 15 minutos. Se houver ativos sem matrícula, o painel avisa quantos."),
            ("2", "<b>Link do quiz</b>: <b>Copiar link</b> para mandar no grupo dos funcionários."),
            ("3", "<b>QR Code</b>: aponta para o quiz. Quem lê com a câmera do celular cai direto na lista de nomes."),
            ("4", "<b>Baixar QR Code (PNG)</b>: imagem em tamanho bom para imprimir em folha A4 e colar no mural."),
        ]).replace('class="marcas"', 'class="marcas duas"')
    )
    pgs.append(pagina(config, 15, R))

    # Antes de divulgar + FAQ
    faq = (
        '<p class="olho">Fechamento</p><h1>Antes de divulgar</h1>'
        '<div class="caixa ok"><ol class="passos">'
        '<li><div>Cadastre os <b>setores</b> e os <b>funcionários</b> (um por um ou pela planilha).</div></li>'
        '<li><div>Decida se vai <b>exigir matrícula</b>. Se sim, confira se todos os ativos têm matrícula.</div></li>'
        '<li><div>Testes também ficam gravados. Antes de liberar, peça ao responsável técnico para <b>apagar as respostas de teste</b>. Os cadastros continuam.</div></li>'
        '<li><div>Divulgue o <b>link</b> ou o <b>QR Code</b> do quiz e o <b>Guia do Funcionário</b>. Nunca o link do painel.</div></li>'
        '<li><div>Combine quem da CIPA vai entregar os brindes e onde.</div></li>'
        '</ol></div>'
        '<h2>Dúvidas comuns</h2><div class="faq">'
        '<div><h3>Um funcionário não acha o nome na lista</h3><p>Confira na aba Funcionários se ele está cadastrado e <span class="tag ok">Ativo</span>. Inativos não aparecem no quiz.</p></div>'
        '<div><h3>Alguém pediu para responder de novo</h3><p>Não é possível. O sistema não tem opção para liberar uma nova tentativa, e isso é de propósito, para ninguém refazer até acertar.</p></div>'
        '<div><h3>A pessoa começou e não terminou</h3><p>Ela aparece como <span class="tag warn">Em andamento</span>. Basta abrir o quiz e escolher o nome de novo: continua de onde parou, até em outro celular.</p></div>'
        '<div><h3>O nome dela ficou bloqueado por 15 minutos</h3><p>Acontece quando a matrícula é digitada errada 5 vezes seguidas, com a opção "Exigir matrícula" ligada. Confira a matrícula na aba Funcionários e peça para tentar depois do horário mostrado.</p></div>'
        '<div><h3>Cadastrei com o nome ou o setor errado</h3><p>Use <b>Editar</b> na aba Funcionários. Se a pessoa já respondeu, o ranking continua mostrando o nome e o setor da época da resposta.</p></div>'
        '<div><h3>Registrei um brinde por engano</h3><p>O painel não desfaz a entrega. Fale com o responsável técnico pelo sistema.</p></div>'
        '</div>'
    )
    pgs.append(pagina(faq, 16, R))
    return documento("Manual do Quiz da Segurança · CIPA Momesso", pgs)


# ---------------------------------------------------------------- Guia do Funcionário
def guia_funcionario():
    R = "Guia do Funcionário · Quiz da Segurança"
    topo = (
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6mm">'
        f'<img src="{LOGO_M}" style="height:8mm"><img src="{LOGO_C}" style="height:16mm"></div>'
    )
    acesso = (
        '<div class="caixa" style="display:flex;gap:6mm;align-items:center;margin-bottom:5mm">'
        f'<div class="qr" data-link="{LINK_QUIZ}"></div>'
        '<div><h3 style="font-size:15pt">Acesse o quiz</h3>'
        f'<p style="margin-bottom:1mm">Aponte a câmera do celular para o QR Code ou digite <span class="url" style="font-size:13pt">{LINK_QUIZ_TXT}</span></p>'
        '<p class="mut" style="margin:0;font-size:9.6pt">Sem senha e sem instalar nada. 4 perguntas · 1 tentativa por pessoa · acertou todas, ganha brinde.</p></div></div>'
    )
    paginas = paginas_quiz(R, 1, True)
    # Coloca o cabeçalho e o QR na primeira página do guia
    paginas[0] = paginas[0].replace('<div class="conteudo"><p class="olho">Guia do funcionário</p>',
                                    '<div class="conteudo">' + topo + '<p class="olho">Guia do funcionário</p>', 1)
    paginas[0] = paginas[0].replace('<div class="linha">', acesso + '<div class="linha">', 1)
    return documento("Guia do Funcionário · Quiz da Segurança", paginas)


async def imprimir(html, nome_pdf):
    caminho_html = os.path.join(SAIDA, nome_pdf.replace(".pdf", ".html"))
    open(caminho_html, "w", encoding="utf-8").write(html)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page()
        await pg.goto("file://" + caminho_html)
        await pg.evaluate("document.fonts.ready")
        await pg.wait_for_timeout(400)
        estouros = await pg.evaluate("""() => [...document.querySelectorAll('.pg .conteudo')].map((c, i) => [i + 1, c.scrollHeight - c.clientHeight]).filter(x => x[1] > 1)""")
        if estouros:
            print("AVISO: conteúdo passando da página (página, mm aprox.):", [(n, round(px * 25.4 / 96, 1)) for n, px in estouros])
        await pg.pdf(path=os.path.join(SAIDA, nome_pdf), prefer_css_page_size=True, print_background=True)
        await b.close()
    print("ok", nome_pdf, os.path.getsize(os.path.join(SAIDA, nome_pdf)) // 1024, "KB")


async def main():
    await imprimir(manual_cipa(), "Manual-Quiz-da-Seguranca-CIPA.pdf")
    await imprimir(guia_funcionario(), "Guia-do-Funcionario-Quiz-da-Seguranca.pdf")

asyncio.run(main())
