# Instantia

Capturador de tela para Windows, em português: aperte **Print Screen**, escolha a área, marque e copie.

- Seleção de área ou de janela com um clique, lupa para acertar o pixel
- Edição na própria tela: seta, retângulo, elipse, linha, caneta, marca-texto, texto, numeração e borrão
- **Ocultar dados**: borra sozinho CPF, CNPJ, e-mail, telefone, valores, linha digitável, cartão e chave PIX
- **Copiar texto do print** (OCR do Windows, sem internet)
- Fixar o print na tela
- Gravação da tela em MP4 ou GIF (FFmpeg baixado na primeira gravação)
- Histórico, início com o Windows e atualização automática

## Atalhos

| Tecla | O que faz |
|---|---|
| Print Screen | Capturar área (clique = janela, Enter = tela inteira) |
| Ctrl + Print Screen | Copiar o texto de uma área |
| Shift + Print Screen | Gravar a tela (Print Screen de novo para parar) |
| Enter / Ctrl+C | Copiar · Ctrl+S salvar · Esc cancelar |
| A R E L P M T N B V | Seta, retângulo, elipse, linha, caneta, marca-texto, texto, número, borrão, mover |
| H / O / F | Ocultar dados / copiar texto / fixar na tela |

## Download

[Instantia-Setup.exe](https://github.com/lohanlilson/Instantia/releases/latest/download/Instantia-Setup.exe) — Windows 10 (1809) ou 11, 64 bits.

## Desenvolvimento

```
pip install -r requirements.txt
python main.py
python main.py --selftest saida.txt
python build.py            # executável + instalador (precisa do Inno Setup 6)
```

© 2026 Lohan Lilson S. Lopes — lohanlilson@gmail.com
