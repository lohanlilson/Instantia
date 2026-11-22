"""Marcações desenhadas sobre o print: seta, linha, retângulo, elipse, caneta, marca-texto, texto, número e borrão.

As coordenadas são as da tela em que a captura foi feita (pixels lógicos). Na hora de exportar, o desenho é
refeito na resolução real da imagem (pixels do monitor), então nada fica serrilhado.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QLineF, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPainterPathStroker,
                           QPen, QPolygonF)

CORES = ["#e5243b", "#ff8a00", "#ffd400", "#21b04b", "#1e88e5", "#8b5cff", "#111111", "#ffffff"]
FONTE = "Segoe UI"


def _norm(p1: QPointF, p2: QPointF) -> QRectF:
    return QRectF(p1, p2).normalized()


class Anot:
    tipo = "?"

    def __init__(self, cor="#e5243b", espessura=4):
        self.cor = QColor(cor)
        self.espessura = espessura

    # geometria
    def area(self) -> QRectF:
        raise NotImplementedError

    def forma(self) -> QPainterPath:
        """Região clicável (para selecionar e mover)."""
        p = QPainterPath()
        p.addRect(self.area().adjusted(-4, -4, 4, 4))
        return p

    def contem(self, pt: QPointF) -> bool:
        return self.forma().contains(pt)

    def mover(self, d: QPointF):
        raise NotImplementedError

    def editando(self, p1: QPointF, p2: QPointF, shift=False):
        """Atualiza enquanto o mouse arrasta (p1 = onde começou)."""

    def valida(self) -> bool:
        r = self.area()
        return r.width() > 2 or r.height() > 2

    def desenhar(self, g: QPainter, fundo: QImage | None = None, escala: float = 1.0):
        raise NotImplementedError

    def caneta(self):
        pen = QPen(self.cor, self.espessura, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        return pen


def _contorno(path: QPainterPath, largura: float) -> QPainterPath:
    s = QPainterPathStroker()
    s.setWidth(max(10.0, largura + 8))
    return s.createStroke(path)


class Retangulo(Anot):
    tipo = "retangulo"

    def __init__(self, r=QRectF(), **k):
        super().__init__(**k)
        self.r = QRectF(r)

    def area(self):
        return self.r

    def forma(self):
        p = QPainterPath()
        p.addRect(self.r)
        return _contorno(p, self.espessura)

    def mover(self, d):
        self.r.translate(d)

    def editando(self, p1, p2, shift=False):
        if shift:                                     # quadrado
            lado = max(abs(p2.x() - p1.x()), abs(p2.y() - p1.y()))
            p2 = QPointF(p1.x() + math.copysign(lado, p2.x() - p1.x()), p1.y() + math.copysign(lado, p2.y() - p1.y()))
        self.r = _norm(p1, p2)

    def desenhar(self, g, fundo=None, escala=1.0):
        g.setPen(self.caneta())
        g.setBrush(Qt.NoBrush)
        g.drawRoundedRect(self.r, 2, 2)


class Elipse(Retangulo):
    tipo = "elipse"

    def forma(self):
        p = QPainterPath()
        p.addEllipse(self.r)
        return _contorno(p, self.espessura)

    def desenhar(self, g, fundo=None, escala=1.0):
        g.setPen(self.caneta())
        g.setBrush(Qt.NoBrush)
        g.drawEllipse(self.r)


class Linha(Anot):
    tipo = "linha"

    def __init__(self, p1=QPointF(), p2=QPointF(), **k):
        super().__init__(**k)
        self.p1, self.p2 = QPointF(p1), QPointF(p2)

    def area(self):
        return _norm(self.p1, self.p2)

    def valida(self):
        return QLineF(self.p1, self.p2).length() > 4

    def forma(self):
        p = QPainterPath(self.p1)
        p.lineTo(self.p2)
        return _contorno(p, self.espessura)

    def mover(self, d):
        self.p1 += d
        self.p2 += d

    def editando(self, p1, p2, shift=False):
        if shift:                                     # trava em 45°
            ln = QLineF(p1, p2)
            ang = round(ln.angle() / 45) * 45
            ln.setAngle(ang)
            p2 = ln.p2()
        self.p1, self.p2 = QPointF(p1), QPointF(p2)

    def desenhar(self, g, fundo=None, escala=1.0):
        g.setPen(self.caneta())
        g.drawLine(self.p1, self.p2)


class Seta(Linha):
    tipo = "seta"

    def cabeca(self) -> QPolygonF:
        ln = QLineF(self.p2, self.p1)
        tam = max(14.0, self.espessura * 4.2)
        a = math.radians(ln.angle())
        abertura = math.radians(26)
        pts = [self.p2]
        for s in (+1, -1):
            pts.append(QPointF(self.p2.x() + tam * math.cos(a + s * abertura), self.p2.y() - tam * math.sin(a + s * abertura)))
        return QPolygonF(pts)

    def desenhar(self, g, fundo=None, escala=1.0):
        ln = QLineF(self.p1, self.p2)
        tam = max(14.0, self.espessura * 4.2)
        corpo = QLineF(self.p1, ln.pointAt(max(0.0, 1 - (tam * 0.7) / max(ln.length(), 1))))
        g.setPen(self.caneta())
        g.drawLine(corpo)
        g.setPen(QPen(self.cor, 1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        g.setBrush(self.cor)
        g.drawPolygon(self.cabeca())


class CanetaLivre(Anot):
    tipo = "caneta"

    def __init__(self, pontos=None, **k):
        super().__init__(**k)
        self.pontos = [QPointF(p) for p in (pontos or [])]

    def area(self):
        if not self.pontos:
            return QRectF()
        xs = [p.x() for p in self.pontos]
        ys = [p.y() for p in self.pontos]
        return QRectF(QPointF(min(xs), min(ys)), QPointF(max(xs), max(ys)))

    def valida(self):
        return len(self.pontos) > 1

    def caminho(self):
        p = QPainterPath()
        if self.pontos:
            p.moveTo(self.pontos[0])
            for i in range(1, len(self.pontos)):        # suaviza com curvas entre os pontos do meio
                a = self.pontos[i - 1]
                b = self.pontos[i]
                p.quadTo(a, (a + b) / 2)
            p.lineTo(self.pontos[-1])
        return p

    def forma(self):
        return _contorno(self.caminho(), self.espessura)

    def mover(self, d):
        self.pontos = [p + d for p in self.pontos]

    def editando(self, p1, p2, shift=False):
        if not self.pontos:
            self.pontos.append(QPointF(p1))
        if QLineF(self.pontos[-1], p2).length() >= 1.5:
            self.pontos.append(QPointF(p2))

    def desenhar(self, g, fundo=None, escala=1.0):
        g.setPen(self.caneta())
        g.setBrush(Qt.NoBrush)
        g.drawPath(self.caminho())


class MarcaTexto(Retangulo):
    """Faixa amarela translúcida (como caneta marca-texto), sem esconder o que está embaixo."""
    tipo = "marcatexto"

    def __init__(self, r=QRectF(), **k):
        k.setdefault("cor", "#ffd400")
        super().__init__(r, **k)

    def forma(self):
        p = QPainterPath()
        p.addRect(self.r)
        return p

    def desenhar(self, g, fundo=None, escala=1.0):
        g.save()
        g.setCompositionMode(QPainter.CompositionMode_Multiply)
        c = QColor(self.cor)
        g.setPen(Qt.NoPen)
        g.setBrush(c)
        g.drawRect(self.r)
        g.restore()


class Borrao(Retangulo):
    """Esconde o que está embaixo (pixelado). Usado também pelo "Ocultar dados"."""
    tipo = "borrao"

    def __init__(self, r=QRectF(), automatico=False, **k):
        super().__init__(r, **k)
        self.automatico = automatico

    def forma(self):
        p = QPainterPath()
        p.addRect(self.r)
        return p

    def desenhar(self, g, fundo=None, escala=1.0):
        r = self.r
        if fundo is None or r.isEmpty():
            g.fillRect(r, QColor(120, 120, 120))
            return
        # fundo está em pixels reais; r em pixels lógicos (escala = pixels reais por lógico)
        rr = QRect(int(r.x() * escala), int(r.y() * escala), max(1, int(r.width() * escala)),
                   max(1, int(r.height() * escala))).intersected(fundo.rect())
        if rr.isEmpty():
            return
        pedaco = fundo.copy(rr)
        bloco = max(8.0 * escala, min(rr.width(), rr.height()) / 1.7)      # blocos grandes: ilegível de verdade
        peq = pedaco.scaled(max(1, int(rr.width() / bloco)), max(1, int(rr.height() / bloco)),
                            Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        pix = peq.scaled(rr.width(), rr.height(), Qt.IgnoreAspectRatio, Qt.FastTransformation)
        g.drawImage(QRectF(rr.x() / escala, rr.y() / escala, rr.width() / escala, rr.height() / escala), pix)


class Texto(Anot):
    tipo = "texto"

    def __init__(self, pos=QPointF(), texto="", tamanho=None, **k):
        super().__init__(**k)
        self.pos = QPointF(pos)
        self.texto = texto
        self.tamanho = tamanho or max(14, int(self.espessura * 4.5))

    def fonte(self):
        f = QFont(FONTE)
        f.setPixelSize(int(self.tamanho))
        f.setBold(True)
        return f

    def area(self):
        fm = QFontMetricsF(self.fonte())
        linhas = (self.texto or " ").split("\n")
        w = max(fm.horizontalAdvance(ln) for ln in linhas)
        return QRectF(self.pos, QPointF(self.pos.x() + w + 6, self.pos.y() + fm.lineSpacing() * len(linhas) + 4))

    def valida(self):
        return bool(self.texto.strip())

    def mover(self, d):
        self.pos += d

    def desenhar(self, g, fundo=None, escala=1.0):
        fm = QFontMetricsF(self.fonte())
        path = QPainterPath()
        for i, ln in enumerate(self.texto.split("\n")):
            path.addText(QPointF(self.pos.x() + 3, self.pos.y() + 2 + fm.ascent() + i * fm.lineSpacing()), self.fonte(), ln)
        claro = self.cor.lightness() > 150
        g.setPen(QPen(QColor(0, 0, 0, 170) if claro else QColor(255, 255, 255, 220), max(2.0, self.tamanho / 7),
                      Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        g.setBrush(Qt.NoBrush)
        g.drawPath(path)                               # contorno: lê em qualquer fundo
        g.setPen(Qt.NoPen)
        g.setBrush(self.cor)
        g.drawPath(path)


class Numero(Anot):
    """Bolinha numerada (1, 2, 3…) para indicar passos."""
    tipo = "numero"

    def __init__(self, pos=QPointF(), n=1, **k):
        super().__init__(**k)
        self.pos = QPointF(pos)
        self.n = n

    def raio(self):
        return max(13.0, self.espessura * 3.4)

    def area(self):
        r = self.raio()
        return QRectF(self.pos.x() - r, self.pos.y() - r, 2 * r, 2 * r)

    def valida(self):
        return True

    def forma(self):
        p = QPainterPath()
        p.addEllipse(self.area())
        return p

    def mover(self, d):
        self.pos += d

    def editando(self, p1, p2, shift=False):
        self.pos = QPointF(p2)

    def desenhar(self, g, fundo=None, escala=1.0):
        r = self.area()
        g.setPen(QPen(QColor(255, 255, 255), 2))
        g.setBrush(self.cor)
        g.drawEllipse(r)
        f = QFont(FONTE)
        f.setPixelSize(int(self.raio() * 1.15))
        f.setBold(True)
        g.setFont(f)
        g.setPen(QColor("#111111") if self.cor.lightness() > 170 else QColor("#ffffff"))
        g.drawText(r, Qt.AlignCenter, str(self.n))


FERRAMENTAS = {
    "seta": Seta, "linha": Linha, "retangulo": Retangulo, "elipse": Elipse, "caneta": CanetaLivre,
    "marcatexto": MarcaTexto, "texto": Texto, "numero": Numero, "borrao": Borrao,
}


def nova(ferramenta: str, cor: str, espessura: int, p: QPointF, numero: int = 1) -> Anot:
    cls = FERRAMENTAS[ferramenta]
    if cls is MarcaTexto:
        c = QColor(cor)
        if c.name() in ("#111111", "#ffffff"):
            c = QColor("#ffd400")
        return MarcaTexto(QRectF(p, p), cor=c.name())
    if cls is Numero:
        return Numero(p, numero, cor=cor, espessura=espessura)
    if cls is Texto:
        return Texto(p, "", cor=cor, espessura=espessura)
    if cls in (Linha, Seta):
        return cls(p, p, cor=cor, espessura=espessura)
    if cls is CanetaLivre:
        return CanetaLivre([p], cor=cor, espessura=espessura)
    return cls(QRectF(p, p), cor=cor, espessura=espessura)


def renderizar(base: QImage, selecao: QRect, anots: list, escala: float) -> QImage:
    """Imagem final: o pedaço selecionado do print (pixels reais) com as marcações por cima."""
    rr = QRect(int(round(selecao.x() * escala)), int(round(selecao.y() * escala)),
               int(round(selecao.width() * escala)), int(round(selecao.height() * escala))).intersected(base.rect())
    out = base.copy(rr).convertToFormat(QImage.Format_ARGB32)
    out.setDevicePixelRatio(1.0)
    if not anots:
        return out
    g = QPainter(out)
    g.setRenderHint(QPainter.Antialiasing)
    g.setRenderHint(QPainter.TextAntialiasing)
    g.scale(escala, escala)
    g.translate(-selecao.x(), -selecao.y())
    fundo = base
    for a in anots:
        if isinstance(a, Borrao):
            a.desenhar(g, fundo, escala)
    for a in anots:
        if not isinstance(a, Borrao):
            a.desenhar(g, fundo, escala)
    g.end()
    return out


__all__ = ["CORES", "FERRAMENTAS", "nova", "renderizar", "Anot", "Seta", "Linha", "Retangulo", "Elipse",
           "CanetaLivre", "MarcaTexto", "Borrao", "Texto", "Numero"]
