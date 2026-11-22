"""Reconhecer o texto do print (OCR), sem internet.

No Windows 10/11 usa o OCR do próprio Windows (o mesmo da Ferramenta de Captura), em português quando o idioma
está instalado. Sem ele (ou fora do Windows) usa o Tesseract, se estiver instalado.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage

SEM_JANELA = 0x08000000 if sys.platform == "win32" else 0


@dataclass
class Palavra:
    texto: str
    rect: QRect          # em pixels da imagem
    linha: int


class SemOCR(Exception):
    pass


def _preparar(img: QImage) -> tuple[QImage, float]:
    """Amplia prints pequenos (texto de tela costuma ter 11–14 px; o OCR acerta mais com o dobro)."""
    fator = 1.0
    maior = max(img.width(), img.height())
    if min(img.width(), img.height()) < 1600 and maior * 2 <= 8000:
        fator = 2.0
    if fator != 1.0:
        img = img.scaled(int(img.width() * fator), int(img.height() * fator), Qt.IgnoreAspectRatio,
                         Qt.SmoothTransformation)
    return img, fator


# ------------------------------------------------------------------ Windows
def _windows(img: QImage) -> list[Palavra]:
    import asyncio
    from winrt.windows.globalization import Language
    from winrt.windows.graphics.imaging import BitmapAlphaMode, BitmapPixelFormat, SoftwareBitmap
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage.streams import DataWriter

    eng = None
    for tag in ("pt-BR", "pt-PT", "pt"):
        try:
            lang = Language(tag)
            if OcrEngine.is_language_supported(lang):
                eng = OcrEngine.try_create_from_language(lang)
                break
        except Exception:  # noqa: BLE001
            continue
    if eng is None:
        eng = OcrEngine.try_create_from_user_profile_languages()
    if eng is None:
        langs = list(OcrEngine.available_recognizer_languages)
        if langs:
            eng = OcrEngine.try_create_from_language(langs[0])
    if eng is None:
        raise SemOCR("O OCR do Windows não tem nenhum idioma instalado")

    grande, fator = _preparar(img)
    lim = int(OcrEngine.max_image_dimension)
    if max(grande.width(), grande.height()) > lim:
        grande, fator = img, 1.0
        if max(img.width(), img.height()) > lim:
            f = lim / max(img.width(), img.height())
            grande = img.scaled(int(img.width() * f), int(img.height() * f), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            fator = f
    g = grande.convertToFormat(QImage.Format_ARGB32)            # BGRA na memória (little-endian)
    w, h = g.width(), g.height()
    dados = bytes(g.constBits())[: g.bytesPerLine() * h]
    if g.bytesPerLine() != w * 4:
        dados = b"".join(dados[y * g.bytesPerLine(): y * g.bytesPerLine() + w * 4] for y in range(h))
    wr = DataWriter()
    wr.write_bytes(dados)
    bmp = SoftwareBitmap.create_copy_from_buffer(wr.detach_buffer(), BitmapPixelFormat.BGRA8, w, h,
                                                 BitmapAlphaMode.PREMULTIPLIED)

    async def rodar():
        return await eng.recognize_async(bmp)
    res = asyncio.run(rodar())
    out = []
    for i, ln in enumerate(res.lines):
        for wd in ln.words:
            r = wd.bounding_rect
            out.append(Palavra(wd.text, QRect(int(r.x / fator), int(r.y / fator), max(1, int(r.width / fator)),
                                              max(1, int(r.height / fator))), i))
    return out


# ------------------------------------------------------------------ Tesseract
def _tesseract_exe():
    cands = [shutil.which("tesseract")]
    if sys.platform == "win32":
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", "")):
            if base:
                cands.append(os.path.join(base, "Tesseract-OCR", "tesseract.exe"))
    return next((c for c in cands if c and os.path.exists(c)), None)


def _tesseract(img: QImage) -> list[Palavra]:
    exe = _tesseract_exe()
    if not exe:
        raise SemOCR("Nenhum OCR disponível neste computador")
    grande, fator = _preparar(img)
    d = tempfile.mkdtemp(prefix="instantia-ocr-")
    try:
        arq = os.path.join(d, "p.png")
        grande.save(arq)
        langs = subprocess.run([exe, "--list-langs"], capture_output=True, text=True, creationflags=SEM_JANELA).stdout
        idioma = "+".join(x for x in ("por", "eng") if x in langs.split()) or "eng"
        r = subprocess.run([exe, arq, "-", "-l", idioma, "--psm", "11", "tsv"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", creationflags=SEM_JANELA)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    out = []
    linhas = {}
    for row in r.stdout.splitlines()[1:]:
        c = row.split("\t")
        if len(c) < 12 or not c[11].strip():
            continue
        try:
            if float(c[10]) < 20:
                continue
            x, y, w, h = (int(v) for v in c[6:10])
        except ValueError:
            continue
        chave = (c[2], c[3], c[4])
        linhas.setdefault(chave, len(linhas))
        out.append(Palavra(c[11], QRect(int(x / fator), int(y / fator), max(1, int(w / fator)), max(1, int(h / fator))),
                           linhas[chave]))
    return out


def reconhecer(img: QImage) -> list[Palavra]:
    """Palavras com posição. Levanta SemOCR se não houver OCR no computador."""
    erros = []
    if sys.platform == "win32":
        try:
            return _windows(img)
        except SemOCR as e:
            erros.append(str(e))
        except Exception as e:  # noqa: BLE001
            erros.append(f"OCR do Windows: {e}")
    try:
        return _tesseract(img)
    except SemOCR as e:
        erros.append(str(e))
    raise SemOCR(erros[0] if erros else "Nenhum OCR disponível")


def texto(palavras: list[Palavra]) -> str:
    """Texto em linhas, na ordem de leitura."""
    linhas: dict[int, list[Palavra]] = {}
    for p in palavras:
        linhas.setdefault(p.linha, []).append(p)
    ordem = sorted(linhas.values(), key=lambda ps: (min(p.rect.y() for p in ps), min(p.rect.x() for p in ps)))
    return "\n".join(" ".join(p.texto for p in sorted(ps, key=lambda p: p.rect.x())) for ps in ordem)


def motor_disponivel() -> str | None:
    if sys.platform == "win32":
        try:
            from winrt.windows.media.ocr import OcrEngine
            if list(OcrEngine.available_recognizer_languages):
                return "Windows"
        except Exception:  # noqa: BLE001
            pass
    return "Tesseract" if _tesseract_exe() else None


__all__ = ["Palavra", "SemOCR", "reconhecer", "texto", "motor_disponivel"]
