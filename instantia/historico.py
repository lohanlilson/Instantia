"""Histórico: cópia de cada print (e de cada gravação salva), para achar de novo depois."""
from __future__ import annotations

import os
import time

from PySide6.QtGui import QImage

from . import pasta_dados

EXT = (".png", ".jpg", ".jpeg", ".gif", ".mp4")


def pasta():
    return pasta_dados("Historico")


def guardar(img: QImage, limite: int = 300) -> str:
    nome = time.strftime("%Y-%m-%d %H-%M-%S") + f"-{int(time.time() * 1000) % 1000:03d}.png"
    c = os.path.join(pasta(), nome)
    img.save(c, "PNG")
    limpar(limite)
    return c


def registrar_arquivo(caminho: str, limite: int = 300):
    """Gravações e arquivos salvos fora do histórico: guarda só um atalho (arquivo .lnk.txt com o caminho)."""
    nome = time.strftime("%Y-%m-%d %H-%M-%S") + "-arquivo.txt"
    with open(os.path.join(pasta(), nome), "w", encoding="utf-8") as f:
        f.write(caminho)
    limpar(limite)


def itens() -> list[str]:
    """Caminhos, do mais novo para o mais antigo (arquivos que não existem mais ficam de fora)."""
    out = []
    for n in sorted(os.listdir(pasta()), reverse=True):
        c = os.path.join(pasta(), n)
        if n.endswith("-arquivo.txt"):
            try:
                alvo = open(c, encoding="utf-8").read().strip()
            except OSError:
                continue
            if os.path.exists(alvo):
                out.append(alvo)
        elif n.lower().endswith(EXT):
            out.append(c)
    return out


def limpar(limite: int):
    nomes = sorted(os.listdir(pasta()), reverse=True)
    for n in nomes[max(limite, 1):]:
        try:
            os.remove(os.path.join(pasta(), n))
        except OSError:
            pass


def apagar(caminho: str):
    """Tira do histórico (não apaga arquivos salvos pela pessoa em outras pastas)."""
    p = os.path.normcase(os.path.abspath(caminho))
    for n in os.listdir(pasta()):
        c = os.path.join(pasta(), n)
        if os.path.normcase(os.path.abspath(c)) == p:
            os.remove(c)
            return
        if n.endswith("-arquivo.txt"):
            try:
                if os.path.normcase(os.path.abspath(open(c, encoding="utf-8").read().strip())) == p:
                    os.remove(c)
                    return
            except OSError:
                pass


__all__ = ["pasta", "guardar", "registrar_arquivo", "itens", "limpar", "apagar"]
