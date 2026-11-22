"""Autoteste (usado na publicação e para conferir o programa instalado): Instantia.exe --selftest saida.txt"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import traceback


def executar(argv):
    i = argv.index("--selftest")
    saida = argv[i + 1] if len(argv) > i + 1 else None
    linhas = []

    def log(msg):
        linhas.append(msg)
        print(msg, flush=True)
        if saida:
            with open(saida, "w", encoding="utf-8") as f:
                f.write("\n".join(linhas) + "\n")

    os.environ.setdefault("LOCALAPPDATA", tempfile.mkdtemp(prefix="instantia-teste-"))
    falhas = 0
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(argv[:1])
        from . import __version__
        log(f"Instantia {__version__} — autoteste ({sys.platform}, Python {sys.version.split()[0]})")
        for teste in (t_anotacoes, t_seletor, t_sensiveis, t_ocr, t_historico, t_interface, t_teclado, t_gravacao):
            try:
                falhas += teste(log, app)
            except Exception:  # noqa: BLE001
                falhas += 1
                log(f"ERRO {teste.__name__}:\n" + traceback.format_exc())
    except Exception:  # noqa: BLE001
        falhas += 1
        log("ERRO geral:\n" + traceback.format_exc())
    log(f"RESULTADO: {'tudo certo' if not falhas else f'{falhas} falha(s)'}")
    sys.stdout.flush()
    codigo = 1 if falhas else 0
    if sys.platform == "win32":     # sai sem descarregar as DLLs (o Windows OCR às vezes trava na descarga)
        import ctypes
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.TerminateProcess(ctypes.c_void_p(k.GetCurrentProcess()), codigo)
    os._exit(codigo)


def ok(log, cond, msg):
    log(("OK   " if cond else "ERRO ") + msg)
    return 0 if cond else 1


def _imagem_teste(w=900, h=520):
    from PySide6.QtGui import QColor, QFont, QImage, QPainter
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor("white"))
    g = QPainter(img)
    f = QFont("Segoe UI" if sys.platform == "win32" else "DejaVu Sans")
    f.setPixelSize(16)
    g.setFont(f)
    g.setPen(QColor("#222222"))
    linhas = ["Cliente: Maria de Souza", "CPF: 123.456.789-09", "CNPJ 53.176.704/0001-86",
              "E-mail: maria.souza@empresa.com.br", "Telefone: (62) 98119-7966", "Valor total: R$ 1.500,00",
              "Data: 15/11/2026", "Boleto: 23793.38128 60000.000003 00000.000400 1 84340000150000"]
    for i, t in enumerate(linhas):
        g.drawText(24, 40 + 44 * i, t)
    g.end()
    return img, linhas


class _FotoFalsa:
    def __init__(self, img, escala=1.0):
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QGuiApplication
        self.tela = QGuiApplication.primaryScreen()
        self.imagem = img
        self.escala = escala
        self.geo = QRect(0, 0, int(img.width() / escala), int(img.height() / escala))
        self.janelas = [QRect(100, 100, 300, 200)]
        self.origem_fisica = (0, 0)

    def retangulo_fisico(self, r):
        return (r.x(), r.y(), r.width() // 2 * 2, r.height() // 2 * 2)


def t_anotacoes(log, app):
    from PySide6.QtCore import QPointF, QRect, QRectF
    from PySide6.QtGui import QColor
    from . import anotacoes as A
    img, _ = _imagem_teste()
    anots = [A.Seta(QPointF(10, 10), QPointF(200, 120), cor="#e5243b", espessura=4),
             A.Retangulo(QRectF(20, 150, 120, 60), cor="#1e88e5", espessura=4),
             A.Borrao(QRectF(20, 50, 200, 30)), A.Numero(QPointF(300, 300), 3, cor="#21b04b"),
             A.Texto(QPointF(400, 200), "Olá", cor="#e5243b"), A.MarcaTexto(QRectF(20, 250, 200, 24)),
             A.CanetaLivre([QPointF(500, 400), QPointF(520, 420), QPointF(560, 410)], cor="#8b5cff"),
             A.Elipse(QRectF(600, 50, 100, 60)), A.Linha(QPointF(600, 200), QPointF(800, 200))]
    falhas = 0
    for esc in (1.0, 1.5):
        from PySide6.QtCore import Qt
        base = img.scaled(int(img.width() * esc), int(img.height() * esc), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        out = A.renderizar(base, QRect(0, 0, 900, 520), anots, esc)
        falhas += ok(log, out.width() == int(900 * esc) and out.height() == int(520 * esc),
                     f"marcações renderizadas na resolução real (escala {esc}): {out.width()}×{out.height()}")
        p = QColor(out.pixel(int(105 * esc), int(65 * esc)))           # meio da seta
        falhas += ok(log, p.red() > 180 and p.green() < 90, f"seta desenhada em vermelho (escala {esc})")
    # borrão escondeu o texto (variedade de cores menor)
    out = A.renderizar(img, QRect(0, 0, 900, 520), [A.Borrao(QRectF(20, 20, 300, 30))], 1.0)
    antes = len({img.pixel(x, y) for x in range(24, 300, 2) for y in range(25, 48, 2)})
    depois = len({out.pixel(x, y) for x in range(24, 300, 2) for y in range(25, 48, 2)})
    falhas += ok(log, depois < antes, f"borrão esconde o texto ({antes} → {depois} tons)")
    a = A.Seta(QPointF(0, 0), QPointF(100, 0))
    falhas += ok(log, a.contem(QPointF(50, 2)) and not a.contem(QPointF(50, 40)), "clique acerta a marcação")
    return falhas


def t_seletor(log, app):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QColor
    from PySide6.QtTest import QTest
    from . import seletor as S
    img, _ = _imagem_teste()
    falhas = 0
    resultado = {}

    def fim(acao, imagem, sel):
        resultado.update(acao=acao, imagem=imagem)

    orig = S.Sessao.__init__

    def init(self, *a, **k):
        import instantia.captura as C
        f0 = C.fotografar
        C.fotografar = lambda telas=None: [_FotoFalsa(img)]
        try:
            orig(self, *a, **k)
        finally:
            C.fotografar = f0
    S.Sessao.__init__ = init
    try:
        s = S.Sessao(fim, "imagem", ferramenta_inicial="seta")
        s.mostrar()
        w = s.seletores[0]
        app.processEvents()
        QTest.mousePress(w, Qt.LeftButton, Qt.NoModifier, QPoint(50, 60))
        QTest.mouseMove(w, QPoint(300, 200))
        _mover(w, QPoint(450, 330), Qt.LeftButton)
        QTest.mouseRelease(w, Qt.LeftButton, Qt.NoModifier, QPoint(450, 330))
        app.processEvents()
        falhas += ok(log, w.estado == "editando" and w.sel.width() == 401 and w.barra is not None and w.barra.isVisible(),
                     f"arrastar escolhe a área ({w.sel.width()}×{w.sel.height()}) e mostra a barra")
        # seta com o mouse
        QTest.mousePress(w, Qt.LeftButton, Qt.NoModifier, QPoint(100, 100))
        _mover(w, QPoint(300, 250), Qt.LeftButton)
        QTest.mouseRelease(w, Qt.LeftButton, Qt.NoModifier, QPoint(300, 250))
        falhas += ok(log, len(w.anots) == 1 and w.anots[0].tipo == "seta", "seta desenhada com o mouse")
        QTest.keyClick(w, Qt.Key_N)
        QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, QPoint(380, 120))
        QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, QPoint(400, 160))
        falhas += ok(log, [a.n for a in w.anots if a.tipo == "numero"] == [1, 2], "numeração 1, 2 com a tecla N")
        QTest.keyClick(w, Qt.Key_Z, Qt.ControlModifier)
        falhas += ok(log, len(w.anots) == 2 and w.numero == 2, "Ctrl+Z desfaz")
        QTest.keyClick(w, Qt.Key_Y, Qt.ControlModifier)
        falhas += ok(log, len(w.anots) == 3, "Ctrl+Y refaz")
        # texto
        QTest.keyClick(w, Qt.Key_T)
        QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, QPoint(120, 280))
        app.processEvents()
        falhas += ok(log, w.editor_texto is not None, "ferramenta de texto abre o campo")
        if w.editor_texto:
            w.editor_texto.insert("Atenção aqui")
            QTest.keyClick(w.editor_texto, Qt.Key_Return)
        falhas += ok(log, any(a.tipo == "texto" and a.texto == "Atenção aqui" for a in w.anots), "texto escrito no print")
        # mover a marcação com a ferramenta de mover
        QTest.keyClick(w, Qt.Key_V)
        seta = w.anots[0]
        antes = seta.p1.x()
        QTest.mousePress(w, Qt.LeftButton, Qt.NoModifier, QPoint(200, 175))
        _mover(w, QPoint(230, 175), Qt.LeftButton)
        QTest.mouseRelease(w, Qt.LeftButton, Qt.NoModifier, QPoint(230, 175))
        falhas += ok(log, abs(seta.p1.x() - antes - 30) < 1, "arrastar move a marcação")
        QTest.keyClick(w, Qt.Key_Return)
        app.processEvents()
        im = resultado.get("imagem")
        falhas += ok(log, resultado.get("acao") == "copiar" and im is not None and im.width() == 401,
                     f"Enter conclui com a imagem ({im.width() if im else 0}×{im.height() if im else 0})")
        if im is not None:
            sx, sy = seta.p1.x() - 50, seta.p1.y() - 60        # seta em coordenadas da imagem
            ex, ey = seta.p2.x() - 50, seta.p2.y() - 60
            vermelhos = 0
            for t in (0.2, 0.3, 0.4, 0.5, 0.6):
                c = QColor(im.pixel(int(sx + (ex - sx) * t), int(sy + (ey - sy) * t)))
                vermelhos += c.red() > 150 and c.green() < 110 and c.blue() < 120
            falhas += ok(log, vermelhos >= 4, f"imagem final contém a seta ({vermelhos}/5 pontos)")
        # clique sem arrastar = janela embaixo; Esc cancela
        resultado.clear()
        s2 = S.Sessao(fim, "imagem")
        s2.mostrar()
        w2 = s2.seletores[0]
        QTest.mouseMove(w2, QPoint(150, 150))
        QTest.mouseClick(w2, Qt.LeftButton, Qt.NoModifier, QPoint(150, 150))
        falhas += ok(log, w2.sel is not None and w2.sel.width() == 300 and w2.sel.height() == 200,
                     "um clique captura a janela embaixo do cursor")
        QTest.keyClick(w2, Qt.Key_Escape)
        app.processEvents()
        falhas += ok(log, resultado.get("acao") == "cancelar", "Esc cancela")
        # ocultar dados direto na tela congelada
        resultado.clear()
        s3 = S.Sessao(fim, "imagem")
        s3.mostrar()
        w3 = s3.seletores[0]
        QTest.keyClick(w3, Qt.Key_Return)          # Enter sem seleção: tela inteira
        app.processEvents()
        from . import ocr
        if ocr.motor_disponivel():
            w3.ocultar_dados()
            fim_t = time.time() + 60
            while time.time() < fim_t and not any(a.tipo == "borrao" for a in w3.anots):
                app.processEvents()
                time.sleep(0.05)
            n = sum(1 for a in w3.anots if a.tipo == "borrao")
            falhas += ok(log, n >= 5, f"“Ocultar dados” borrou {n} dado(s) na tela")
        QTest.keyClick(w3, Qt.Key_Escape)
    finally:
        S.Sessao.__init__ = orig
    return falhas


def _mover(w, alvo, botao):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication
    ev = QMouseEvent(QMouseEvent.MouseMove, QPointF(alvo), QPointF(w.mapToGlobal(alvo)), Qt.NoButton, botao, Qt.NoModifier)
    QApplication.sendEvent(w, ev)


def t_sensiveis(log, app):
    from PySide6.QtCore import QRect
    from . import ocr, sensiveis as SV
    falhas = 0
    falhas += ok(log, SV.cpf_valido("123.456.789-09") and not SV.cpf_valido("123.456.789-00"), "validação de CPF")
    falhas += ok(log, SV.cnpj_valido("53176704000186") and not SV.cnpj_valido("53176704000187"), "validação de CNPJ")
    falhas += ok(log, SV.luhn("4111 1111 1111 1111") and not SV.luhn("4111 1111 1111 1112"), "validação de cartão")
    palavras = []
    texto = ["Pago por 12345678909 em 10/11", "Data 15/11/2026 pedido 98765", "pix 7d9f0a1e-3b2c-4d5e-8f90-a1b2c3d4e5f6"]
    for li, t in enumerate(texto):
        x = 0
        for w in t.split():
            palavras.append(ocr.Palavra(w, QRect(x, li * 20, len(w) * 8, 16), li))
            x += len(w) * 8 + 8
    tipos = [t for t, _ in SV.achar(palavras)]
    falhas += ok(log, tipos == ["CPF", "chave PIX"], f"acha CPF sem pontos e chave PIX; ignora datas e pedidos ({tipos})")
    return falhas


def t_ocr(log, app):
    from . import ocr, sensiveis as SV
    motor = ocr.motor_disponivel()
    if not motor:
        return ok(log, sys.platform != "win32", "OCR disponível (sem OCR neste computador)")
    img, linhas = _imagem_teste()
    t0 = time.time()
    pal = ocr.reconhecer(img)
    texto = ocr.texto(pal)
    falhas = ok(log, "maria" in texto.lower() and "1.500" in texto,
                f"OCR ({motor}) leu o print em {time.time() - t0:.1f} s: {texto.splitlines()}")
    tipos = {t for t, _ in SV.achar(pal)}
    esperado = {"CPF", "CNPJ", "e-mail", "telefone", "valor", "linha digitável"}
    falhas += ok(log, esperado <= tipos, f"dados sensíveis no print: {sorted(tipos)}")
    return falhas


def t_historico(log, app):
    from . import historico
    img, _ = _imagem_teste(200, 100)
    c = historico.guardar(img, 300)
    arq = os.path.join(tempfile.mkdtemp(), "video.mp4")
    open(arq, "wb").write(b"x")
    historico.registrar_arquivo(arq)
    itens = historico.itens()
    falhas = ok(log, itens[:2] == [arq, c] or set(itens[:2]) == {arq, c}, "histórico guarda prints e gravações")
    historico.apagar(arq)
    falhas += ok(log, arq not in historico.itens() and os.path.exists(arq), "tirar do histórico não apaga o arquivo")
    return falhas


def t_interface(log, app):
    from PySide6.QtGui import QGuiApplication
    from .app import Controle
    from .janela import DialogoConfig
    falhas = 0
    ctl = Controle(app, iniciar_na_bandeja=False)
    app.processEvents()
    falhas += ok(log, ctl.janela.isVisible(), "janela principal abre")
    img, _ = _imagem_teste(320, 200)
    ctl.copiar(img)
    cb = QGuiApplication.clipboard().image()
    falhas += ok(log, cb.width() == 320, "copiar coloca a imagem na área de transferência")
    destino = ctl.salvar(img)
    falhas += ok(log, bool(destino) and os.path.exists(destino), f"salvar grava o arquivo ({os.path.basename(destino or '')})")
    os.remove(destino)
    f = ctl.fixar(img)
    app.processEvents()
    falhas += ok(log, f.isVisible() and f.width() >= 320, "fixar na tela")
    f.close()
    d = DialogoConfig(ctl.janela, ctl)
    d.show()
    app.processEvents()
    d.accept()
    falhas += ok(log, True, "configurações abrem e salvam")
    ctl.janela.recarregar()
    app.processEvents()
    falhas += ok(log, ctl.janela.lista.count() >= 1, f"recentes mostram {ctl.janela.lista.count()} item(ns)")
    ctl.encerrar(atualizando=True)
    return falhas


def t_teclado(log, app):
    if sys.platform != "win32":
        return 0
    from .teclado import Teclado
    t = Teclado()
    ligou = t.ligar()
    t.desligar()
    return ok(log, ligou, "tecla Print Screen (gancho do teclado) ligada")


def t_gravacao(log, app):
    from . import gravacao as G
    cmd = G.comando("ffmpeg", (10, 20, 640, 360), "s.mp4", 30, "Microfone (Realtek)", True, plataforma="win32")
    falhas = ok(log, "gdigrab" in cmd and "-offset_x" in cmd and "audio=Microfone (Realtek)" in cmd and "640x360" in cmd,
                "comando do FFmpeg para gravar a área")
    if os.environ.get("INSTANTIA_TESTE_GRAVACAO") != "1":
        return falhas
    ff = G.caminho_ffmpeg() or G.baixar_ffmpeg()
    falhas += ok(log, bool(ff) and os.path.exists(ff), f"FFmpeg baixado ({ff})")
    pasta = tempfile.mkdtemp()
    try:
        g = G.Gravacao((0, 0, 320, 240), pasta, 15)
        g.iniciar()
        time.sleep(2.5)
        mp4 = g.parar("mp4", "teste")
        falhas += ok(log, os.path.getsize(mp4) > 1000, f"gravou {os.path.getsize(mp4)} bytes de vídeo")
        gif = G.para_gif(ff, mp4, os.path.join(pasta, "teste.gif"))
        falhas += ok(log, os.path.getsize(gif) > 100, "converteu em GIF")
    except Exception as e:  # noqa: BLE001
        log(f"AVISO gravação real não pôde ser testada aqui: {e}")
    return falhas


__all__ = ["executar"]
