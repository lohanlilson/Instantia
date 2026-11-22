"""Ícones desenhados no próprio código (nítidos em qualquer escala, sem depender de fontes do sistema)."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

_cache: dict = {}


def icone(nome: str, cor: str = "#ffffff", tam: int = 20) -> QIcon:
    chave = (nome, cor, tam)
    if chave in _cache:
        return _cache[chave]
    ic = QIcon()
    for esc in (1, 2):
        pm = QPixmap(tam * esc, tam * esc)
        pm.fill(Qt.transparent)
        pm.setDevicePixelRatio(esc)
        g = QPainter(pm)
        g.setRenderHint(QPainter.Antialiasing)
        _desenhar(g, nome, QColor(cor), tam)
        g.end()
        ic.addPixmap(pm)
    _cache[chave] = ic
    return ic


def _desenhar(g: QPainter, nome: str, c: QColor, s: float):
    k = s / 20.0
    g.scale(k, k)
    pen = QPen(c, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    g.setPen(pen)
    g.setBrush(Qt.NoBrush)
    P = QPointF
    if nome == "mover":
        poly = QPolygonF([P(5, 3), P(5, 16), P(8.5, 12.5), P(11, 17.5), P(13, 16.5), P(10.6, 11.6), P(15.5, 11.5)])
        g.setBrush(c)
        g.drawPolygon(poly)
    elif nome == "seta":
        g.drawLine(P(4, 16), P(15, 5))
        g.setBrush(c)
        g.drawPolygon(QPolygonF([P(16.5, 3.5), P(9.5, 5.2), P(14.8, 10.5)]))
    elif nome == "linha":
        g.drawLine(P(4, 16), P(16, 4))
    elif nome == "retangulo":
        g.drawRoundedRect(QRectF(3.5, 5, 13, 10), 1.5, 1.5)
    elif nome == "elipse":
        g.drawEllipse(QRectF(3, 5, 14, 10))
    elif nome == "caneta":
        path = QPainterPath(P(3.5, 14))
        path.cubicTo(P(6, 6), P(9, 18), P(12, 9))
        path.cubicTo(P(13.5, 5), P(15.5, 8), P(16.5, 6))
        g.drawPath(path)
    elif nome == "marcatexto":
        g.setPen(Qt.NoPen)
        amarelo = QColor("#ffd400")
        amarelo.setAlpha(200)
        g.setBrush(amarelo)
        g.drawRect(QRectF(2.5, 10, 15, 6))
        g.setPen(pen)
        g.setBrush(Qt.NoBrush)
        g.drawLine(P(5, 8), P(15, 8))
    elif nome == "texto":
        f = QFont("Segoe UI")
        f.setPixelSize(15)
        f.setBold(True)
        path = QPainterPath()
        path.addText(P(5.2, 15.5), f, "T")
        g.setPen(Qt.NoPen)
        g.setBrush(c)
        g.drawPath(path)
    elif nome == "numero":
        g.setBrush(c)
        g.setPen(Qt.NoPen)
        g.drawEllipse(QRectF(3, 3, 14, 14))
        f = QFont("Segoe UI")
        f.setPixelSize(10)
        f.setBold(True)
        path = QPainterPath()
        path.addText(P(7.3, 13.6), f, "1")
        g.setBrush(QColor("#1c1a26"))
        g.drawPath(path)
    elif nome == "borrao":
        g.setPen(Qt.NoPen)
        for i in range(4):
            for j in range(4):
                cc = QColor(c)
                cc.setAlpha(255 if (i + j) % 2 == 0 else 110)
                g.setBrush(cc)
                g.drawRect(QRectF(3 + i * 3.6, 3 + j * 3.6, 3.4, 3.4))
    elif nome == "desfazer":
        path = QPainterPath(P(6, 7))
        path.cubicTo(P(13, 3), P(19, 10), P(12, 16))
        g.drawPath(path)
        g.drawPolyline(QPolygonF([P(6.5, 2.8), P(5.6, 7.2), P(10, 8)]))
    elif nome == "refazer":
        path = QPainterPath(P(14, 7))
        path.cubicTo(P(7, 3), P(1, 10), P(8, 16))
        g.drawPath(path)
        g.drawPolyline(QPolygonF([P(13.5, 2.8), P(14.4, 7.2), P(10, 8)]))
    elif nome == "ocultar":
        path = QPainterPath(P(2.5, 10))
        path.quadTo(P(10, 2), P(17.5, 10))
        path.quadTo(P(10, 18), P(2.5, 10))
        g.drawPath(path)
        g.drawEllipse(QRectF(7.6, 7.6, 4.8, 4.8))
        g.drawLine(P(4, 16.5), P(16, 3.5))
    elif nome == "ocr":
        g.drawRect(QRectF(2.5, 2.5, 15, 15))
        for y in (7, 10, 13):
            g.drawLine(P(5.5, y), P(14.5 if y != 13 else 11, y))
    elif nome == "fixar":
        g.drawLine(P(10, 12), P(10, 18))
        g.setBrush(c)
        g.drawPolygon(QPolygonF([P(6, 12), P(14, 12), P(12.5, 8), P(12.5, 3.5), P(7.5, 3.5), P(7.5, 8)]))
    elif nome == "salvar":
        g.drawRoundedRect(QRectF(3, 3, 14, 14), 2, 2)
        g.drawRect(QRectF(6, 3, 8, 5))
        g.drawRect(QRectF(6, 11, 8, 6))
    elif nome == "copiar":
        g.drawRoundedRect(QRectF(6.5, 6.5, 10, 11), 1.5, 1.5)
        path = QPainterPath(P(3.5, 13.5))
        path.lineTo(P(3.5, 3.5))
        path.lineTo(P(12.5, 3.5))
        g.drawPath(path)
    elif nome == "fechar":
        g.drawLine(P(5, 5), P(15, 15))
        g.drawLine(P(15, 5), P(5, 15))
    elif nome == "gravar":
        g.drawEllipse(QRectF(2.5, 2.5, 15, 15))
        g.setBrush(QColor("#e5243b"))
        g.setPen(Qt.NoPen)
        g.drawEllipse(QRectF(6, 6, 8, 8))
    elif nome == "parar":
        g.setBrush(c)
        g.setPen(Qt.NoPen)
        g.drawRoundedRect(QRectF(5, 5, 10, 10), 2, 2)
    elif nome == "pausar":
        g.setBrush(c)
        g.setPen(Qt.NoPen)
        g.drawRoundedRect(QRectF(5, 4, 3.4, 12), 1, 1)
        g.drawRoundedRect(QRectF(11.6, 4, 3.4, 12), 1, 1)
    elif nome == "camera":
        g.drawRoundedRect(QRectF(2.5, 5.5, 15, 11), 2.5, 2.5)
        g.drawEllipse(QRectF(7, 8, 6, 6))
        g.drawLine(P(7, 5.5), P(8.5, 3.5))
        g.drawLine(P(8.5, 3.5), P(11.5, 3.5))
        g.drawLine(P(11.5, 3.5), P(13, 5.5))
    elif nome == "pasta":
        path = QPainterPath(P(2.5, 6))
        for q in (P(2.5, 4), P(8, 4), P(9.5, 6), P(17.5, 6), P(17.5, 16), P(2.5, 16), P(2.5, 6)):
            path.lineTo(q)
        g.drawPath(path)
    elif nome == "historico":
        g.drawEllipse(QRectF(3, 3, 14, 14))
        g.drawPolyline(QPolygonF([P(10, 6), P(10, 10), P(13, 12)]))
    elif nome == "tela":
        g.drawRoundedRect(QRectF(2.5, 3.5, 15, 10.5), 1.5, 1.5)
        g.drawLine(P(7, 17), P(13, 17))
        g.drawLine(P(10, 14), P(10, 17))
    elif nome == "janela":
        g.drawRoundedRect(QRectF(2.5, 3.5, 15, 13), 1.5, 1.5)
        g.drawLine(P(2.5, 7), P(17.5, 7))
    elif nome == "config":
        g.drawEllipse(QRectF(7, 7, 6, 6))
        import math
        for i in range(8):
            a = math.radians(i * 45)
            g.drawLine(P(10 + 5 * math.cos(a), 10 + 5 * math.sin(a)), P(10 + 7.5 * math.cos(a), 10 + 7.5 * math.sin(a)))
    else:
        g.drawRect(QRectF(4, 4, 12, 12))


def bolinha_cor(cor: str, tam: int = 18, borda: str = "#ffffff") -> QIcon:
    pm = QPixmap(tam * 2, tam * 2)
    pm.fill(Qt.transparent)
    pm.setDevicePixelRatio(2)
    g = QPainter(pm)
    g.setRenderHint(QPainter.Antialiasing)
    g.setPen(QPen(QColor(borda), 1.5))
    g.setBrush(QColor(cor))
    g.drawEllipse(QRectF(2, 2, tam - 4, tam - 4))
    g.end()
    return QIcon(pm)


def espessura_icone(px: int, tam: int = 20) -> QIcon:
    pm = QPixmap(tam * 2, tam * 2)
    pm.fill(Qt.transparent)
    pm.setDevicePixelRatio(2)
    g = QPainter(pm)
    g.setRenderHint(QPainter.Antialiasing)
    g.setPen(Qt.NoPen)
    g.setBrush(QColor("#ffffff"))
    d = {2: 4, 4: 7, 7: 11}.get(px, 6)
    g.drawEllipse(QRectF((tam - d) / 2, (tam - d) / 2, d, d))
    g.end()
    return QIcon(pm)


__all__ = ["icone", "bolinha_cor", "espessura_icone"]
