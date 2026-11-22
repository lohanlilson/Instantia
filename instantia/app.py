"""O Instantia rodando: ícone perto do relógio, tecla Print Screen, capturas, gravação e atualização."""
from __future__ import annotations

import os
import sys
import time

from PySide6.QtCore import QObject, QRect, QSettings, QStandardPaths, QTimer
from PySide6.QtGui import QAction, QGuiApplication, QIcon, QImage
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QMessageBox, QSystemTrayIcon

from . import APP_ID, APP_NAME, historico, resource, tema
from .flutuantes import Fixada, avisar as mostrar_aviso
from .icones import icone

SERVIDOR = "Instantia-" + (os.environ.get("USERNAME") or os.environ.get("USER") or "u")


def instancia_aberta(mensagem: str = "mostrar") -> bool:
    """Se o Instantia já está aberto, manda a mensagem (mostrar / capturar …) e devolve True."""
    s = QLocalSocket()
    s.connectToServer(SERVIDOR)
    if not s.waitForConnected(400):
        return False
    s.write(mensagem.encode("utf-8"))
    s.flush()
    s.waitForBytesWritten(1000)
    s.disconnectFromServer()
    return True


def iniciar_com_windows(ligar: bool):
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return
    import winreg
    chave = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, chave, 0, winreg.KEY_SET_VALUE) as k:
        if ligar:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, f'"{sys.executable}" --bandeja')
        else:
            try:
                winreg.DeleteValue(k, APP_NAME)
            except OSError:
                pass


class Controle(QObject):
    def __init__(self, app: QApplication, iniciar_na_bandeja=False):
        super().__init__()
        self.app = app
        self.settings = QSettings(APP_ID, APP_ID)
        self.icone = QIcon(resource("assets", "instantia.png"))
        self.sessao = None
        self.gravacao = None
        self._grav_ui = []
        self._threads = []

        self.servidor = QLocalServer(self)
        QLocalServer.removeServer(SERVIDOR)
        self.servidor.listen(SERVIDOR)
        self.servidor.newConnection.connect(self._mensagem)

        from .janela import Janela
        self.janela = Janela(self)
        from .atualizador import Atualizador
        self.atualizador = Atualizador(self.janela)

        self.tray = QSystemTrayIcon(self.icone, self)
        self.tray.setToolTip(f"{APP_NAME} — Print Screen para capturar")
        m = QMenu()
        for texto, ic, fn in (("Capturar área\tPrint Screen", "camera", lambda: self.capturar("imagem")),
                              ("Copiar texto da tela\tCtrl+Print Screen", "ocr", lambda: self.capturar("texto")),
                              ("Gravar a tela\tShift+Print Screen", "gravar", lambda: self.capturar("gravar")),
                              ("Capturar em 3 segundos", "historico", lambda: self.capturar("imagem", atraso=3))):
            a = QAction(icone(ic, "#6c6880"), texto, m)
            a.triggered.connect(fn)
            m.addAction(a)
        m.addSeparator()
        m.addAction(icone("janela", "#6c6880"), "Abrir o Instantia", self.mostrar_janela)
        m.addAction(icone("pasta", "#6c6880"), "Abrir a pasta dos prints",
                    self._abrir_pasta)
        m.addAction(icone("config", "#6c6880"), "Configurações", lambda: (self.mostrar_janela(), self.janela.configuracoes()))
        m.addSeparator()
        m.addAction("Sair", self.encerrar)
        self._menu = m
        self.tray.setContextMenu(m)
        self.tray.activated.connect(self._tray_clicado)
        self.tray.show()

        from .teclado import Teclado
        self.teclado = Teclado()
        self.teclado.atalho.connect(self._atalho)
        self.aplicar_configuracoes(primeira=True)
        if not iniciar_na_bandeja:
            self.mostrar_janela()
        QTimer.singleShot(5000, self.atualizador.verificar_auto)
        QTimer.singleShot(1500, self._resultado_atualizacao)

    # ------------------------------------------------------------------ geral
    def pasta_salvar(self) -> str:
        p = self.settings.value("pasta_salvar", "") or os.path.join(
            QStandardPaths.writableLocation(QStandardPaths.PicturesLocation) or os.path.expanduser("~"), "Instantia")
        os.makedirs(p, exist_ok=True)
        return p

    def aplicar_configuracoes(self, primeira=False):
        s = self.settings
        escolha = s.value("tema", "auto")
        tema.aplicar(self.app, tema.sistema_escuro() if escolha == "auto" else escolha == "escuro")
        if s.value("usar_printscreen", "true") != "false":
            ok = self.teclado.ligar()
            if not ok and sys.platform == "win32" and not primeira:
                QMessageBox.warning(self.janela, APP_NAME, "Não foi possível usar a tecla Print Screen.")
        else:
            self.teclado.desligar()
        try:
            iniciar_com_windows(s.value("iniciar_windows", "true") != "false")
        except OSError:
            pass

    def _abrir_pasta(self):
        from .janela import abrir_arquivo
        abrir_arquivo(self.pasta_salvar())

    def mostrar_janela(self):
        self.janela.show()
        if self.janela.isMinimized():
            self.janela.showNormal()
        self.janela.raise_()
        self.janela.activateWindow()

    def _tray_clicado(self, motivo):
        if motivo == QSystemTrayIcon.Trigger:
            self.capturar("imagem")
        elif motivo == QSystemTrayIcon.DoubleClick:
            self.mostrar_janela()

    def _mensagem(self):
        while self.servidor.hasPendingConnections():
            c = self.servidor.nextPendingConnection()
            c.waitForReadyRead(500)
            msg = bytes(c.readAll()).decode("utf-8", "replace").strip()
            c.disconnectFromServer()
            if msg.startswith("capturar"):
                self.capturar(msg.split(":", 1)[1] if ":" in msg else "imagem")
            else:
                self.mostrar_janela()

    def _atalho(self, mod):
        if self.gravacao is not None:              # gravando: Print Screen de novo para a gravação
            self._parar_gravacao("mp4")
            return
        self.capturar({"": "imagem", "ctrl": "texto", "shift": "gravar"}.get(mod, "imagem"))

    def _resultado_atualizacao(self):
        from .atualizador import avisar_falha, resultado_da_ultima_atualizacao
        info = resultado_da_ultima_atualizacao()
        if info:
            avisar_falha(self.janela, info)

    def encerrar(self, atualizando=False):
        if self.gravacao is not None:
            self._parar_gravacao("mp4")
        self.teclado.desligar()
        self.tray.hide()
        self.servidor.close()
        if not atualizando:
            self.app.quit()

    # ------------------------------------------------------------------ captura
    def capturar(self, modo="imagem", atraso=0):
        if self.sessao is not None or self.gravacao is not None:
            return
        if atraso:
            mostrar_aviso(f"Capturando em {atraso} s…", "Abra o menu ou a janela que você quer capturar.", ms=atraso * 1000 - 200)
            QTimer.singleShot(atraso * 1000, lambda: self.capturar(modo))
            return
        janela_visivel = self.janela.isVisible() and not self.janela.isMinimized() and self.janela.isActiveWindow()
        if janela_visivel:                          # não sai a própria janela do Instantia no print
            self.janela.hide()
            QApplication.processEvents()
            QTimer.singleShot(220, lambda: self._abrir_sessao(modo, reabrir=True))
            return
        self._abrir_sessao(modo)

    def _abrir_sessao(self, modo, reabrir=False):
        from .seletor import Sessao
        s = self.settings
        ferr = s.value("ferramenta_inicial", "seta") or None
        self._reabrir = reabrir
        self.sessao = Sessao(self._concluido, modo, cor=s.value("cor", "#e5243b"), espessura=int(s.value("espessura", 4)),
                             ferramenta_inicial=ferr)
        self.sessao.mostrar()

    def _concluido(self, acao, img: QImage | None, seletor):
        sess = self.sessao
        self.sessao = None
        if sess is not None:
            self.settings.setValue("cor", sess.cor)
            if seletor is not None:
                self.settings.setValue("espessura", seletor.espessura)
        if acao == "cancelar":
            self._voltar_janela()
            return
        if sess is not None and sess.modo == "gravar":
            self._preparar_gravacao(seletor)
            return
        if acao == "texto":
            self._copiar_texto(img)
        elif acao == "copiar":
            self.copiar(img)
        elif acao == "salvar":
            self.salvar(img)
        elif acao == "salvar_como":
            self.salvar(img, perguntar=True)
        elif acao == "fixar":
            pos = seletor.mapToGlobal(seletor.sel.topLeft())
            self.fixar(img, pos, seletor.foto.escala)
            self._guardar(img)
        self._voltar_janela()

    def _voltar_janela(self):
        if getattr(self, "_reabrir", False):
            self._reabrir = False
            QTimer.singleShot(150, self.mostrar_janela)

    def _guardar(self, img):
        if self.settings.value("historico", "true") != "false":
            try:
                historico.guardar(img, int(self.settings.value("historico_limite", 300)))
            except OSError:
                pass
            if self.janela.isVisible():
                self.janela.recarregar()

    def copiar(self, img: QImage, avisar=True, guardar=True):
        QGuiApplication.clipboard().setImage(img)
        if guardar:
            self._guardar(img)
        if avisar:
            mostrar_aviso("Copiado ✓", f"{img.width()} × {img.height()} — cole com Ctrl+V", img)

    def _nome(self):
        return time.strftime("Instantia %Y-%m-%d %H-%M-%S")

    def salvar(self, img: QImage, perguntar=False):
        fmt = self.settings.value("formato", "png")
        destino = os.path.join(self.pasta_salvar(), f"{self._nome()}.{fmt}")
        if perguntar:
            destino, _ = QFileDialog.getSaveFileName(None, "Salvar print", destino,
                                                     "PNG (*.png);;JPG (*.jpg);;BMP (*.bmp)")
            if not destino:
                return
        n = 2
        base, ext = os.path.splitext(destino)
        while os.path.exists(destino) and not perguntar:
            destino = f"{base} ({n}){ext}"
            n += 1
        ok = img.save(destino, quality=92 if ext.lower() in (".jpg", ".jpeg") else -1)
        if not ok:
            QMessageBox.warning(None, APP_NAME, f"Não foi possível salvar em:\n{destino}")
            return
        if self.settings.value("copiar_ao_salvar", "true") != "false":
            QGuiApplication.clipboard().setImage(img)
        self._guardar(img)
        from .janela import mostrar_na_pasta
        mostrar_aviso("Salvo ✓", os.path.basename(destino) + " — clique para abrir a pasta", img, ms=4500,
               acao=lambda: mostrar_na_pasta(destino))
        return destino

    def fixar(self, img: QImage, pos=None, escala=None):
        from PySide6.QtGui import QCursor
        tela = QGuiApplication.screenAt(pos or QCursor.pos()) or QGuiApplication.primaryScreen()
        f = Fixada(img, pos or (QCursor.pos()), escala or tela.devicePixelRatio(),
                   ao_copiar=lambda i: self.copiar(i, guardar=False), ao_salvar=lambda i: self.salvar(i, perguntar=True))
        f.show()
        f.raise_()
        f.activateWindow()
        return f

    def _copiar_texto(self, img: QImage):
        from .sensiveis import ThreadTexto
        mostrar_aviso("Lendo o texto…", ms=1500)
        th = ThreadTexto(img)
        th.terminou.connect(lambda t, e: self._texto_pronto(t, e, img))
        th.start()

    def _texto_pronto(self, texto, erro, img):
        if erro:
            mostrar_aviso("Não foi possível ler o texto", erro, ms=6000)
            return
        if not texto.strip():
            mostrar_aviso("Nenhum texto encontrado", "Tente selecionar uma área maior ou com letras mais nítidas.", img)
            return
        QGuiApplication.clipboard().setText(texto)
        linhas = texto.strip().splitlines()
        previa = "\n".join(linhas[:3])[:160] + ("…" if len(linhas) > 3 or len(texto) > 160 else "")
        mostrar_aviso("Texto copiado ✓", previa, ms=5000)

    # ------------------------------------------------------------------ gravação
    def _preparar_gravacao(self, seletor):
        from .gravacao import ThreadFFmpeg, caminho_ffmpeg
        self._grav_alvo = (seletor.foto, QRect(seletor.sel))
        if caminho_ffmpeg():
            self._iniciar_gravacao()
            return
        mostrar_aviso("Preparando o gravador…", "Na primeira gravação o FFmpeg é baixado (uma vez só, cerca de 30 MB).",
               ms=8000)
        th = ThreadFFmpeg()
        th.terminou.connect(self._ffmpeg_pronto)
        self._threads.append(th)
        th.start()

    def _ffmpeg_pronto(self, caminho, erro):
        if erro:
            QMessageBox.warning(None, APP_NAME, f"Não foi possível baixar o gravador (FFmpeg):\n{erro}")
            return
        self._iniciar_gravacao()

    def _iniciar_gravacao(self):
        from .gravacao import BarraGravacao, Gravacao, Moldura
        foto, sel = self._grav_alvo
        s = self.settings
        g = Gravacao(foto.retangulo_fisico(sel), self.pasta_salvar(), int(s.value("grav_fps", 30)),
                     s.value("grav_micro", "") or "", s.value("grav_cursor", "true") != "false")
        area_global = sel.translated(foto.geo.topLeft())
        moldura = Moldura(area_global)
        barra = BarraGravacao(area_global, foto.geo)
        barra.pedir.connect(self._parar_gravacao)
        moldura.show()
        barra.show()
        QApplication.processEvents()
        try:
            g.iniciar()
        except Exception as e:  # noqa: BLE001
            moldura.close()
            barra.close()
            QMessageBox.warning(None, APP_NAME, f"Não foi possível começar a gravação:\n{e}")
            return
        self.gravacao = g
        self._grav_ui = [moldura, barra]
        self._grav_timer = QTimer(self, interval=500, timeout=lambda: barra.mostrar_tempo(g.duracao()))
        self._grav_timer.start()
        self.tray.setToolTip(f"{APP_NAME} — gravando (Print Screen para parar)")

    def _parar_gravacao(self, formato):
        g = self.gravacao
        if g is None:
            return
        self.gravacao = None
        self._grav_timer.stop()
        for w in self._grav_ui:
            w.close()
        self._grav_ui = []
        self.tray.setToolTip(f"{APP_NAME} — Print Screen para capturar")
        if formato == "cancelar":
            g.cancelar()
            return
        if formato == "gif":
            mostrar_aviso("Gerando o GIF…", ms=2500)
        QApplication.processEvents()
        try:
            destino = g.parar(formato, self._nome())
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(None, APP_NAME, f"Não foi possível salvar a gravação:\n{e}")
            return
        historico.registrar_arquivo(destino, int(self.settings.value("historico_limite", 300)))
        if self.janela.isVisible():
            self.janela.recarregar()
        from .janela import mostrar_na_pasta
        mostrar_aviso("Gravação salva ✓", os.path.basename(destino) + " — clique para abrir a pasta", ms=6000,
               acao=lambda: mostrar_na_pasta(destino))
        if sys.platform == "win32":                  # deixa o arquivo pronto para colar (Ctrl+V) no WhatsApp/e-mail
            try:
                from PySide6.QtCore import QMimeData, QUrl
                md = QMimeData()
                md.setUrls([QUrl.fromLocalFile(destino)])
                QGuiApplication.clipboard().setMimeData(md)
            except Exception:  # noqa: BLE001
                pass


__all__ = ["Controle", "instancia_aberta", "iniciar_com_windows", "SERVIDOR"]
