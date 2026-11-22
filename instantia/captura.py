"""Tira a foto das telas e descobre onde estão as janelas (para selecionar uma janela com um clique)."""
from __future__ import annotations

import sys

from PySide6.QtCore import QRect
from PySide6.QtGui import QCursor, QGuiApplication, QImage


class Foto:
    """Foto de um monitor: imagem em pixels reais + geometria lógica da tela."""

    def __init__(self, tela, imagem: QImage, escala: float):
        self.tela = tela
        self.imagem = imagem
        self.escala = escala                # pixels reais por pixel lógico
        self.geo = tela.geometry()          # posição lógica no desktop virtual
        self.janelas: list[QRect] = []      # retângulos das janelas, em coordenadas locais da tela
        # canto superior esquerdo do monitor em pixels reais do desktop (para a gravação com o FFmpeg)
        self.origem_fisica = (round(self.geo.x() * escala), round(self.geo.y() * escala))

    def retangulo_fisico(self, r: QRect) -> tuple[int, int, int, int]:
        """(x, y, largura, altura) em pixels reais do desktop, com largura e altura pares (exigência do H.264)."""
        e = self.escala
        x = self.origem_fisica[0] + round(r.x() * e)
        y = self.origem_fisica[1] + round(r.y() * e)
        w = max(2, round(r.width() * e)) // 2 * 2
        h = max(2, round(r.height() * e)) // 2 * 2
        return x, y, w, h


def fotografar(telas=None) -> list[Foto]:
    """Congela todas as telas (ou as indicadas) do jeito que estão agora."""
    out = []
    for t in telas or QGuiApplication.screens():
        pm = t.grabWindow(0)
        img = pm.toImage().convertToFormat(QImage.Format_RGB32)
        esc = pm.devicePixelRatio() or t.devicePixelRatio() or 1.0
        geo = t.geometry()
        if img.width() and geo.width():
            esc = img.width() / geo.width()
        img.setDevicePixelRatio(1.0)
        out.append(Foto(t, img, esc))
    if sys.platform == "win32":
        try:
            _janelas_windows(out)
        except Exception:  # noqa: BLE001
            pass
    return out


def tela_do_cursor():
    return QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()


# ------------------------------------------------------------------ Windows: lista de janelas (de cima para baixo)
def _janelas_windows(fotos: list[Foto]):
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    dwm = ctypes.windll.dwmapi

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT), ("rcWork", RECT), ("dwFlags", wintypes.DWORD),
                    ("szDevice", wintypes.WCHAR * 32)]

    # posição real (pixels) de cada monitor, pelo nome (\\.\DISPLAY1 …), que é o mesmo que o Qt usa
    monitores = {}
    PROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(RECT), ctypes.c_void_p)

    def cb_mon(hmon, hdc, rc, data):
        mi = MONITORINFOEXW()
        mi.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if u.GetMonitorInfoW(ctypes.c_void_p(hmon), ctypes.byref(mi)):
            r = mi.rcMonitor
            monitores[mi.szDevice] = (r.left, r.top, r.right, r.bottom)
        return 1
    u.EnumDisplayMonitors(None, None, PROC(cb_mon), 0)

    proprio = set()
    import os
    pid_proprio = os.getpid()
    janelas = []
    ENUM = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        if not u.IsWindowVisible(hwnd) or u.IsIconic(hwnd):
            return True
        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == pid_proprio:
            proprio.add(hwnd)
            return True
        cloaked = ctypes.c_int(0)
        dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))   # DWMWA_CLOAKED
        if cloaked.value:
            return True
        ex = u.GetWindowLongW(hwnd, -20)                       # GWL_EXSTYLE
        if ex & 0x00000080 and not u.GetWindowTextLengthW(hwnd):   # WS_EX_TOOLWINDOW sem título
            return True
        r = RECT()
        if dwm.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:   # EXTENDED_FRAME_BOUNDS
            u.GetWindowRect(hwnd, ctypes.byref(r))
        if r.right - r.left < 40 or r.bottom - r.top < 30:
            return True
        janelas.append((r.left, r.top, r.right, r.bottom))
        return True
    u.EnumWindows(ENUM(cb), 0)

    for f in fotos:
        m = monitores.get(f.tela.name())
        if not m:
            continue
        ml, mt, mr, mb = m
        f.origem_fisica = (ml, mt)
        for (l, t, r, b) in janelas:
            l2, t2, r2, b2 = max(l, ml), max(t, mt), min(r, mr), min(b, mb)
            if r2 - l2 < 20 or b2 - t2 < 20:
                continue
            e = f.escala
            f.janelas.append(QRect(round((l2 - ml) / e), round((t2 - mt) / e), round((r2 - l2) / e), round((b2 - t2) / e)))


__all__ = ["Foto", "fotografar", "tela_do_cursor"]
