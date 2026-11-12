"""Render the OpenTwin Porcelain & Ink geometry into macOS icon assets."""
from pathlib import Path
from PIL import Image, ImageDraw
import subprocess

ROOT = Path(__file__).resolve().parent
SIZE = 1024
image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)

# Base Squircle Container
draw.rounded_rectangle((48, 48, 976, 976), radius=210, fill="#F8FAFC", outline="#CBD5E1", width=6)

# Human Circle (Deep Slate-Ink #0F172A)
draw.ellipse((190, 292, 630, 732), fill="#0F172A")
# Human Core Dot
draw.ellipse((380, 482, 440, 542), fill="#FFFFFF")

# AI Twin Squircle (Serene Teal #0F766E)
draw.rounded_rectangle((470, 292, 910, 732), radius=130, fill="#0F766E")
# AI Twin Spark (✦)
draw.rounded_rectangle((672, 420, 708, 604), radius=16, fill="#FFFFFF")
draw.rounded_rectangle((598, 494, 782, 530), radius=16, fill="#FFFFFF")

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
