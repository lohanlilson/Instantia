import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter, QFont, QColor
from PySide6.QtCore import Qt
app = QApplication([])
from instantia import sensiveis, ocr
linhas = ["Cliente: Maria de Souza", "CPF: 123.456.789-09", "CNPJ 53.176.704/0001-86", "E-mail: maria.souza@empresa.com.br",
          "Telefone: (62) 98119-7966", "Valor total: R$ 1.500,00", "Data: 15/11/2026",
          "Boleto: 23793.38128 60000.000003 00000.000400 1 84340000150000"]
img = QImage(900, 40 * len(linhas) + 20, QImage.Format_RGB32); img.fill(QColor("white"))
g = QPainter(img); f = QFont("DejaVu Sans"); f.setPixelSize(15); g.setFont(f); g.setPen(QColor("#222"))
for i, t in enumerate(linhas): g.drawText(20, 34 + 40 * i, t)
g.end()
pal = ocr.reconhecer(img)
print(ocr.texto(pal))
ach = sensiveis.achar(pal)
for t, r in ach: print(t, r)
tipos = {t for t, _ in ach}
esperado = {"CPF", "CNPJ", "e-mail", "telefone", "valor", "linha digitável"}
print("faltou:", esperado - tipos)
assert sensiveis.cpf_valido("123.456.789-09") and not sensiveis.cpf_valido("123.456.789-00")
assert sensiveis.cnpj_valido("53176704000186") and sensiveis.luhn("4111 1111 1111 1111")
