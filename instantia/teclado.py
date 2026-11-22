"""Tecla Print Screen (e combinações) para o Instantia, mesmo com a Ferramenta de Captura do Windows 11.

Usa um gancho de teclado de baixo nível (o mesmo método do ShareX e do Greenshot): a tecla chega primeiro aqui e,
quando o Instantia cuida dela, não segue para o Windows (então a Ferramenta de Captura não abre junto).
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QObject, QTimer, Signal

VK_SNAPSHOT = 0x2C
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0100, 0x0101, 0x0104, 0x0105
VK_SHIFT, VK_CONTROL, VK_MENU = 0x10, 0x11, 0x12


class Teclado(QObject):
    """Emite atalho("") / atalho("ctrl") / atalho("shift") quando Print Screen é pressionada."""
    atalho = Signal(str)

    def __init__(self):
        super().__init__()
        self._hook = None
        self._proc = None
        self.ativo = False

    def ligar(self) -> bool:
        if sys.platform != "win32" or self._hook:
            return bool(self._hook)
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        k = ctypes.windll.kernel32

        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD), ("flags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

        LRESULT = ctypes.c_ssize_t
        HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        u.CallNextHookEx.restype = LRESULT
        u.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        u.SetWindowsHookExW.restype = wintypes.HHOOK
        u.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
        u.GetAsyncKeyState.restype = ctypes.c_short
        k.GetModuleHandleW.restype = wintypes.HMODULE

        def proc(n, wparam, lparam):
            try:
                if n >= 0:
                    kb = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                    if kb.vkCode == VK_SNAPSHOT and self.ativo:
                        if wparam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                            alt = u.GetAsyncKeyState(VK_MENU) & 0x8000
                            if alt:                       # Alt+PrtSc: deixa com o Windows (janela ativa)
                                return u.CallNextHookEx(None, n, wparam, lparam)
                            mod = "ctrl" if u.GetAsyncKeyState(VK_CONTROL) & 0x8000 else (
                                "shift" if u.GetAsyncKeyState(VK_SHIFT) & 0x8000 else "")
                            QTimer.singleShot(0, lambda m=mod: self.atalho.emit(m))
                        return 1                          # não repassa: a Ferramenta de Captura não abre
            except Exception:  # noqa: BLE001
                pass
            return u.CallNextHookEx(None, n, wparam, lparam)

        self._proc = HOOKPROC(proc)
        self._hook = u.SetWindowsHookExW(13, self._proc, k.GetModuleHandleW(None), 0)   # WH_KEYBOARD_LL
        self.ativo = bool(self._hook)
        return self.ativo

    def desligar(self):
        if self._hook and sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.UnhookWindowsHookEx(self._hook)
        self._hook = None
        self.ativo = False


__all__ = ["Teclado"]
