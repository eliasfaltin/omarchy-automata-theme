"""Theme-switcher preview: the escapement still with a terminal in the palette."""
import cairo
from common import *

import os
import sys

# Usage: [AUTOMATA_MODE=light] python3 preview_card.py OUT.png
OUT = sys.argv[1]
SRC = os.path.join(VARIANTS, VARIANT_DIR, "2-escapement.png")
if LIGHT:
    C = dict(red="#a94a38", yellow="#857427", orange="#9c5f35", green="#5e6b3c", cyan="#4e6e64",
             blue="#4d5f73", magenta="#7d5a66", brown="#6b5439", bred="#c0563f", byellow="#a08e42",
             bgreen="#75844c", bcyan="#62877b", bblue="#61768c", bmagenta="#95707d")
else:
    C = dict(red="#c96b57", yellow="#c2b169", orange="#c98a5e", green="#9da67a", cyan="#8fa99f",
             blue="#8b9bab", magenta="#ab8e96", brown="#8c7556", bred="#d98a77", byellow="#d3c47e",
             bgreen="#b3bb90", bcyan="#a9c0b6", bblue="#a6b4c2", bmagenta="#c0a6ad")

src = cairo.ImageSurface.create_from_png(SRC)
surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
ctx = cairo.Context(surf)
ctx.set_source_surface(src, 0, 0)
ctx.paint()

# Terminal window, placed over the empty middle of the plate.
x, y, w, h = 1060, 1180, 1480, 820
ctx.rectangle(x, y, w, h)
rgba(ctx, BG, 0.97)
ctx.fill_preserve()
ctx.set_line_width(4)
rgba(ctx, INK, 1)
ctx.stroke()

lines = [
    [("~/automata", C["blue"]), (" > ", C["green"]), ("owe status", INK)],
    [("engine ", DIM), ("shell", C["green"]), ("   intro ", DIM), ("ok", C["cyan"]), ("   loop ", DIM), ("60 s", C["yellow"])],
    [],
    [("~/automata", C["blue"]), (" > ", C["green"]), ("ls backgrounds", INK)],
    [("1-rule-110.png  2-escapement.png  3-life.png", INK)],
    [("loop-1-rule-110.mp4  ", C["cyan"]), ("loop-3-life.mp4", C["cyan"])],
    [("error ", C["red"]), ("none  ", DIM), ("warn ", C["yellow"]), ("none  ", DIM), ("seams ", C["green"]), ("0 px", INK)],
    [],
]
ctx.select_font_face(FONT)
yy = y + 90
for ln in lines:
    xx = x + 60
    for s, col in ln:
        c = hexrgb(col) if isinstance(col, str) else col
        ctx.set_font_size(38)
        rgba(ctx, c, 1)
        ctx.move_to(xx, yy)
        ctx.show_text(s)
        xx += ctx.text_extents(s).x_advance
    yy += 62
# Palette swatches
keys = ["red", "yellow", "orange", "green", "cyan", "blue", "magenta", "brown"]
for i, k in enumerate(keys):
    for j, kk in enumerate((k, "b" + k)):
        col = hexrgb(C.get(kk, C[k]))
        rgba(ctx, col, 1)
        ctx.rectangle(x + 60 + i * 168, y + h - 190 + j * 74, 150, 60)
        ctx.fill()

out = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1800, 1012)
oc = cairo.Context(out)
oc.scale(1800 / W, 1012 / H)
oc.set_source_surface(surf, 0, 0)
oc.get_source().set_filter(cairo.FILTER_BEST)
oc.paint()
out.write_to_png(OUT)
