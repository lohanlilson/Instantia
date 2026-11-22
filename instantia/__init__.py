"""Instantia — capturador de tela."""
import os
import sys

__version__ = "1.0.0"
APP_NAME = "Instantia"
APP_ID = "Instantia"
AUTHOR = "Lohan Lilson S. Lopes"
EMAIL = "lohanlilson@gmail.com"
COPYRIGHT = f"© 2026 {AUTHOR}"
# Repositório do GitHub (público) onde as versões são publicadas em Releases
UPDATE_REPO = "lohanlilson/Instantia"


def resource(*parts):
    """Caminho de um recurso (funciona no código-fonte e no executável do PyInstaller)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, *parts)


def pasta_dados(*partes):
    """%LOCALAPPDATA%\\Instantia\\... (criada se não existir)."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~/.local/share")
    p = os.path.join(base, "Instantia", *partes)
    os.makedirs(p, exist_ok=True)
    return p
