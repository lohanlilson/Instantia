"""Identidade visual do Instantia (mesma família do Dispersio PDF e do Convergio).

Marca: a área selecionada, em tracejado de vidro, com a cruz do cursor em dourado no canto.
Gera: logo.png (1024), instantia.png (256), instantia.ico (16–256) e as imagens do instalador.
"""
import math
import os

from PIL import Image, ImageDraw, ImageFilter, ImageChops

S = 2048
U = S / 1024
INDIGO_1, INDIGO_2 = (24, 16, 70), (70, 38, 176)
VIOLETA, AZUL, DOURADO = (186, 140, 255), (100, 150, 255), (255, 182, 80)


def u(*v):
    return [x * U for x in v]


def gradiente(size, stops, angulo=90):
    """Gradiente linear em qualquer ângulo; stops = [(pos, (r,g,b[,a])), ...]."""
    n = 256
    g = Image.new("RGBA", (n, n))
    px = g.load()
    ca, sa = math.cos(math.radians(angulo)), math.sin(math.radians(angulo))
    for y in range(n):
        for x in range(n):
            t = ((x / (n - 1) - .5) * ca + (y / (n - 1) - .5) * sa) / (abs(ca) * .5 + abs(sa) * .5) * .5 + .5
            t = min(1, max(0, t))
            for i in range(len(stops) - 1):
                p0, c0 = stops[i]
                p1, c1 = stops[i + 1]
                if p0 <= t <= p1:
                    f = (t - p0) / max(1e-6, p1 - p0)
                    c0 = c0 + (255,) * (4 - len(c0))
                    c1 = c1 + (255,) * (4 - len(c1))
                    px[x, y] = tuple(int(c0[j] + (c1[j] - c0[j]) * f) for j in range(4))
                    break
    return g.resize(size, Image.BICUBIC)


def radial(centro, raio, cor, forca=1.0, expo=2.0):
    m = Image.new("L", (160, 160), 0)
    cx, cy, r = centro[0] / S * 159, centro[1] / S * 159, raio / S * 159
    px = m.load()
    for y in range(160):
        for x in range(160):
            px[x, y] = int(255 * forca * max(0.0, 1 - math.hypot(x - cx, y - cy) / r) ** expo)
    c = Image.new("RGBA", (S, S), cor + (0,))
    c.putalpha(m.resize((S, S), Image.BICUBIC))
    return c


def preencher(mascara, cor_ou_grad):
    if isinstance(cor_ou_grad, tuple):
        cam = Image.new("RGBA", (S, S), cor_ou_grad[:3] + (255,))
        a = mascara if len(cor_ou_grad) == 3 else mascara.point(lambda v: v * cor_ou_grad[3] // 255)
    else:
        cam = cor_ou_grad.copy()
        a = ImageChops.multiply(cam.getchannel("A"), mascara)
    cam.putalpha(a)
    return cam


def arredondar(mascara, raio):
    """Arredonda os cantos de uma máscara (desfoque + limiar)."""
    m = mascara.filter(ImageFilter.GaussianBlur(raio)).point(lambda v: 255 if v > 128 else 0)
    return m.filter(ImageFilter.GaussianBlur(1.2 * U))


def poligono(pts, raio=0):
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).polygon([(x * U, y * U) for x, y in pts], fill=255)
    return arredondar(m, raio * U) if raio else m


def brilho(camada, raio, vezes=2):
    g = camada.filter(ImageFilter.GaussianBlur(raio * U))
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    for _ in range(vezes):
        out.alpha_composite(g)
    return out


def sombra(mascara, raio=22, dy=14, forca=0.5):
    a = mascara.filter(ImageFilter.GaussianBlur(raio * U)).point(lambda v: int(v * forca))
    c = Image.new("RGBA", (S, S), (8, 4, 30, 0))
    c.putalpha(a)
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.alpha_composite(c, (0, int(dy * U)))
    return out


CAIXA = u(56, 56, 968, 968)
RAIO = int(210 * U)


def fundo():
    img = gradiente((S, S), [(0, INDIGO_1), (1, INDIGO_2)], 60)
    img.alpha_composite(radial(u(512, 470), 520 * U, (124, 58, 237), 0.9))
    img.alpha_composite(radial(u(512, 980), 420 * U, (10, 6, 40), 0.55))
    return img


def acabar(img):
    borda = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(borda).rounded_rectangle(CAIXA, radius=RAIO, outline=(255, 255, 255, 46), width=int(5 * U))
    # reflexo suave no topo
    topo = gradiente((S, S), [(0, (255, 255, 255, 34)), (0.42, (255, 255, 255, 0)), (1, (255, 255, 255, 0))], 90)
    img.alpha_composite(topo)
    img.alpha_composite(borda)
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).rounded_rectangle(CAIXA, radius=RAIO, fill=255)
    img.putalpha(ImageChops.multiply(img.getchannel("A"), m))
    return img.resize((1024, 1024), Image.LANCZOS)


def feixe_cam(p0, p1, w0, w1, cor, a0=40, a1=255):
    """Feixe afunilado com transparência crescente até p1."""
    m = Image.new("L", (S, S), 0)
    (x0, y0), (x1, y1) = (p0[0] * U, p0[1] * U), (p1[0] * U, p1[1] * U)
    dx, dy = x1 - x0, y1 - y0
    n = math.hypot(dx, dy)
    nx, ny = -dy / n, dx / n
    w0, w1 = w0 * U / 2, w1 * U / 2
    ImageDraw.Draw(m).polygon([(x0 + nx * w0, y0 + ny * w0), (x1 + nx * w1, y1 + ny * w1),
                               (x1 - nx * w1, y1 - ny * w1), (x0 - nx * w0, y0 - ny * w0)], fill=255)
    # gradiente de alfa ao longo do feixe
    g = Image.new("L", (S, S), 0)
    steps = 60
    gd = ImageDraw.Draw(g)
    for i in range(steps, -1, -1):
        t = i / steps
        cx, cy = x0 + dx * t, y0 + dy * t
        r = (w0 + (w1 - w0) * t) * 1.6 + 6
        gd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=int(a0 + (a1 - a0) * t))
    m = ImageChops.multiply(m, g.filter(ImageFilter.GaussianBlur(10 * U)))
    c = Image.new("RGBA", (S, S), cor + (0,))
    c.putalpha(m)
    return c



def seta_mask(topo, haste_w, haste_y1, ponta_y0, ponta_w, ponta_y1, raio, cx=512):
    m = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(m)
    d.rectangle(u(cx - haste_w / 2, topo, cx + haste_w / 2, haste_y1), fill=255)
    d.polygon([tuple(u(cx - ponta_w / 2, ponta_y0)), tuple(u(cx + ponta_w / 2, ponta_y0)), tuple(u(cx, ponta_y1))], fill=255)
    return arredondar(m, raio * U)


def contorno_de(m, enc=14, forca=.45):
    inn = m.filter(ImageFilter.MinFilter(int(enc * U) // 2 * 2 + 1))
    return ImageChops.subtract(m, inn).point(lambda v: int(v * forca))


# C2: rastros coloridos convergindo para uma seta branca de vidro
def opcao_c2():
    img = fundo()
    r = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    for x0, x1, w, cor in ((150, 430, 40, VIOLETA), (280, 460, 30, VIOLETA), (400, 490, 24, AZUL), (512, 512, 36, (235, 230, 255)),
                           (624, 534, 24, AZUL), (744, 564, 30, DOURADO), (874, 594, 40, DOURADO)):
        r.alpha_composite(feixe_cam((x0, -20), (x1, 470), w, w * .55, cor, 0, 240))
    img.alpha_composite(brilho(r, 24, 2))
    img.alpha_composite(r)
    seta = seta_mask(400, 170, 640, 590, 520, 856, 26)
    img.alpha_composite(sombra(seta, 30, 22, .7))
    g = gradiente((S, S), [(0, (255, 255, 255)), (0.7, (232, 222, 255)), (1, (205, 186, 255))], 90)
    img.alpha_composite(brilho(preencher(seta, (200, 170, 255)), 34, 1))
    img.alpha_composite(preencher(seta, g))
    img.alpha_composite(preencher(contorno_de(seta, 16, .9), (255, 255, 255)))
    return acabar(img)



def cantos_mask(m0=226, m1=798, braco=210, esp=60, raio=14):
    m = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(m)
    for (cx, cy, sx, sy) in ((m0, m0, 1, 1), (m1, m0, -1, 1), (m0, m1, 1, -1), (m1, m1, -1, -1)):
        x0, x1 = sorted((cx, cx + sx * braco))
        y0, y1 = sorted((cy, cy + sy * esp))
        d.rectangle(u(x0, y0, x1, y1), fill=255)
        x0, x1 = sorted((cx, cx + sx * esp))
        y0, y1 = sorted((cy, cy + sy * braco))
        d.rectangle(u(x0, y0, x1, y1), fill=255)
    return arredondar(m, raio * U)


def opcao_instantia():
    img = fundo()
    # clarão no centro: raios coloridos saindo do ponto da captura
    r = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    c = (512, 512)
    for ang, comp, w, cor in ((-90, 250, 52, (240, 236, 255)), (90, 250, 52, (240, 236, 255)),
                              (0, 260, 52, DOURADO), (180, 260, 52, VIOLETA),
                              (-45, 170, 34, AZUL), (135, 170, 34, AZUL), (45, 170, 34, DOURADO), (-135, 170, 34, VIOLETA)):
        a = math.radians(ang)
        fim = (c[0] + comp * math.cos(a), c[1] + comp * math.sin(a))
        r.alpha_composite(feixe_cam(fim, c, 2, w, cor, 0, 255))
    img.alpha_composite(brilho(r, 26, 2))
    img.alpha_composite(r)
    img.alpha_composite(radial(u(512, 512), 150 * U, (255, 255, 255), 1.0, 2.4))
    nucleo = Image.new("L", (S, S), 0)
    ImageDraw.Draw(nucleo).ellipse(u(470, 470, 554, 554), fill=255)
    img.alpha_composite(preencher(nucleo.filter(ImageFilter.GaussianBlur(4 * U)), (255, 255, 255)))
    # cantos do visor, em vidro branco
    cantos = cantos_mask()
    img.alpha_composite(sombra(cantos, 26, 18, .65))
    g = gradiente((S, S), [(0, (255, 255, 255)), (0.7, (232, 222, 255)), (1, (205, 186, 255))], 90)
    img.alpha_composite(brilho(preencher(cantos, (200, 170, 255)), 30, 1))
    img.alpha_composite(preencher(cantos, g))
    img.alpha_composite(preencher(contorno_de(cantos, 14, .9), (255, 255, 255)))
    return acabar(img)


def vidro(img, m, forca_sombra=.65):
    img.alpha_composite(sombra(m, 26, 18, forca_sombra))
    g = gradiente((S, S), [(0, (255, 255, 255)), (0.7, (232, 222, 255)), (1, (205, 186, 255))], 90)
    img.alpha_composite(brilho(preencher(m, (200, 170, 255)), 30, 1))
    img.alpha_composite(preencher(m, g))
    img.alpha_composite(preencher(contorno_de(m, 14, .9), (255, 255, 255)))


def opcao_area():
    """Área selecionada (tracejado de vidro) com a cruz do cursor em dourado no canto."""
    img = fundo()
    m = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(m)
    x0, y0, x1, y1 = 230, 260, 740, 700
    w, seg, gap = 44, 70, 44
    for (a, b, horiz, fixo) in ((x0, x1, True, y0), (x0, x1, True, y1), (y0, y1, False, x0), (y0, y1, False, x1)):
        t = a
        while t < b:
            e = min(t + seg, b)
            if horiz:
                d.rectangle(u(t, fixo - w / 2, e, fixo + w / 2), fill=255)
            else:
                d.rectangle(u(fixo - w / 2, t, fixo + w / 2, e), fill=255)
            t += seg + gap
    vidro(img, arredondar(m, 10 * U))
    cruz = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(cruz)
    cx, cy = 740, 700
    d.rectangle(u(cx - 22, cy - 150, cx + 22, cy + 150), fill=255)
    d.rectangle(u(cx - 150, cy - 22, cx + 150, cy + 22), fill=255)
    r = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    r.alpha_composite(preencher(arredondar(cruz, 8 * U), gradiente((S, S), [(0, DOURADO), (1, (255, 120, 90))], 45)))
    img.alpha_composite(brilho(r, 26, 2))
    img.alpha_composite(r)
    return acabar(img)


def icone():
    return opcao_area()


if __name__ == "__main__":
    aqui = os.path.dirname(os.path.abspath(__file__))
    grande = icone()
    grande.save(os.path.join(aqui, "logo.png"))
    grande.resize((256, 256), Image.LANCZOS).save(os.path.join(aqui, "instantia.png"))
    tamanhos = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    imgs = [grande.resize((t, t), Image.LANCZOS) for t in tamanhos]
    imgs[-1].save(os.path.join(aqui, "instantia.ico"), sizes=[(t, t) for t in tamanhos], append_images=imgs[:-1])
    # imagens do instalador (Inno Setup): lateral 328x628 e pequena 110x116
    lateral = gradiente((328, 628), [(0, INDIGO_1), (1, INDIGO_2)], 70)
    lateral.alpha_composite(grande.resize((220, 220), Image.LANCZOS), (54, 160))
    lateral.convert("RGB").save(os.path.join(aqui, "wizard.bmp"))
    pequena = Image.new("RGBA", (110, 116), (255, 255, 255, 255))
    pequena.alpha_composite(grande.resize((100, 100), Image.LANCZOS), (5, 8))
    pequena.convert("RGB").save(os.path.join(aqui, "wizard_small.bmp"))
    print("ícones gerados")
