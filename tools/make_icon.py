"""Generate assets/netvanta.ico (development helper; needs Pillow)."""

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 512
OUT = Path(__file__).resolve().parents[1] / "assets" / "netvanta.ico"


def build() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # rounded dark-blue tile with a vertical gradient
    tile = Image.new("RGBA", (SIZE, SIZE))
    tdraw = ImageDraw.Draw(tile)
    for y in range(SIZE):
        t = y / SIZE
        tdraw.line([(0, y), (SIZE, y)], fill=(int(20 + 20 * t), int(60 + 50 * t), int(150 + 60 * t), 255))
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle((16, 16, SIZE - 16, SIZE - 16), radius=110, fill=255)
    img.paste(tile, (0, 0), mask)
    # pulse line forming a stylised "N"
    pts = [(110, 380), (110, 140), (256, 380), (256, 140), (402, 140), (402, 380)]
    draw.line(pts[:5], fill=(255, 255, 255, 255), width=40, joint="curve")
    draw.line([(256, 140), (402, 380)], fill=(94, 234, 212, 255), width=40)
    for x, y in ((110, 380), (110, 140), (402, 380)):
        draw.ellipse((x - 20, y - 20, x + 20, y + 20), fill=(255, 255, 255, 255))
    return img


if __name__ == "__main__":
    OUT.parent.mkdir(exist_ok=True)
    build().save(OUT, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("wrote", OUT)
