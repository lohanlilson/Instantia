"""A tela congelada: escolher a área (ou a janela, com um clique) e editar ali mesmo.

Teclas: Esc cancela · Enter / Ctrl+C copia · Ctrl+S salva · Ctrl+Shift+S salvar como · Ctrl+Z / Ctrl+Y ·
Delete apaga a marcação escolhida · setas movem a seleção (Shift = 10 px) · letras escolhem a ferramenta.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QColor, QCursor, QFont, QImage, QKeySequence, QPainter, QPainterPath, QPen,
                           QShortcut)
from PySide6.QtWidgets import (QColorDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QToolButton,
                               QWidget)

from . import anotacoes as A
from .icones import bolinha_cor, espessura_icone, icone

ACENTO = QColor("#8b5cff")
ESCURECER = QColor(8, 6, 20, 120)
ALCA = 7

FERRAMENTAS = [  # (id, dica, tecla)
    (None, "Mover / ajustar (V)", "V"), ("seta", "Seta (A)", "A"), ("retangulo", "Retângulo (R)", "R"),
    ("elipse", "Elipse (E)", "E"), ("linha", "Linha (L)", "L"), ("caneta", "Caneta (P)", "P"),
    ("marcatexto", "Marca-texto (M)", "M"), ("texto", "Texto (T)", "T"), ("numero", "Numeração 1, 2, 3… (N)", "N"),
    ("borrao", "Borrão (B)", "B"),
]
ESPESSURAS = [2, 4, 7]


def _botao(pai, nome_icone, dica, cb=None, checavel=False):
    b = QToolButton(pai)
    b.setIcon(icone(nome_icone or "mover"))
    b.setIconSize(QSize(20, 20))
    b.setToolTip(dica)
    b.setCheckable(checavel)
    b.setAutoRaise(True)
    b.setFocusPolicy(Qt.NoFocus)
    b.setCursor(Qt.PointingHandCursor)
    if cb:
        b.clicked.connect(cb)
    return b


class Barra(QFrame):
    """Barra de ferramentas que aparece junto da área escolhida."""

    def __init__(self, sel: "Seletor"):
        super().__init__(sel)
        self.sel = sel
        self.setObjectName("BarraInstantia")
        self.setStyleSheet("""
            QFrame#BarraInstantia { background: rgba(28,26,38,0.97); border: 1px solid rgba(255,255,255,0.10);
                border-radius: 12px; }
            QToolButton { border: none; border-radius: 8px; padding: 5px; background: transparent; }
            QToolButton:hover { background: rgba(255,255,255,0.12); }
            QToolButton:checked { background: #8b5cff; }
            QToolButton:disabled { opacity: 0.4; }
            QFrame#Sep { background: rgba(255,255,255,0.14); }
            QLabel { color: #d8d5e6; font-size: 12px; padding: 0 6px; }
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 5, 6, 5)
        lay.setSpacing(2)
        self.bt_ferr = {}
        for fid, dica, _ in FERRAMENTAS:
            b = _botao(self, fid, dica, checavel=True)
            b.clicked.connect(lambda _=False, f=fid: sel.escolher_ferramenta(f))
            self.bt_ferr[fid] = b
            lay.addWidget(b)
        lay.addWidget(self._sep())
        self.bt_cor = _botao(self, None, "Cor", self._menu_cor)
        self.bt_esp = _botao(self, None, "Espessura", self._trocar_espessura)
        lay.addWidget(self.bt_cor)
        lay.addWidget(self.bt_esp)
        lay.addWidget(self._sep())
        self.bt_desf = _botao(self, "desfazer", "Desfazer (Ctrl+Z)", sel.desfazer)
        self.bt_ref = _botao(self, "refazer", "Refazer (Ctrl+Y)", sel.refazer)
        lay.addWidget(self.bt_desf)
        lay.addWidget(self.bt_ref)
        lay.addWidget(self._sep())
        self.bt_ocultar = _botao(self, "ocultar", "Ocultar dados: borra CPF, CNPJ, e-mail, telefone, valores, "
                                                  "linha digitável e cartões (H)", sel.ocultar_dados)
        self.bt_ocr = _botao(self, "ocr", "Copiar o texto do print (O)", lambda: sel.concluir("texto"))
        self.bt_fixar = _botao(self, "fixar", "Fixar na tela (F)", lambda: sel.concluir("fixar"))
        self.bt_salvar = _botao(self, "salvar", "Salvar (Ctrl+S) — Ctrl+Shift+S para escolher onde",
                                lambda: sel.concluir("salvar"))
        self.bt_copiar = _botao(self, "copiar", "Copiar (Enter / Ctrl+C)", lambda: sel.concluir("copiar"))
        self.bt_fechar = _botao(self, "fechar", "Cancelar (Esc)", sel.sessao.cancelar)
        for b in (self.bt_ocultar, self.bt_ocr, self.bt_fixar, self.bt_salvar, self.bt_copiar, self.bt_fechar):
            lay.addWidget(b)
        self.aviso = QLabel("", self)
        self.aviso.hide()
        lay.addWidget(self.aviso)
        self.atualizar()

    def _sep(self):
        s = QFrame(self)
        s.setObjectName("Sep")
        s.setFixedSize(1, 22)
        return s

    def atualizar(self):
        s = self.sel
        for fid, b in self.bt_ferr.items():
            b.setChecked(fid == s.ferramenta)
        self.bt_cor.setIcon(bolinha_cor(s.cor))
        self.bt_esp.setIcon(espessura_icone(s.espessura))
        self.bt_desf.setEnabled(bool(s.anots))
        self.bt_ref.setEnabled(bool(s.desfeitos))
        self.adjustSize()

    def mostrar_aviso(self, texto):
        self.aviso.setText(texto)
        self.aviso.setVisible(bool(texto))
        self.adjustSize()
        self.sel.posicionar_barra()

    def _menu_cor(self):
        m = PaletaCores(self.sel, self.bt_cor.mapTo(self.sel, QPoint(0, self.bt_cor.height() + 4)))
        m.show()

    def _trocar_espessura(self):
        s = self.sel
        s.espessura = ESPESSURAS[(ESPESSURAS.index(s.espessura) + 1) % len(ESPESSURAS)] if s.espessura in ESPESSURAS else 4
        if s.escolhida is not None:
            s.escolhida.espessura = s.espessura
            if isinstance(s.escolhida, A.Texto):
                s.escolhida.tamanho = max(14, int(s.espessura * 4.5))
            s.update()
        self.atualizar()


class PaletaCores(QFrame):
    def __init__(self, sel: "Seletor", pos: QPoint):
        super().__init__(sel)
        self.sel = sel
        self.setStyleSheet("QFrame { background: rgba(28,26,38,0.98); border-radius: 10px; }"
                           "QToolButton { border: none; border-radius: 6px; padding: 3px; }"
                           "QToolButton:hover { background: rgba(255,255,255,0.14); }")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(2)
        for c in A.CORES:
            b = QToolButton(self)
            b.setIcon(bolinha_cor(c, 20))
            b.setIconSize(QSize(20, 20))
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(lambda _=False, cc=c: self._usar(cc))
            lay.addWidget(b)
        mais = QToolButton(self)
        mais.setText("…")
        mais.setStyleSheet("color: white; font-weight: 700;")
        mais.setToolTip("Outra cor")
        mais.clicked.connect(self._outra)
        lay.addWidget(mais)
        self.adjustSize()
        x = min(max(0, pos.x()), sel.width() - self.width())
        y = pos.y() if pos.y() + self.height() < sel.height() else pos.y() - self.height() - 40
        self.move(x, y)
        self.raise_()

    def _usar(self, c):
        self.sel.definir_cor(c)
        self.close()
        self.deleteLater()

    def _outra(self):
        c = QColorDialog.getColor(QColor(self.sel.cor), self.sel, "Cor")
        if c.isValid():
            self._usar(c.name())


class Lupa:
    """Lupa com a posição e a cor do pixel embaixo do cursor (para acertar a seleção no pixel)."""
    TAM = 120
    ZOOM = 8

    @staticmethod
    def desenhar(g: QPainter, img: QImage, escala: float, pos: QPoint, limites: QRect):
        n = Lupa.TAM // Lupa.ZOOM
        cx, cy = int(pos.x() * escala), int(pos.y() * escala)
        pedaco = img.copy(cx - n // 2, cy - n // 2, n, n)
        x = pos.x() + 22
        y = pos.y() + 22
        if x + Lupa.TAM + 46 > limites.right():
            x = pos.x() - 22 - Lupa.TAM - 46
        if y + Lupa.TAM + 36 > limites.bottom():
            y = pos.y() - 22 - Lupa.TAM - 36
        r = QRect(x, y, Lupa.TAM, Lupa.TAM)
        g.save()
        path = QPainterPath()
        path.addRoundedRect(QRectF(r), 10, 10)
        g.setClipPath(path)
        g.drawImage(r, pedaco)
        g.setClipping(False)
        g.setPen(QPen(QColor(139, 92, 255, 200), 1))
        meio = Lupa.TAM / 2
        g.drawLine(QPointF(x + meio, y), QPointF(x + meio, y + Lupa.TAM))
        g.drawLine(QPointF(x, y + meio), QPointF(x + Lupa.TAM, y + meio))
        g.setPen(QPen(QColor(255, 255, 255, 230), 2))
        g.setBrush(Qt.NoBrush)
        g.drawRoundedRect(QRectF(r), 10, 10)
        cor = QColor(img.pixel(min(max(cx, 0), img.width() - 1), min(max(cy, 0), img.height() - 1)))
        info = QRect(x, y + Lupa.TAM + 4, Lupa.TAM + 46, 30)
        g.setPen(Qt.NoPen)
        g.setBrush(QColor(28, 26, 38, 235))
        g.drawRoundedRect(QRectF(info), 7, 7)
        g.setBrush(cor)
        g.drawRoundedRect(QRectF(info.x() + 6, info.y() + 7, 16, 16), 3, 3)
        f = QFont("Segoe UI")
        f.setPixelSize(11)
        g.setFont(f)
        g.setPen(QColor("#ffffff"))
        g.drawText(info.adjusted(27, 0, -4, 0), Qt.AlignVCenter | Qt.AlignLeft, f"{cx}, {cy}  {cor.name().upper()}")
        g.restore()


class Seletor(QWidget):
    """Uma tela congelada (há um Seletor por monitor)."""
    pronto = Signal()

    def __init__(self, sessao, foto):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.sessao = sessao
        self.foto = foto
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.estado = "escolhendo"          # escolhendo | arrastando | editando
        self.sel: QRect | None = None
        self.hover: QRect | None = None
        self.mouse = QPoint(-100, -100)
        self.inicio = QPoint()
        self.ferramenta = None
        self.cor = sessao.cor
        self.espessura = sessao.espessura
        self.anots: list[A.Anot] = []
        self.desfeitos: list = []
        self.numero = 1
        self.atual: A.Anot | None = None
        self.escolhida: A.Anot | None = None
        self.arraste = None                 # ("mover_sel"|"alca"|"mover_anot", dados)
        self.editor_texto: QLineEdit | None = None
        self.barra: Barra | None = None
        self.ativo = True
        self.setGeometry(foto.geo)
        for seq, fn in (("Ctrl+Z", self.desfazer), ("Ctrl+Y", self.refazer), ("Ctrl+Shift+Z", self.refazer)):
            QShortcut(QKeySequence(seq), self, fn)

    # ------------------------------------------------------------------ estado
    def desativar(self):
        """Outro monitor recebeu a seleção: este só fica escuro."""
        self.ativo = False
        self.hover = None
        self.update()

    def escolher_ferramenta(self, f):
        self._fechar_editor_texto()
        self.ferramenta = f
        self.escolhida = None
        if self.barra:
            self.barra.atualizar()
        self.setCursor(Qt.ArrowCursor if f is None else Qt.CrossCursor)
        self.update()

    def definir_cor(self, c):
        self.cor = c
        self.sessao.cor = c
        if self.escolhida is not None:
            self.escolhida.cor = QColor(c)
        if self.editor_texto is not None and self.atual is not None:
            self.atual.cor = QColor(c)
            self._estilo_editor()
        if self.barra:
            self.barra.atualizar()
        self.update()

    def adicionar(self, a: A.Anot):
        self.anots.append(a)
        self.desfeitos.clear()
        if self.barra:
            self.barra.atualizar()
        self.update()

    def desfazer(self):
        self._fechar_editor_texto()
        if self.anots:
            a = self.anots.pop()
            self.desfeitos.append(a)
            if isinstance(a, A.Numero):
                self.numero = max(1, a.n)
            if a is self.escolhida:
                self.escolhida = None
        if self.barra:
            self.barra.atualizar()
        self.update()

    def refazer(self):
        if self.desfeitos:
            a = self.desfeitos.pop()
            self.anots.append(a)
            if isinstance(a, A.Numero):
                self.numero = a.n + 1
        if self.barra:
            self.barra.atualizar()
        self.update()

    def definir_selecao(self, r: QRect):
        self.sel = r.normalized().intersected(self.rect())
        if self.sel.width() < 2 or self.sel.height() < 2:
            self.sel = QRect(self.sel.topLeft(), QSize(max(2, self.sel.width()), max(2, self.sel.height())))
        self.posicionar_barra()
        self.update()

    def comecar_edicao(self):
        self.estado = "editando"
        self.sessao.selecionou(self)
        if self.sessao.modo != "imagem":
            QTimer.singleShot(0, lambda: self.concluir(self.sessao.modo))
            return
        if self.barra is None:
            self.barra = Barra(self)
        self.ferramenta = self.sessao.ferramenta_inicial
        self.barra.atualizar()
        self.barra.show()
        self.posicionar_barra()
        self.setCursor(Qt.ArrowCursor if self.ferramenta is None else Qt.CrossCursor)

    def posicionar_barra(self):
        if not self.barra or not self.sel:
            return
        b = self.barra
        b.adjustSize()
        x = self.sel.right() - b.width() + 1
        x = max(4, min(x, self.width() - b.width() - 4))
        y = self.sel.bottom() + 8
        if y + b.height() > self.height() - 4:
            y = self.sel.top() - b.height() - 8
            if y < 4:
                y = self.sel.bottom() - b.height() - 8
        b.move(x, y)
        b.raise_()

    def concluir(self, acao):
        self._fechar_editor_texto()
        if not self.sel:
            return
        self.sessao.concluir(self, acao)

    def imagem_final(self, com_marcacoes=True) -> QImage:
        return A.renderizar(self.foto.imagem, self.sel, self.anots if com_marcacoes else [], self.foto.escala)

    # ------------------------------------------------------------------ ocultar dados
    def ocultar_dados(self):
        if not self.sel:
            return
        from .sensiveis import ThreadOcultar
        if self.barra:
            self.barra.mostrar_aviso("Procurando dados…")
            self.barra.bt_ocultar.setEnabled(False)
        self._th = ThreadOcultar(self.imagem_final(False))
        self._th.terminou.connect(self._ocultar_resultado)
        self._th.start()

    def _ocultar_resultado(self, achados, erro):
        if not self.isVisible() or self.sel is None:
            return
        if self.barra:
            self.barra.bt_ocultar.setEnabled(True)
        if erro:
            if self.barra:
                self.barra.mostrar_aviso(erro)
            return
        e = self.foto.escala
        novos = 0
        for tipo, r in achados:
            rr = QRectF(self.sel.x() + r.x() / e - 2, self.sel.y() + r.y() / e - 2, r.width() / e + 4, r.height() / e + 4)
            if any(isinstance(a, A.Borrao) and a.r.contains(rr.center()) for a in self.anots):
                continue
            self.anots.append(A.Borrao(rr, automatico=True))
            novos += 1
        self.desfeitos.clear()
        if self.barra:
            self.barra.atualizar()
            tipos = sorted({t for t, _ in achados})
            self.barra.mostrar_aviso(f"{novos} dado(s) ocultado(s): {', '.join(tipos)}" if novos
                                     else "Nenhum dado sensível encontrado")
            QTimer.singleShot(5000, lambda: self.barra and self.barra.mostrar_aviso(""))
        self.update()

    # ------------------------------------------------------------------ texto
    def _estilo_editor(self):
        if not self.editor_texto or not self.atual:
            return
        a = self.atual
        f = a.fonte()
        self.editor_texto.setFont(f)
        self.editor_texto.setStyleSheet(f"QLineEdit {{ background: rgba(255,255,255,0.10); color: {a.cor.name()};"
                                        f" border: 1px dashed {ACENTO.name()}; padding: 0 2px; }}")

    def _abrir_editor_texto(self, a: A.Texto):
        self.atual = a
        ed = QLineEdit(self)
        self.editor_texto = ed
        self._estilo_editor()
        ed.setText(a.texto)
        ed.move(int(a.pos.x()), int(a.pos.y()))
        ed.setMinimumWidth(160)
        ed.resize(max(160, int(a.area().width() + 40)), int(a.area().height() + 6))
        ed.textChanged.connect(lambda t: (setattr(a, "texto", t), ed.resize(max(160, int(a.area().width() + 40)), ed.height())))
        ed.installEventFilter(self)
        ed.show()
        ed.setFocus()

    def eventFilter(self, obj, ev):
        if obj is self.editor_texto and ev.type() == QEvent.KeyPress:
            if ev.key() == Qt.Key_Escape:
                if self.atual:
                    self.atual.texto = ""
                self._fechar_editor_texto()
                return True
            if ev.key() in (Qt.Key_Return, Qt.Key_Enter):   # termina o texto (não conclui o print)
                self._fechar_editor_texto()
                return True
        return super().eventFilter(obj, ev)

    def _fechar_editor_texto(self):
        ed, a = self.editor_texto, self.atual
        if ed is None:
            return
        self.editor_texto = None
        self.atual = None
        ed.hide()
        ed.deleteLater()
        if a is not None and a.valida() and a not in self.anots:
            self.adicionar(a)
        elif a is not None and not a.valida() and a in self.anots:
            self.anots.remove(a)
        self.setFocus()
        self.update()

    # ------------------------------------------------------------------ geometria
    def _alcas(self) -> dict:
        r = self.sel
        if not r:
            return {}
        cx, cy = r.center().x(), r.center().y()
        pts = {"tl": QPoint(r.left(), r.top()), "t": QPoint(cx, r.top()), "tr": QPoint(r.right(), r.top()),
               "r": QPoint(r.right(), cy), "br": QPoint(r.right(), r.bottom()), "b": QPoint(cx, r.bottom()),
               "bl": QPoint(r.left(), r.bottom()), "l": QPoint(r.left(), cy)}
        return {k: QRect(p.x() - ALCA, p.y() - ALCA, 2 * ALCA + 1, 2 * ALCA + 1) for k, p in pts.items()}

    def _alca_em(self, p: QPoint):
        for k, r in self._alcas().items():
            if r.contains(p):
                return k
        return None

    def _janela_em(self, p: QPoint) -> QRect:
        for r in self.foto.janelas:
            if r.contains(p):
                return r
        return self.rect()

    def _anot_em(self, p: QPointF):
        for a in reversed(self.anots):
            if a.contem(p):
                return a
        return None

    # ------------------------------------------------------------------ desenho
    def paintEvent(self, ev):
        g = QPainter(self)
        g.setRenderHint(QPainter.Antialiasing)
        g.drawImage(self.rect(), self.foto.imagem)
        sel = self.sel if self.estado != "escolhendo" else None
        fora = QPainterPath()
        fora.addRect(QRectF(self.rect()))
        if sel and self.ativo:
            dentro = QPainterPath()
            dentro.addRect(QRectF(sel))
            fora = fora.subtracted(dentro)
        g.fillPath(fora, ESCURECER if self.ativo else QColor(8, 6, 20, 150))
        if not self.ativo:
            return
        if self.estado == "escolhendo" and self.hover is not None:
            g.setPen(QPen(ACENTO, 2))
            g.setBrush(QColor(139, 92, 255, 28))
            g.drawRect(QRectF(self.hover).adjusted(1, 1, -1, -1))
            self._rotulo_tamanho(g, self.hover)
        if sel:
            g.save()
            g.setClipRect(sel)
            for a in self.anots:
                if isinstance(a, A.Borrao):
                    a.desenhar(g, self.foto.imagem, self.foto.escala)
            for a in self.anots:
                if not isinstance(a, A.Borrao):
                    a.desenhar(g, self.foto.imagem, self.foto.escala)
            if self.atual is not None and self.atual not in self.anots and not isinstance(self.atual, A.Texto):
                self.atual.desenhar(g, self.foto.imagem, self.foto.escala)
            if self.escolhida is not None:
                g.setPen(QPen(QColor("#ffffff"), 1, Qt.DashLine))
                g.setBrush(Qt.NoBrush)
                g.drawRect(self.escolhida.area().adjusted(-4, -4, 4, 4))
            g.restore()
            g.setPen(QPen(ACENTO, 1.5))
            g.setBrush(Qt.NoBrush)
            g.drawRect(QRectF(sel).adjusted(0.5, 0.5, -0.5, -0.5))
            if self.estado == "editando" and self.ferramenta is None:
                g.setPen(QPen(QColor("#ffffff"), 1.2))
                g.setBrush(ACENTO)
                for r in self._alcas().values():
                    g.drawRoundedRect(QRectF(r).adjusted(2, 2, -2, -2), 2, 2)
            self._rotulo_tamanho(g, sel)
        if self.estado in ("escolhendo", "arrastando") and self.rect().contains(self.mouse):
            if self.estado == "escolhendo":
                g.setPen(QPen(QColor(255, 255, 255, 90), 1, Qt.DashLine))
                g.drawLine(QPointF(self.mouse.x() + .5, 0), QPointF(self.mouse.x() + .5, self.height()))
                g.drawLine(QPointF(0, self.mouse.y() + .5), QPointF(self.width(), self.mouse.y() + .5))
            Lupa.desenhar(g, self.foto.imagem, self.foto.escala, self.mouse, self.rect())
            if self.estado == "escolhendo" and self.sessao.dica:
                self._dica(g)

    def _rotulo_tamanho(self, g: QPainter, r: QRect):
        e = self.foto.escala
        txt = f"{round(r.width() * e)} × {round(r.height() * e)}"
        f = QFont("Segoe UI")
        f.setPixelSize(12)
        f.setBold(True)
        g.setFont(f)
        w = g.fontMetrics().horizontalAdvance(txt) + 16
        y = r.top() - 26 if r.top() > 30 else r.top() + 6
        caixa = QRectF(r.left(), y, w, 22)
        g.setPen(Qt.NoPen)
        g.setBrush(QColor(28, 26, 38, 225))
        g.drawRoundedRect(caixa, 6, 6)
        g.setPen(QColor("#ffffff"))
        g.drawText(caixa, Qt.AlignCenter, txt)

    def _dica(self, g: QPainter):
        txt = self.sessao.dica
        f = QFont("Segoe UI")
        f.setPixelSize(13)
        g.setFont(f)
        w = g.fontMetrics().horizontalAdvance(txt) + 28
        caixa = QRectF((self.width() - w) / 2, 24, w, 34)
        if caixa.contains(QPointF(self.mouse)):
            caixa.moveTop(self.height() - 64)
        g.setPen(Qt.NoPen)
        g.setBrush(QColor(28, 26, 38, 225))
        g.drawRoundedRect(caixa, 10, 10)
        g.setPen(QColor("#ffffff"))
        g.drawText(caixa, Qt.AlignCenter, txt)

    # ------------------------------------------------------------------ mouse
    def mousePressEvent(self, ev):
        if not self.ativo:
            self.sessao.cancelar()
            return
        p = ev.position().toPoint()
        pf = ev.position()
        if ev.button() == Qt.RightButton:
            if self.estado == "editando" and self.sessao.modo == "imagem":
                self._fechar_editor_texto()
                self.estado = "escolhendo"          # volta a escolher a área
                self.sel = None
                self.anots.clear()
                self.desfeitos.clear()
                self.numero = 1
                if self.barra:
                    self.barra.hide()
                self.hover = self._janela_em(p)
                self.setCursor(Qt.CrossCursor)
                self.sessao.reativar_todos()
                self.update()
            else:
                self.sessao.cancelar()
            return
        if ev.button() != Qt.LeftButton:
            return
        if self.estado == "escolhendo":
            self.inicio = p
            self.estado = "arrastando"
            self.sel = QRect(p, p)
            return
        if self.estado != "editando":
            return
        self._fechar_editor_texto()
        if self.ferramenta is None:
            alca = self._alca_em(p)
            if alca:
                self.arraste = ("alca", alca, QRect(self.sel))
                return
            a = self._anot_em(pf) if self.sel.contains(p) else None
            if a is not None:
                self.escolhida = a
                self.arraste = ("mover_anot", a, pf)
                self.update()
                return
            self.escolhida = None
            if self.sel.contains(p):
                self.arraste = ("mover_sel", p - self.sel.topLeft())
            else:                                   # fora: nova seleção (mantém as marcações)
                self.estado = "arrastando"
                self.inicio = p
                self.sel = QRect(p, p)
                if self.barra:
                    self.barra.hide()
            self.update()
            return
        # ferramenta de desenho
        if self.ferramenta == "texto":
            a = self._anot_em(pf)
            if isinstance(a, A.Texto):              # clicou num texto existente: edita
                self.anots.remove(a)
                self._abrir_editor_texto(a)
                return
            t = A.nova("texto", self.cor, self.espessura, pf)
            t.pos = QPointF(pf.x(), pf.y() - t.area().height() / 2)
            self._abrir_editor_texto(t)
            return
        self.atual = A.nova(self.ferramenta, self.cor, self.espessura, pf, self.numero)
        self.arraste = ("desenhar", pf)
        if self.ferramenta == "numero":
            self.adicionar(self.atual)
            self.numero += 1
            self.atual = None
            self.arraste = None
        self.update()

    def mouseMoveEvent(self, ev):
        p = ev.position().toPoint()
        pf = ev.position()
        self.mouse = p
        if not self.ativo:
            return
        shift = bool(ev.modifiers() & Qt.ShiftModifier)
        if self.estado == "escolhendo":
            self.hover = self._janela_em(p)
            self.sessao.mouse_em(self)
        elif self.estado == "arrastando":
            r = QRect(self.inicio, p).normalized()
            if shift:
                lado = max(r.width(), r.height())
                r = QRect(self.inicio, QPoint(self.inicio.x() + (lado if p.x() >= self.inicio.x() else -lado),
                                              self.inicio.y() + (lado if p.y() >= self.inicio.y() else -lado))).normalized()
            self.sel = r.intersected(self.rect())
        elif self.estado == "editando":
            if self.arraste:
                tipo = self.arraste[0]
                if tipo == "desenhar" and self.atual is not None:
                    self.atual.editando(self.arraste[1], pf, shift)
                elif tipo == "mover_anot":
                    a, ultimo = self.arraste[1], self.arraste[2]
                    a.mover(pf - ultimo)
                    self.arraste = ("mover_anot", a, pf)
                elif tipo == "mover_sel":
                    tl = p - self.arraste[1]
                    tl.setX(max(0, min(tl.x(), self.width() - self.sel.width())))
                    tl.setY(max(0, min(tl.y(), self.height() - self.sel.height())))
                    self.sel.moveTopLeft(tl)
                    self.posicionar_barra()
                elif tipo == "alca":
                    k, orig = self.arraste[1], self.arraste[2]
                    r = QRect(orig)
                    if "l" in k:
                        r.setLeft(p.x())
                    if "r" in k:
                        r.setRight(p.x())
                    if "t" in k:
                        r.setTop(p.y())
                    if "b" in k and k != "tl":
                        r.setBottom(p.y())
                    self.sel = r.normalized().intersected(self.rect())
                    self.posicionar_barra()
            elif self.ferramenta is None:
                alca = self._alca_em(p)
                cursores = {"tl": Qt.SizeFDiagCursor, "br": Qt.SizeFDiagCursor, "tr": Qt.SizeBDiagCursor,
                            "bl": Qt.SizeBDiagCursor, "t": Qt.SizeVerCursor, "b": Qt.SizeVerCursor,
                            "l": Qt.SizeHorCursor, "r": Qt.SizeHorCursor}
                if alca:
                    self.setCursor(cursores[alca])
                elif self.sel.contains(p):
                    self.setCursor(Qt.SizeAllCursor if self._anot_em(pf) is None else Qt.OpenHandCursor)
                else:
                    self.setCursor(Qt.CrossCursor)
        self.update()

    def mouseReleaseEvent(self, ev):
        if ev.button() != Qt.LeftButton or not self.ativo:
            return
        p = ev.position().toPoint()
        if self.estado == "arrastando":
            r = QRect(self.inicio, p).normalized()
            if r.width() < 4 and r.height() < 4:       # só um clique: a janela embaixo (ou a tela inteira)
                r = self._janela_em(p)
            if self.sel and self.sel.width() >= 4 and self.sel.height() >= 4:
                r = self.sel
            self.definir_selecao(r)
            self.comecar_edicao()
            self.update()
            return
        if self.estado == "editando" and self.arraste:
            tipo = self.arraste[0]
            if tipo == "desenhar" and self.atual is not None:
                if self.atual.valida():
                    self.adicionar(self.atual)
                self.atual = None
            self.arraste = None
            self.update()

    def mouseDoubleClickEvent(self, ev):
        if self.estado == "editando" and self.ferramenta is None and self.sel and self.sel.contains(ev.position().toPoint()) \
                and self._anot_em(ev.position()) is None:
            self.concluir("copiar")

    # ------------------------------------------------------------------ teclado
    def keyPressEvent(self, ev):
        k = ev.key()
        mod = ev.modifiers()
        ctrl = bool(mod & Qt.ControlModifier)
        if k == Qt.Key_Escape:
            if self.escolhida is not None:
                self.escolhida = None
                self.update()
                return
            self.sessao.cancelar()
            return
        if self.estado != "editando":
            if k in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):     # Enter sem seleção: tela inteira
                self.definir_selecao(self.rect())
                self.comecar_edicao()
            return
        if k in (Qt.Key_Return, Qt.Key_Enter) or (ctrl and k == Qt.Key_C):
            self.concluir("copiar")
        elif ctrl and k == Qt.Key_S:
            self.concluir("salvar_como" if mod & Qt.ShiftModifier else "salvar")
        elif k in (Qt.Key_Delete, Qt.Key_Backspace) and self.escolhida is not None:
            self.anots.remove(self.escolhida)
            self.desfeitos.append(self.escolhida)
            self.escolhida = None
            if self.barra:
                self.barra.atualizar()
            self.update()
        elif k in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            d = 10 if mod & Qt.ShiftModifier else 1
            dx = {Qt.Key_Left: -d, Qt.Key_Right: d}.get(k, 0)
            dy = {Qt.Key_Up: -d, Qt.Key_Down: d}.get(k, 0)
            if self.escolhida is not None:
                self.escolhida.mover(QPointF(dx, dy))
            elif mod & Qt.AltModifier:                 # Alt + setas: muda o tamanho
                self.definir_selecao(self.sel.adjusted(0, 0, dx, dy))
            else:
                self.definir_selecao(self.sel.translated(dx, dy))
            self.update()
        elif not ctrl:
            letra = ev.text().upper()
            for fid, _, tecla in FERRAMENTAS:
                if letra == tecla:
                    self.escolher_ferramenta(fid)
                    return
            if letra == "H":
                self.ocultar_dados()
            elif letra == "O":
                self.concluir("texto")
            elif letra == "F":
                self.concluir("fixar")


class Sessao:
    """Uma captura: congela as telas, espera a escolha e devolve a imagem (ou o retângulo, na gravação)."""

    def __init__(self, ao_concluir, modo="imagem", cor="#e5243b", espessura=4, dica="", ferramenta_inicial="seta"):
        from .captura import fotografar
        self.ao_concluir = ao_concluir          # fn(acao, imagem: QImage|None, seletor)
        self.modo = modo                        # imagem | texto | gravar | ocultar
        self.cor = cor
        self.espessura = espessura
        self.ferramenta_inicial = ferramenta_inicial
        self.dica = dica or {"imagem": "Arraste para escolher a área · clique numa janela · Enter = tela inteira · Esc cancela",
                             "texto": "Escolha a área com o texto que você quer copiar · Esc cancela",
                             "gravar": "Escolha a área para gravar · clique numa janela · Enter = tela inteira · Esc cancela"}.get(modo, "")
        self.fotos = fotografar()
        self.seletores = [Seletor(self, f) for f in self.fotos]
        self.terminada = False

    def mostrar(self):
        alvo = None
        from .captura import tela_do_cursor
        tc = tela_do_cursor()
        for s in self.seletores:
            s.show()
            if s.windowHandle():
                s.windowHandle().setScreen(s.foto.tela)
            s.setGeometry(s.foto.geo)
            s.raise_()
            if s.foto.tela is tc:
                alvo = s
        alvo = alvo or (self.seletores[0] if self.seletores else None)
        if alvo:
            alvo.activateWindow()
            alvo.setFocus()
            alvo.mouse = alvo.mapFromGlobal(QCursor.pos())
            alvo.hover = alvo._janela_em(alvo.mouse)
            alvo.update()
            _primeiro_plano(alvo)

    def mouse_em(self, seletor):
        if not seletor.isActiveWindow():
            seletor.activateWindow()
            seletor.setFocus()
        for s in self.seletores:
            if s is not seletor and s.hover is not None:
                s.hover = None
                s.mouse = QPoint(-100, -100)
                s.update()

    def selecionou(self, seletor):
        for s in self.seletores:
            if s is not seletor:
                s.desativar()

    def reativar_todos(self):
        for s in self.seletores:
            s.ativo = True
            s.update()

    def concluir(self, seletor, acao):
        if self.terminada:
            return
        self.terminada = True
        img = seletor.imagem_final() if self.modo != "gravar" else None
        for s in self.seletores:
            s.hide()
        try:
            self.ao_concluir(acao, img, seletor)
        finally:
            self._fechar()

    def cancelar(self):
        if self.terminada:
            return
        self.terminada = True
        self._fechar()
        try:
            self.ao_concluir("cancelar", None, None)
        except Exception:  # noqa: BLE001
            pass

    def _fechar(self):
        for s in self.seletores:
            s.close()
        self.seletores = []


def _primeiro_plano(w: QWidget):
    import sys
    if sys.platform != "win32":
        return
    try:
        import ctypes
        u = ctypes.windll.user32
        hwnd = int(w.winId())
        u.SetForegroundWindow(hwnd)
        u.SetFocus(hwnd)
    except Exception:  # noqa: BLE001
        pass


__all__ = ["Sessao", "Seletor"]
