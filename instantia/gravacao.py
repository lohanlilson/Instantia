"""Gravar a tela em vídeo (MP4) ou GIF, com o microfone se a pessoa quiser.

Usa o FFmpeg (gdigrab no Windows). O FFmpeg não vem no instalador: é baixado uma vez, do PyPI (pacote
imageio-ffmpeg), na primeira gravação, conferindo o SHA-256.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

from PySide6.QtCore import QObject, QPoint, QRect, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QWidget

from . import APP_NAME, __version__, pasta_dados
from .icones import icone

SEM_JANELA = 0x08000000 if sys.platform == "win32" else 0
PYPI_FFMPEG = "https://pypi.org/pypi/imageio-ffmpeg/json"


# ------------------------------------------------------------------ FFmpeg
def caminho_ffmpeg() -> str | None:
    env = os.environ.get("INSTANTIA_FFMPEG")
    if env and os.path.exists(env):
        return env
    local = os.path.join(pasta_dados("ffmpeg"), "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    if os.path.exists(local):
        return local
    return shutil.which("ffmpeg")


def baixar_ffmpeg(progresso=None) -> str:
    padrao = {"win32": r"-win_amd64\.whl$", "linux": r"-manylinux.*x86_64\.whl$"}.get(sys.platform)
    if not padrao:
        raise IOError("FFmpeg não disponível para este sistema")
    ua = {"User-Agent": f"{APP_NAME}/{__version__}"}
    with urllib.request.urlopen(urllib.request.Request(PYPI_FFMPEG, headers=ua), timeout=30) as r:
        info = json.loads(r.read().decode("utf-8"))
    arq = next((u for u in info["urls"] if re.search(padrao, u["filename"])), None)
    if not arq:
        raise IOError("pacote do FFmpeg não encontrado")
    tmp = tempfile.mkdtemp(prefix="instantia-ffmpeg-")
    try:
        whl = os.path.join(tmp, "ffmpeg.whl")
        h = hashlib.sha256()
        with urllib.request.urlopen(urllib.request.Request(arq["url"], headers=ua), timeout=60) as r, open(whl, "wb") as f:
            total = int(r.headers.get("Content-Length") or arq.get("size") or 0)
            lido = 0
            while True:
                b = r.read(1 << 16)
                if not b:
                    break
                f.write(b)
                h.update(b)
                lido += len(b)
                if progresso and total:
                    progresso(lido / total)
        if h.hexdigest() != arq["digests"]["sha256"]:
            raise IOError("o FFmpeg baixado está corrompido")
        destino = os.path.join(pasta_dados("ffmpeg"), "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
        with zipfile.ZipFile(whl) as z:
            membro = next(n for n in z.namelist() if "/binaries/ffmpeg" in n and not n.endswith("/"))
            with z.open(membro) as o, open(destino + ".tmp", "wb") as s:
                shutil.copyfileobj(o, s)
        os.replace(destino + ".tmp", destino)
        if sys.platform != "win32":
            os.chmod(destino, 0o755)
        return destino
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def microfones() -> list[str]:
    """Nomes dos microfones (DirectShow) que o FFmpeg enxerga."""
    ff = caminho_ffmpeg()
    if not ff or sys.platform != "win32":
        return []
    r = subprocess.run([ff, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=SEM_JANELA)
    nomes = []
    for ln in r.stderr.splitlines():
        m = re.search(r'"([^"]+)"\s*\(audio\)', ln)
        if m:
            nomes.append(m.group(1))
    if not nomes:                                   # versões antigas do FFmpeg listam em seções
        secao = False
        for ln in r.stderr.splitlines():
            if "DirectShow audio devices" in ln:
                secao = True
            elif "DirectShow video devices" in ln:
                secao = False
            elif secao:
                m = re.search(r'\]\s+"([^"]+)"', ln)
                if m and "Alternative name" not in ln:
                    nomes.append(m.group(1))
    return nomes


def comando(ff, retangulo, saida, fps=30, microfone="", cursor=True, plataforma=sys.platform):
    x, y, w, h = retangulo
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error"]
    if plataforma == "win32":
        cmd += ["-f", "gdigrab", "-framerate", str(fps), "-offset_x", str(x), "-offset_y", str(y),
                "-video_size", f"{w}x{h}", "-draw_mouse", "1" if cursor else "0", "-i", "desktop"]
        if microfone:
            cmd += ["-f", "dshow", "-i", f"audio={microfone}"]
    else:                                           # Linux (testes): X11
        tela = os.environ.get("DISPLAY", ":0")
        cmd += ["-f", "x11grab", "-framerate", str(fps), "-video_size", f"{w}x{h}", "-i", f"{tela}+{x},{y}"]
    cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    if microfone and plataforma == "win32":
        cmd += ["-c:a", "aac", "-b:a", "128k"]
    cmd.append(saida)
    return cmd


def para_gif(ff, mp4, gif, largura_max=960, fps=12):
    filtro = (f"fps={fps},scale='min(iw,{largura_max})':-2:flags=lanczos,split[a][b];"
              "[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4")
    r = subprocess.run([ff, "-y", "-hide_banner", "-loglevel", "error", "-i", mp4, "-vf", filtro, gif],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=SEM_JANELA)
    if r.returncode != 0 or not os.path.exists(gif):
        raise IOError(r.stderr.strip()[-300:] or "falha ao gerar o GIF")
    return gif


class Gravacao(QObject):
    """Um processo do FFmpeg gravando um retângulo da tela."""
    terminou = Signal(str, str)        # arquivo, erro

    def __init__(self, retangulo, pasta, fps=30, microfone="", cursor=True):
        super().__init__()
        self.retangulo = retangulo
        self.pasta = pasta
        self.fps, self.microfone, self.cursor = fps, microfone, cursor
        self.proc = None
        self.inicio = 0.0
        self.mp4 = os.path.join(tempfile.mkdtemp(prefix="instantia-grav-"), "gravacao.mp4")

    def iniciar(self):
        ff = caminho_ffmpeg()
        if not ff:
            raise IOError("FFmpeg não encontrado")
        cmd = comando(ff, self.retangulo, self.mp4, self.fps, self.microfone, self.cursor)
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=SEM_JANELA)
        self.inicio = time.monotonic()
        time.sleep(0.4)
        if self.proc.poll() is not None:
            err = self.proc.stderr.read().decode("utf-8", "replace").strip()
            if self.microfone and ("dshow" in err.lower() or "audio" in err.lower()):
                # microfone indisponível: grava sem som
                self.microfone = ""
                return self.iniciar()
            raise IOError(err[-300:] or "o FFmpeg não iniciou a gravação")

    def duracao(self):
        return time.monotonic() - self.inicio if self.inicio else 0.0

    def parar(self, formato="mp4", nome=None):
        """Para e salva na pasta (mp4 ou gif). Devolve o caminho."""
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.write(b"q")
                self.proc.stdin.flush()
                self.proc.stdin.close()
            except OSError:
                pass
            try:
                self.proc.wait(20)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if not os.path.exists(self.mp4) or os.path.getsize(self.mp4) < 1000:
            err = self.proc.stderr.read().decode("utf-8", "replace").strip() if self.proc else ""
            raise IOError(err[-300:] or "a gravação ficou vazia")
        os.makedirs(self.pasta, exist_ok=True)
        nome = nome or time.strftime("Instantia %Y-%m-%d %H-%M-%S")
        if formato == "gif":
            destino = os.path.join(self.pasta, nome + ".gif")
            para_gif(caminho_ffmpeg(), self.mp4, destino)
        else:
            destino = os.path.join(self.pasta, nome + ".mp4")
            shutil.move(self.mp4, destino)
        shutil.rmtree(os.path.dirname(self.mp4), ignore_errors=True)
        return destino

    def cancelar(self):
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                pass
        shutil.rmtree(os.path.dirname(self.mp4), ignore_errors=True)


class Moldura(QWidget):
    """Borda vermelha tracejada em volta da área gravada (fica FORA da área, então não aparece no vídeo)."""

    def __init__(self, r: QRect):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setGeometry(r.adjusted(-4, -4, 4, 4))
        self.fase = 0
        self._t = QTimer(self, interval=120, timeout=self._andar)
        self._t.start()

    def _andar(self):
        self.fase = (self.fase + 1) % 16
        self.update()

    def paintEvent(self, ev):
        g = QPainter(self)
        pen = QPen(QColor("#e5243b"), 2, Qt.CustomDashLine)
        pen.setDashPattern([4, 4])
        pen.setDashOffset(self.fase)
        g.setPen(pen)
        g.drawRect(self.rect().adjusted(1, 1, -2, -2))


class BarraGravacao(QWidget):
    """Controle flutuante: tempo, parar (MP4), parar como GIF e cancelar."""
    pedir = Signal(str)                # mp4 | gif | cancelar

    def __init__(self, area: QRect, tela_geo: QRect):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("""
            QWidget#Fundo { background: rgba(28,26,38,0.97); border-radius: 12px; border: 1px solid rgba(255,255,255,0.12); }
            QLabel { color: white; font-size: 13px; font-weight: 600; padding: 0 8px; }
            QToolButton { color: white; border: none; border-radius: 8px; padding: 5px 9px; font-weight: 600; }
            QToolButton:hover { background: rgba(255,255,255,0.14); }
        """)
        fundo = QWidget(self)
        fundo.setObjectName("Fundo")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(fundo)
        h = QHBoxLayout(fundo)
        h.setContentsMargins(6, 4, 6, 4)
        self.ponto = QLabel("●")
        self.ponto.setStyleSheet("color: #e5243b; padding: 0 0 0 6px;")
        self.tempo = QLabel("00:00")
        h.addWidget(self.ponto)
        h.addWidget(self.tempo)
        for texto, ic, acao, dica in (("Parar", "parar", "mp4", "Parar e salvar em MP4"),
                                      ("GIF", None, "gif", "Parar e salvar como GIF"),
                                      ("", "fechar", "cancelar", "Cancelar (não salva)")):
            b = QToolButton()
            if ic:
                b.setIcon(icone(ic))
            b.setText(texto)
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon if ic and texto else
                                 (Qt.ToolButtonIconOnly if ic else Qt.ToolButtonTextOnly))
            b.setToolTip(dica)
            b.clicked.connect(lambda _=False, a=acao: self.pedir.emit(a))
            h.addWidget(b)
        self.adjustSize()
        x = area.right() - self.width()
        y = area.bottom() + 10
        if y + self.height() > tela_geo.bottom():
            y = area.top() - self.height() - 10
        if y < tela_geo.top():
            y = area.bottom() - self.height() - 10        # área = tela inteira: fica dentro (aparece no vídeo)
        x = max(tela_geo.left() + 4, min(x, tela_geo.right() - self.width() - 4))
        self.move(QPoint(x, y))
        self._arraste = None

    def mostrar_tempo(self, s):
        m, s = divmod(int(s), 60)
        self.tempo.setText(f"{m:02d}:{s:02d}")

    def mousePressEvent(self, ev):
        self._arraste = ev.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, ev):
        if self._arraste is not None:
            self.move(ev.globalPosition().toPoint() - self._arraste)

    def mouseReleaseEvent(self, ev):
        self._arraste = None


class ThreadFFmpeg(QThread):
    progresso = Signal(float)
    terminou = Signal(str, str)

    def run(self):
        try:
            self.terminou.emit(caminho_ffmpeg() or baixar_ffmpeg(self.progresso.emit), "")
        except Exception as e:  # noqa: BLE001
            self.terminou.emit("", str(e))


__all__ = ["caminho_ffmpeg", "baixar_ffmpeg", "microfones", "comando", "para_gif", "Gravacao", "Moldura",
           "BarraGravacao", "ThreadFFmpeg"]
