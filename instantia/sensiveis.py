"""Ocultar dados: acha no print CPF, CNPJ, e-mail, telefone, valores em R$, linha digitável de boleto, cartão
e chave PIX aleatória, e devolve onde estão para serem borrados."""
from __future__ import annotations

import re

from PySide6.QtCore import QRect, QThread, Signal

from . import ocr


def _dig(s):
    return re.sub(r"\D", "", s)


def cpf_valido(s) -> bool:
    d = _dig(s)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for n in (9, 10):
        soma = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (soma * 10 % 11) % 10 != int(d[n]):
            return False
    return True


def cnpj_valido(s) -> bool:
    d = _dig(s)
    if len(d) != 14 or d == d[0] * 14:
        return False
    for n in (12, 13):
        pesos = list(range(n - 7, 1, -1)) + list(range(9, 1, -1))
        soma = sum(int(d[i]) * pesos[i] for i in range(n))
        dv = 11 - soma % 11
        if (0 if dv >= 10 else dv) != int(d[n]):
            return False
    return True


def luhn(s) -> bool:
    d = _dig(s)
    if not 13 <= len(d) <= 19:
        return False
    total = 0
    for i, c in enumerate(reversed(d)):
        n = int(c)
        if i % 2:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


# (nome, regex, validação) — a ordem importa: o primeiro que pegar um trecho fica com ele
PADROES = [
    ("linha digitável", re.compile(r"\d{5}[.\s]?\d{5}\s*\d{5}[.\s]?\d{6}\s*\d{5}[.\s]?\d{6}\s*\d\s*\d{14}"), None),
    ("linha digitável", re.compile(r"(?:\d{11}[-\s]?\d\s*){4}"), None),
    ("cartão", re.compile(r"(?<!\d)(?:\d{4}[ .-]?){3}\d{1,7}(?!\d)"), luhn),
    ("CNPJ", re.compile(r"(?<!\d)\d{2}\.\d{3}\.\d{3}\s?/\s?\d{4}\s?-\s?\d{2}(?!\d)"), None),
    ("CNPJ", re.compile(r"(?<!\d)\d{14}(?!\d)"), cnpj_valido),
    ("CPF", re.compile(r"(?<!\d)\d{3}\.\d{3}\.\d{3}\s?-\s?\d{2}(?!\d)"), None),
    ("CPF", re.compile(r"(?<!\d)\d{11}(?!\d)"), cpf_valido),
    ("CPF", re.compile(r"\*{3}\.?\d{3}\.?\d{3}-?\*{2}"), None),                 # CPF mascarado ainda identifica
    ("e-mail", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.I), None),
    ("chave PIX", re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I), None),
    ("telefone", re.compile(r"(?:\+?55\s?)?\(?\b\d{2}\)?\s?9?\s?\d{4}[-\s]\d{4}\b"), None),
    ("telefone", re.compile(r"(?:\+?55\s?)?\(\d{2}\)\s?9?\d{8}\b"), None),
    ("valor", re.compile(r"R\s?\$\s?-?\d{1,3}(?:\.\d{3})*(?:,\d{2})?|R\s?\$\s?-?\d+(?:,\d{2})?", re.I), None),
]


def achar(palavras: list[ocr.Palavra]) -> list[tuple[str, QRect]]:
    """[(tipo, retângulo em pixels da imagem)] dos dados sensíveis encontrados."""
    linhas: dict[int, list[ocr.Palavra]] = {}
    for p in palavras:
        linhas.setdefault(p.linha, []).append(p)
    achados = []
    for ps in linhas.values():
        ps.sort(key=lambda p: p.rect.x())
        texto, spans = "", []
        for p in ps:
            if texto:
                texto += " "
            spans.append((len(texto), len(texto) + len(p.texto), p))
            texto += p.texto
        usado = [False] * len(texto)
        for nome, rx, valida in PADROES:
            for m in rx.finditer(texto):
                a, b = m.span()
                while b > a and texto[b - 1] == " ":
                    b -= 1
                if any(usado[a:b]) or (valida and not valida(m.group(0))):
                    continue
                if nome == "telefone" and len(_dig(m.group(0))) < 10:
                    continue
                for i in range(a, b):
                    usado[i] = True
                ws = [p for (s, e, p) in spans if s < b and e > a]
                if not ws:
                    continue
                r = QRect(ws[0].rect)
                for w in ws[1:]:
                    r = r.united(w.rect)
                # se o dado é só parte da palavra (ex.: "CPF:123.456.789-09"), cobre só a parte dele
                if len(ws) == 1:
                    s, e, p = next(x for x in spans if x[2] is ws[0])
                    if e - s > 0 and (a > s or b < e):
                        cw = p.rect.width() / (e - s)
                        r = QRect(int(p.rect.x() + (max(a, s) - s) * cw), p.rect.y(),
                                  max(4, int((min(b, e) - max(a, s)) * cw) + 2), p.rect.height())
                achados.append((nome, r))
    return achados


_vivas: list = []          # threads em andamento (não podem ser destruídas antes de terminar)


def _guardar(th):
    _vivas.append(th)
    th.finished.connect(lambda: _vivas.remove(th) if th in _vivas else None)
    return th


class ThreadOcultar(QThread):
    terminou = Signal(list, str)          # [(tipo, QRect)], erro

    def __init__(self, imagem, pai=None):
        super().__init__(None)
        self.imagem = imagem
        _guardar(self)

    def run(self):
        try:
            self.terminou.emit(achar(ocr.reconhecer(self.imagem)), "")
        except ocr.SemOCR as e:
            self.terminou.emit([], str(e))
        except Exception as e:  # noqa: BLE001
            self.terminou.emit([], f"Erro no OCR: {e}")


class ThreadTexto(QThread):
    terminou = Signal(str, str)           # texto, erro

    def __init__(self, imagem, pai=None):
        super().__init__(None)
        self.imagem = imagem
        _guardar(self)

    def run(self):
        try:
            self.terminou.emit(ocr.texto(ocr.reconhecer(self.imagem)), "")
        except ocr.SemOCR as e:
            self.terminou.emit("", str(e))
        except Exception as e:  # noqa: BLE001
            self.terminou.emit("", f"Erro no OCR: {e}")


__all__ = ["achar", "cpf_valido", "cnpj_valido", "luhn", "ThreadOcultar", "ThreadTexto"]
