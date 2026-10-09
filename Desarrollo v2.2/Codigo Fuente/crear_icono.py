"""Genera los íconos del programa a partir de recursos/logo_origen.jpeg (requiere Pillow).

Recorta el cuadrado redondeado del logo, vuelve transparentes las esquinas y
escribe pms/assets/logo_24.png, logo_64.png, logo_128.png e icono.ico.
"""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "recursos", "logo_origen.jpeg")
OUT = os.path.join(HERE, "pms", "assets")


def main():
    im = Image.open(SRC).convert("RGB")
    w, h = im.size
    # el fondo exterior es claro: localiza el cuadrado oscuro del logo
    px = im.load()
    dark = [(x, y) for y in range(0, h, 2) for x in range(0, w, 2) if sum(px[x, y]) < 600]
    x0 = min(p[0] for p in dark)
    x1 = max(p[0] for p in dark)
    y0 = min(p[1] for p in dark)
    y1 = max(p[1] for p in dark)
    side = max(x1 - x0, y1 - y0)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    box = (cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2)
    sq = im.crop(box).resize((512, 512), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (512 * 4, 512 * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, 512 * 4 - 1, 512 * 4 - 1), radius=int(512 * 4 * 0.19), fill=255)
    sq.putalpha(mask.resize((512, 512), Image.LANCZOS))
    os.makedirs(OUT, exist_ok=True)
    for s in (24, 32, 64, 128):
        sq.resize((s, s), Image.LANCZOS).save(os.path.join(OUT, f"logo_{s}.png"))
    sq.save(os.path.join(OUT, "icono.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128),
                                                   (256, 256)])
    print("Íconos generados en", OUT)


if __name__ == "__main__":
    main()
