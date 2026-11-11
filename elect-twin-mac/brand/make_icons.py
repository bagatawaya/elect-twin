"""Render the selected editable Counterpart geometry into macOS icon assets."""
from pathlib import Path
from PIL import Image, ImageDraw
import subprocess

ROOT = Path(__file__).resolve().parent
SIZE = 1024
image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((32, 32, 992, 992), radius=220, fill="#f6f6f6")
draw.rounded_rectangle((222, 198, 460, 826), radius=119, fill="#2b1703")
draw.rounded_rectangle((564, 198, 802, 826), radius=119, fill="#b84a1b")
for x in (341, 683):
    draw.ellipse((x - 34, 348, x + 34, 416), fill="#ffffff")
for x in (302, 644):
    draw.rounded_rectangle((x, 548, x + 78, 566), radius=9, fill="#ffffff")
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
print(ROOT / "AppIcon.icns")
