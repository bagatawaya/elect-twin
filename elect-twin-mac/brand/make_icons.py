"""Render the canonical OpenTwin O+T monogram into macOS icon assets."""
from pathlib import Path
from PIL import Image, ImageDraw
import subprocess

ROOT = Path(__file__).resolve().parent
SIZE = 1024
image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)

# 1. Outer Container Badge (circle cx=32 cy=32 r=29, fill=#F0FDFA, stroke=#0F766E)
# Scale factor = 1024 / 64 = 16 -> r = 464, stroke = 56
draw.ellipse((48, 48, 976, 976), fill="#F0FDFA", outline="#0F766E", width=56)

# 2. 'O' Ellipse (ellipse cx=23 cy=32 rx=8 ry=12, stroke=#0F172A stroke-width=4)
# cx=368, cy=512, rx=128, ry=192 -> (240, 320, 496, 704), stroke = 64
draw.ellipse((240, 320, 496, 704), outline="#0F172A", width=64)

# 3. 'T' Path (path d="M34 20h16M42 20v24", stroke=#0F766E stroke-width=4 round caps)
# Horizontal bar: (544, 320) to (800, 320)
draw.line([(544, 320), (800, 320)], fill="#0F766E", width=64)
draw.ellipse((544 - 32, 320 - 32, 544 + 32, 320 + 32), fill="#0F766E")
draw.ellipse((800 - 32, 320 - 32, 800 + 32, 320 + 32), fill="#0F766E")

# Vertical bar: (672, 320) to (672, 704)
draw.line([(672, 320), (672, 704)], fill="#0F766E", width=64)
draw.ellipse((672 - 32, 704 - 32, 672 + 32, 704 + 32), fill="#0F766E")

image.save(ROOT / "AppIcon.png")

iconset = ROOT / "AppIcon.iconset"
iconset.mkdir(exist_ok=True)
for points in (16, 32, 128, 256, 512):
    for scale in (1, 2):
        pixels = points * scale
        resized = image.resize((pixels, pixels), Image.Resampling.LANCZOS)
        suffix = "" if scale == 1 else "@2x"
        resized.save(iconset / f"icon_{points}x{points}{suffix}.png")

subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(ROOT / "AppIcon.icns")], check=True)
print(f"Generated {ROOT / 'AppIcon.icns'}")
