"""8.1 : icône de RF Technical Monitor (carré graphite, trace de spectre menthe, marqueur ambre sur la porteuse
surveillée). Écrit assets/icone.png (256) et assets/icone.ico (16 à 256 ; petites tailles simplifiées).
Lancer depuis la racine : python assets/make_icon.py (Pillow). Puis APP_ICON_PNG64 (tsm_core.py) à refaire."""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import math
from PIL import Image, ImageDraw, ImageFilter
S = 1024
def icon(S=1024, simple=False):
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # fond : carré arrondi graphite, léger dégradé vertical
    bg = Image.new("RGBA", (S, S))
    d = ImageDraw.Draw(bg)
    for y in range(S):
        t = y / S
        c = (int(30 - 10 * t), int(34 - 10 * t), int(42 - 12 * t), 255)
        d.line([(0, y), (S, y)], fill=c)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=255)
    im.paste(bg, (0, 0), mask)
    d = ImageDraw.Draw(im)
    m = S * 0.14
    x0, x1, yb, yt = m, S - m, S * 0.74, S * 0.24
    if not simple:   # grille discrète
        gr = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        gd = ImageDraw.Draw(gr)
        for i in range(1, 4):
            y = yt + (yb - yt) * i / 4
            gd.line([(x0, y), (x1, y)], fill=(255, 255, 255, 26), width=max(1, S // 256))
        im.alpha_composite(gr)
        d = ImageDraw.Draw(im)
    # trace du spectre : bruit de fond + 3 porteuses, la grande au centre-droit
    pts = []
    N = 220
    for i in range(N + 1):
        x = x0 + (x1 - x0) * i / N
        u = i / N
        y = 0.08 * math.sin(u * 61.0) * math.sin(u * 23.0) + 0.04 * math.sin(u * 137.0)
        k = 1.9 if simple else 1.0
        if simple:
            y *= 0.4
        for c, h, w in ((0.24, 0.38, 0.030), (0.62, 0.95, 0.028), (0.84, 0.50, 0.024)):
            y += h * math.exp(-((u - c) / (w * k)) ** 2)
        pts.append((x, yb - (yb - yt) * (0.10 + 0.8 * max(0.0, y)) ))
    # remplissage sous la trace
    fill = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fill)
    fd.polygon(pts + [(x1, yb), (x0, yb)], fill=(79, 209, 197, 60))
    im.alpha_composite(fill)
    lw = int(S * (0.045 if simple else 0.026))
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).line(pts, fill=(79, 209, 197, 160), width=lw * 3, joint="curve")
    glow = glow.filter(ImageFilter.GaussianBlur(S * 0.02))
    im.alpha_composite(glow)
    d = ImageDraw.Draw(im)
    d.line(pts, fill=(120, 236, 224, 255), width=lw, joint="curve")
    # marqueur ambre sur la porteuse surveillée
    cx = x0 + (x1 - x0) * 0.62
    py = min(p[1] for p in pts)
    d.line([(cx, py - S * 0.07), (cx, yb + S * 0.04)], fill=(255, 179, 0, 255), width=max(2, int(S * 0.014)))
    r = S * (0.05 if simple else 0.038)
    d.ellipse([cx - r, py - S * 0.07 - r * 2.1, cx + r, py - S * 0.07], fill=(255, 179, 0, 255))
    # ligne de seuil pointillée
    if not simple:
        th = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        td = ImageDraw.Draw(th)
        ty = yb - (yb - yt) * 0.42
        x = x0
        while x < x1:
            td.line([(x, ty), (min(x + S * 0.03, x1), ty)], fill=(255, 107, 107, 170), width=max(1, int(S * 0.008)))
            x += S * 0.05
        im.alpha_composite(th)
    return im
big = icon(1024)
big.resize((256, 256), Image.LANCZOS).save("icone.png")
small = icon(1024, simple=True)
sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
imgs = {s: (small if s[0] <= 48 else big).resize(s, Image.LANCZOS) for s in sizes}
imgs[(256, 256)].save("icone.ico", sizes=sizes, append_images=[imgs[s] for s in sizes[:-1]])
print("icone.png et icone.ico écrits")
