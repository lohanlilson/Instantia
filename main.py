"""Instantia — ponto de entrada.

  Instantia.exe                         abre o programa (ou mostra a janela, se já estiver aberto)
  Instantia.exe --bandeja               inicia só perto do relógio (usado ao iniciar com o Windows)
  Instantia.exe --capturar [modo]       abre a captura (imagem, texto ou gravar)
  Instantia.exe --selftest saida.txt    autoteste (usado na publicação)
  Instantia.exe --run-update <inst> <pid>   uso interno da atualização automática
"""
import sys


def _limpar_sobras_de_atualizacao():
    import os
    for raiz, _, arquivos in os.walk(os.path.dirname(sys.executable)):
        for nome in arquivos:
            if nome.endswith(".antigo"):
                try:
                    os.remove(os.path.join(raiz, nome))
                except OSError:
                    pass


def main():
    argv = sys.argv
    if "--run-update" in argv:
        from instantia.atualizador import ajudante_atualizacao
        return ajudante_atualizacao(argv)
    if "--selftest" in argv:
        from instantia.selftest import executar
        return executar(argv)
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Instantia.App")
        try:   # nitidez em monitores com escala diferente (o Qt também pede, isto garante antes de tudo)
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except Exception:
            pass

    from PySide6.QtCore import QCoreApplication, Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    from instantia import APP_NAME
    from instantia.app import Controle, instancia_aberta
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    modo = None
    if "--capturar" in argv:
        i = argv.index("--capturar")
        modo = argv[i + 1] if len(argv) > i + 1 and not argv[i + 1].startswith("-") else "imagem"
    if instancia_aberta(f"capturar:{modo}" if modo else ("nada" if "--bandeja" in argv else "mostrar")):
        return 0
    if getattr(sys, "frozen", False):
        _limpar_sobras_de_atualizacao()
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.CreateMutexW(None, False, "Instantia_Running")   # o instalador usa para saber se está aberto
    from PySide6.QtGui import QIcon
    from instantia import resource
    app.setWindowIcon(QIcon(resource("assets", "instantia.png")))
    ctl = Controle(app, iniciar_na_bandeja="--bandeja" in argv or bool(modo))
    QCoreApplication.instance()._ctl = ctl
    if modo:
        from PySide6.QtCore import QTimer
        QTimer.singleShot(300, lambda: ctl.capturar(modo))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
