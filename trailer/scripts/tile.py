# Tile stills into one review sheet: python3 scripts/tile.py <out.jpg> <cols> <width> <files...>
import sys, os
from PIL import Image, ImageDraw
out, cols, tw = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
fs = sys.argv[4:]
def key(f):
    b = os.path.basename(f)
    try: return float(b[1:].rsplit('.', 1)[0])
    except ValueError: return 0
fs.sort(key=key)
th = round(tw * 9 / 16)
rows = (len(fs) + cols - 1) // cols
sheet = Image.new('RGB', (cols * (tw + 4), rows * (th + 4)), (40, 40, 40))
d = ImageDraw.Draw(sheet)
for i, f in enumerate(fs):
    im = Image.open(f).convert('RGB').resize((tw, th), Image.LANCZOS)
    x, y = (i % cols) * (tw + 4), (i // cols) * (th + 4)
    sheet.paste(im, (x, y))
    lab = os.path.basename(f).rsplit('.', 1)[0]
    try: lab = f'{lab}  b{float(lab[1:]) * 2:.1f}'
    except ValueError: pass
    d.rectangle([x, y, x + 8 * len(lab) + 8, y + 15], fill=(0, 0, 0)); d.text((x + 4, y + 2), lab, fill=(255, 255, 0))
sheet.save(out, quality=86)
print(out, sheet.size)
