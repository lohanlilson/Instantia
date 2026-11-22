"""Janela principal (atalhos, prints recentes) e Configurações."""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu, QPushButton,
                               QSpinBox, QTabWidget, QVBoxLayout, QWidget)

from . import APP_NAME, COPYRIGHT, EMAIL, __version__, historico, resource
from .icones import icone


def abrir_arquivo(c):
    QDesktopServices.openUrl(QUrl.fromLocalFile(c))


def mostrar_na_pasta(c):
    if sys.platform == "win32":
        import subprocess
        subprocess.Popen(["explorer", "/select,", os.path.normpath(c)])
    else:
        abrir_arquivo(os.path.dirname(c))


class _Miniaturas(QThread):
    pronta = Signal(str, QImage)

    def __init__(self, caminhos):
        super().__init__()
        self.caminhos = caminhos

    def run(self):
        for c in self.caminhos:
            if c.lower().endswith(".mp4"):
                continue
            img = QImage(c)
            if not img.isNull():
                from PySide6.QtGui import QColor, QPainter
                mini = img.scaled(200, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                g = QPainter(mini)
                g.setPen(QColor(0, 0, 0, 40))
                g.drawRect(mini.rect().adjusted(0, 0, -1, -1))
                g.end()
                self.pronta.emit(c, mini)


class Janela(QMainWindow):
    def __init__(self, app_ctl):
        super().__init__()
        self.ctl = app_ctl
        self.settings = app_ctl.settings
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(resource("assets", "instantia.png")))
        self.resize(900, 640)
        central = QWidget()
        self.setCentralWidget(central)
        v = QVBoxLayout(central)
        v.setContentsMargins(18, 18, 18, 10)
        v.setSpacing(14)

        hero = QFrame(objectName="Hero")
        hv = QVBoxLayout(hero)
        hv.setContentsMargins(22, 18, 22, 18)
        t = QLabel("Instantia", objectName="HeroTitle")
        sub = QLabel("Aperte <b>Print Screen</b> em qualquer lugar: escolha a área, marque e copie. "
                     "Clique numa janela para capturá-la inteira.", objectName="HeroSub")
        sub.setWordWrap(True)
        hv.addWidget(t)
        hv.addWidget(sub)
        linha = QHBoxLayout()
        linha.setSpacing(8)
        for texto, ic, fn in (("Capturar área", "camera", lambda: app_ctl.capturar("imagem")),
                              ("Copiar texto da tela", "ocr", lambda: app_ctl.capturar("texto")),
                              ("Gravar a tela", "gravar", lambda: app_ctl.capturar("gravar")),
                              ("Capturar em 3 s", "historico", lambda: app_ctl.capturar("imagem", atraso=3))):
            b = QPushButton(icone(ic, "#5b2fd6"), "  " + texto, objectName="HeroPrimary")
            b.setIconSize(QSize(18, 18))
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(fn)
            linha.addWidget(b)
        linha.addStretch()
        hv.addLayout(linha)
        dica = QLabel("Print Screen = área  ·  Ctrl + Print Screen = copiar texto  ·  Shift + Print Screen = gravar",
                      objectName="HeroSub")
        hv.addWidget(dica)
        v.addWidget(hero)

        cab = QHBoxLayout()
        cab.addWidget(QLabel("<b>Recentes</b>"))
        cab.addStretch()
        for texto, ic, fn in (("Abrir pasta", "pasta", lambda: abrir_arquivo(app_ctl.pasta_salvar())),
                              ("Configurações", "config", self.configuracoes)):
            b = QPushButton(icone(ic, "#6c6880"), " " + texto)
            b.clicked.connect(fn)
            cab.addWidget(b)
        v.addLayout(cab)

        self.lista = QListWidget()
        self.lista.setViewMode(QListWidget.IconMode)
        self.lista.setIconSize(QSize(200, 128))
        self.lista.setGridSize(QSize(220, 170))
        self.lista.setResizeMode(QListWidget.Adjust)
        self.lista.setMovement(QListWidget.Static)
        self.lista.setSpacing(6)
        self.lista.setWordWrap(True)
        self.lista.setStyleSheet("QListWidget { border: none; background: transparent; }"
                                 "QListWidget::item { border-radius: 10px; padding: 6px; color: palette(text); }"
                                 "QListWidget::item:hover { background: palette(alternate-base); }"
                                 "QListWidget::item:selected { background: palette(highlight); color: palette(highlighted-text); }")
        self.lista.setContextMenuPolicy(Qt.CustomContextMenu)
        self.lista.customContextMenuRequested.connect(self._menu_item)
        self.lista.itemDoubleClicked.connect(lambda it: abrir_arquivo(it.data(Qt.UserRole)))
        v.addWidget(self.lista, 1)
        self.vazio = QLabel("Seus prints aparecem aqui.", objectName="Muted")
        self.vazio.setAlignment(Qt.AlignCenter)
        v.addWidget(self.vazio)
        self.statusBar().showMessage(f"{APP_NAME} {__version__} — continua funcionando perto do relógio quando a "
                                     "janela é fechada.")
        self._th = None
        self._recarregar_pendente = False

    def recarregar(self):
        if not self.isVisible():
            self._recarregar_pendente = True
            return
        self.lista.clear()
        itens = historico.itens()[:120]
        self.vazio.setVisible(not itens)
        self._itens = {}
        import time
        for c in itens:
            try:
                quando = time.strftime("%d/%m às %H:%M", time.localtime(os.path.getmtime(c)))
            except OSError:
                quando = ""
            tipo = {".mp4": "Vídeo · ", ".gif": "GIF · "}.get(os.path.splitext(c)[1].lower(), "")
            it = QListWidgetItem(icone("gravar" if c.lower().endswith(".mp4") else "camera", "#a19db6", 64),
                                 tipo + quando)
            it.setData(Qt.UserRole, c)
            it.setToolTip(c)
            self.lista.addItem(it)
            self._itens[c] = it
        if self._th and self._th.isRunning():
            self._th.requestInterruption()
        self._th = _Miniaturas(itens)
        self._th.pronta.connect(self._miniatura)
        self._th.start()

    def _miniatura(self, c, img):
        it = self._itens.get(c)
        if it is not None:
            it.setIcon(QIcon(QPixmap.fromImage(img)))

    def showEvent(self, ev):
        super().showEvent(ev)
        QTimer.singleShot(0, self.recarregar)

    def _menu_item(self, pos):
        it = self.lista.itemAt(pos)
        if not it:
            return
        c = it.data(Qt.UserRole)
        m = QMenu(self)
        if not c.lower().endswith(".mp4"):
            m.addAction("Copiar", lambda: self.ctl.copiar(QImage(c), avisar=True, guardar=False))
            m.addAction("Fixar na tela", lambda: self.ctl.fixar(QImage(c)))
        m.addAction("Abrir", lambda: abrir_arquivo(c))
        m.addAction("Mostrar na pasta", lambda: mostrar_na_pasta(c))
        m.addSeparator()
        m.addAction("Tirar do histórico", lambda: (historico.apagar(c), self.recarregar()))
        m.exec(self.lista.mapToGlobal(pos))

    def configuracoes(self):
        DialogoConfig(self, self.ctl).exec()

    def fechar_para_atualizar(self):
        self.ctl.encerrar(atualizando=True)

    def closeEvent(self, ev):
        ev.ignore()
        self.hide()
        if self.settings.value("avisou_bandeja", "false") != "true":
            self.settings.setValue("avisou_bandeja", "true")
            self.ctl.tray.showMessage(APP_NAME, "O Instantia continua aqui, perto do relógio. Aperte Print Screen "
                                                "para capturar.", self.ctl.icone, 5000)


class DialogoConfig(QDialog):
    def __init__(self, janela, ctl):
        super().__init__(janela)
        self.ctl = ctl
        s = ctl.settings
        self.setWindowTitle("Configurações")
        self.setMinimumWidth(560)
        v = QVBoxLayout(self)
        abas = QTabWidget()
        v.addWidget(abas)

        # Geral
        g = QWidget()
        f = QFormLayout(g)
        self.ck_prt = QCheckBox("Usar a tecla Print Screen para o Instantia")
        self.ck_prt.setChecked(s.value("usar_printscreen", "true") != "false")
        f.addRow(self.ck_prt)
        nota = QLabel("   Assim a Ferramenta de Captura do Windows não abre junto. Alt + Print Screen continua com o "
                      "Windows.", objectName="Muted")
        nota.setWordWrap(True)
        f.addRow(nota)
        self.ck_ini = QCheckBox("Iniciar com o Windows (fica perto do relógio)")
        self.ck_ini.setChecked(s.value("iniciar_windows", "true") != "false")
        f.addRow(self.ck_ini)
        self.cb_tema = QComboBox()
        for txt, val in (("Igual ao Windows", "auto"), ("Claro", "claro"), ("Escuro", "escuro")):
            self.cb_tema.addItem(txt, val)
        self.cb_tema.setCurrentIndex(max(0, self.cb_tema.findData(s.value("tema", "auto"))))
        f.addRow("Tema:", self.cb_tema)
        self.ck_upd = QCheckBox("Procurar atualizações automaticamente")
        self.ck_upd.setChecked(s.value("auto_atualizar", "true") != "false")
        f.addRow(self.ck_upd)
        abas.addTab(g, "Geral")

        # Captura
        c = QWidget()
        f = QFormLayout(c)
        linha = QHBoxLayout()
        self.ed_pasta = QLineEdit(ctl.pasta_salvar())
        bt = QPushButton("Escolher…")
        bt.clicked.connect(self._escolher_pasta)
        linha.addWidget(self.ed_pasta)
        linha.addWidget(bt)
        f.addRow("Salvar em:", linha)
        self.cb_fmt = QComboBox()
        self.cb_fmt.addItem("PNG (melhor qualidade)", "png")
        self.cb_fmt.addItem("JPG (arquivo menor)", "jpg")
        self.cb_fmt.setCurrentIndex(max(0, self.cb_fmt.findData(s.value("formato", "png"))))
        f.addRow("Formato:", self.cb_fmt)
        self.ck_copiar_salvar = QCheckBox("Ao salvar, também copiar")
        self.ck_copiar_salvar.setChecked(s.value("copiar_ao_salvar", "true") != "false")
        f.addRow(self.ck_copiar_salvar)
        self.cb_ferr = QComboBox()
        for txt, val in (("Seta", "seta"), ("Retângulo", "retangulo"), ("Caneta", "caneta"),
                         ("Mover / ajustar", "")):
            self.cb_ferr.addItem(txt, val)
        self.cb_ferr.setCurrentIndex(max(0, self.cb_ferr.findData(s.value("ferramenta_inicial", "seta"))))
        f.addRow("Ferramenta ao abrir:", self.cb_ferr)
        self.ck_hist = QCheckBox("Guardar os prints no histórico")
        self.ck_hist.setChecked(s.value("historico", "true") != "false")
        self.sp_hist = QSpinBox(minimum=10, maximum=5000, value=int(s.value("historico_limite", 300)))
        self.sp_hist.setSuffix(" itens")
        f.addRow(self.ck_hist)
        f.addRow("Guardar até:", self.sp_hist)
        abas.addTab(c, "Captura")

        # Gravação
        gr = QWidget()
        f = QFormLayout(gr)
        self.cb_fps = QComboBox()
        for fps in (15, 30, 60):
            self.cb_fps.addItem(f"{fps} quadros por segundo", fps)
        self.cb_fps.setCurrentIndex(max(0, self.cb_fps.findData(int(s.value("grav_fps", 30)))))
        f.addRow("Fluidez:", self.cb_fps)
        self.cb_mic = QComboBox()
        self.cb_mic.addItem("Sem som", "")
        atual = s.value("grav_micro", "")
        try:
            from .gravacao import microfones
            for m in microfones():
                self.cb_mic.addItem(m, m)
        except Exception:  # noqa: BLE001
            pass
        if atual and self.cb_mic.findData(atual) < 0:
            self.cb_mic.addItem(atual, atual)
        self.cb_mic.setCurrentIndex(max(0, self.cb_mic.findData(atual)))
        f.addRow("Microfone:", self.cb_mic)
        nota = QLabel("A lista de microfones aparece depois da primeira gravação (quando o gravador é baixado).",
                      objectName="Muted")
        nota.setWordWrap(True)
        f.addRow(nota)
        self.ck_cursor = QCheckBox("Mostrar o cursor do mouse no vídeo")
        self.ck_cursor.setChecked(s.value("grav_cursor", "true") != "false")
        f.addRow(self.ck_cursor)
        abas.addTab(gr, "Gravação")

        # Sobre
        so = QWidget()
        sv = QVBoxLayout(so)
        sv.addWidget(QLabel(f"<h3>{APP_NAME} {__version__}</h3><p>Capturador de tela.</p>"
                            f"<p>{COPYRIGHT} · <a href='mailto:{EMAIL}'>{EMAIL}</a></p>"
                            "<p style='color:gray'>OCR do Windows · gravação com FFmpeg (baixado na primeira "
                            "gravação).</p>"))
        bt_upd = QPushButton("Procurar atualizações agora")
        bt_upd.clicked.connect(lambda: ctl.atualizador.verificar(silencioso=False))
        sv.addWidget(bt_upd)
        sv.addStretch()
        abas.addTab(so, "Sobre")

        linha = QHBoxLayout()
        linha.addStretch()
        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        ok = QPushButton("Salvar", objectName="Primary")
        ok.clicked.connect(self.accept)
        linha.addWidget(cancelar)
        linha.addWidget(ok)
        v.addLayout(linha)

    def _escolher_pasta(self):
        d = QFileDialog.getExistingDirectory(self, "Salvar prints em", self.ed_pasta.text())
        if d:
            self.ed_pasta.setText(d)

    def accept(self):
        s = self.ctl.settings
        b = lambda v: "true" if v else "false"  # noqa: E731
        s.setValue("usar_printscreen", b(self.ck_prt.isChecked()))
        s.setValue("iniciar_windows", b(self.ck_ini.isChecked()))
        s.setValue("tema", self.cb_tema.currentData())
        s.setValue("auto_atualizar", b(self.ck_upd.isChecked()))
        s.setValue("pasta_salvar", self.ed_pasta.text().strip())
        s.setValue("formato", self.cb_fmt.currentData())
        s.setValue("copiar_ao_salvar", b(self.ck_copiar_salvar.isChecked()))
        s.setValue("ferramenta_inicial", self.cb_ferr.currentData())
        s.setValue("historico", b(self.ck_hist.isChecked()))
        s.setValue("historico_limite", self.sp_hist.value())
        s.setValue("grav_fps", self.cb_fps.currentData())
        s.setValue("grav_micro", self.cb_mic.currentData())
        s.setValue("grav_cursor", b(self.ck_cursor.isChecked()))
        self.ctl.aplicar_configuracoes()
        super().accept()


__all__ = ["Janela", "DialogoConfig", "abrir_arquivo", "mostrar_na_pasta"]
