"""Tile qa/shots/<tag>/*.png into one image: python scripts/montage.py <tag> [tag2] -> qa/shots/<tag>[-vs-<tag2>].png"""
import sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
from PIL import Image, ImageDraw
tags = sys.argv[1:]
names = ['lateral-l', 'inferior', 'medial-l-brainstem', 'syndrome-wallenberg']
# fall back to whatever the tags actually hold, in common, when the default set is not there
if not all((Path(f'qa/shots/{t}/{n}.png').exists() for t in tags for n in names)):
    common = set.intersection(*[{p.stem for p in Path(f'qa/shots/{t}').glob('*.png')} for t in tags])
    names = sorted(common)
    if not names:
        raise SystemExit(f"no shot names in common between {tags}")
rows = []
for t in tags:
    rows.append([Image.open(f'qa/shots/{t}/{n}.png').convert('RGB') for n in names])
w, h = rows[0][0].size
sc = 0.5
tw, th = int(w * sc), int(h * sc)
out = Image.new('RGB', (tw * len(names), (th + 24) * len(rows)), 'black')
d = ImageDraw.Draw(out)
for r, (t, imgs) in enumerate(zip(tags, rows)):
    for c, (n, im) in enumerate(zip(names, imgs)):
        out.paste(im.resize((tw, th)), (c * tw, r * (th + 24) + 24))
        d.text((c * tw + 6, r * (th + 24) + 6), f'{t} / {n}', fill='white')
p = f"qa/shots/{'-vs-'.join(tags).replace('/', '-')}.png"
Path(p).parent.mkdir(parents=True, exist_ok=True); out.save(p); print(p)
