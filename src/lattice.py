"""06 — Lattice. A text-free field of Game of Life oscillators.

Pulsars (period 3) sit on a square lattice; pentadecathlons (period 15) fill
the diagonal gaps, alternating horizontal and vertical. Every period divides
15, so the universe repeats exactly every 15 generations.
"""

import math

import cairo
import numpy as np

from common import *
from life_sim import rle, step

NAME = "6-lattice"
P = 12
COLS, ROWS = W // P + 2, H // P + 2
OX, OY = (W - COLS * P) / 2, (H - ROWS * P) / 2
SPACING = 26
PERIOD = 15
GPS = 1.5
INTRO = 6.0
LOOP = PERIOD / GPS

PULSAR = rle("2b3o3b3o2b2$o4bobo4bo$o4bobo4bo$o4bobo4bo$2b3o3b3o2b2$2b3o3b3o2b$o4bobo4bo$o4bobo4bo$o4bobo4bo2$2b3o3b3o!")
PENTA = rle("2bo4bo2b$2ob4ob2o$2bo4bo2b!")


def build():
    g = np.zeros((ROWS, COLS), np.uint8)

    def put(pat, c, r):
        h, w = pat.shape
        if r < 0 or c < 0 or r + h > ROWS or c + w > COLS:
            return
        g[r : r + h, c : c + w] |= pat

    ph, pw = PULSAR.shape
    for j in range(-1, ROWS // SPACING + 2):
        for i in range(-1, COLS // SPACING + 2):
            put(PULSAR, i * SPACING + 2, j * SPACING + 2)
            pent = PENTA if (i + j) % 2 else PENTA.T
            cy = j * SPACING + 2 + ph // 2 + SPACING // 2
            cx = i * SPACING + 2 + pw // 2 + SPACING // 2
            put(pent, cx - pent.shape[1] // 2, cy - pent.shape[0] // 2)
    return g


def simulate():
    pad = 20
    u = np.pad(build(), pad)
    states = []
    for _ in range(PERIOD + 1):
        states.append(u[pad:-pad, pad:-pad].copy())
        u = step(u)
    assert np.array_equal(states[0], states[PERIOD]), "lattice is not periodic"
    return np.array(states[:PERIOD])


STATES = simulate()


def state(g):
    return STATES[g % PERIOD]


def rounded(ctx, x, y, s, rad):
    ctx.new_sub_path()
    ctx.arc(x + s - rad, y + rad, rad, -math.pi / 2, 0)
    ctx.arc(x + s - rad, y + s - rad, rad, 0, math.pi / 2)
    ctx.arc(x + rad, y + s - rad, rad, math.pi / 2, math.pi)
    ctx.arc(x + rad, y + rad, rad, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def draw(ctx, g, reveal=None):
    """Cells at fractional generation g: eased births and deaths, afterglow."""
    g0 = math.floor(g)
    f = smooth((g - g0) / 0.55)
    s0, s1 = state(g0), state(g0 + 1)
    glow = np.zeros(s0.shape, np.float32)
    for k, a in ((1, 0.16), (2, 0.09), (3, 0.05)):
        glow = np.maximum(glow, state(g0 - k) * a)
    glow *= 1 - s0
    alive = s0 * (1 - f) + s1 * f
    dying = (s0 == 1) & (s1 == 0)
    glow = np.where(dying, 0.16 * f, glow * (1 - 0.35 * f))
    ys, xs = np.nonzero((alive > 0.01) | (glow > 0.01))
    for r, c in zip(ys.tolist(), xs.tolist()):
        x, y = OX + c * P, OY + r * P
        rv = 1.0 if reveal is None else reveal(x, y)
        if rv <= 0:
            continue
        gl = float(glow[r, c])
        if gl > 0.01:
            rgba(ctx, DIM, gl * 1.3 * rv)
            rounded(ctx, x + 2, y + 2, P - 4, 2)
            ctx.fill()
        a = float(alive[r, c])
        if a > 0.01:
            s = (P - 4) * (0.55 + 0.45 * a)
            o = (P - s) / 2
            rgba(ctx, INK, 0.62 * a * rv)
            rounded(ctx, x + o, y + o, s, 2)
            ctx.fill()


_dots = None


def dots():
    global _dots
    if _dots is None:
        _dots, ctx = layer()
        rgba(ctx, LINE, 0.55)
        for r in range(ROWS):
            for c in range(COLS):
                ctx.rectangle(OX + c * P + P / 2 - 1, OY + r * P + P / 2 - 1, 2, 2)
        ctx.fill()
    return _dots


def still():
    surf, ctx = new_frame()
    ctx.set_source_surface(dots(), 0, 0)
    ctx.paint()
    draw(ctx, 0)
    return surf


def intro(t):
    surf, ctx = new_frame()
    cx, cy = W / 2, H / 2
    far = math.hypot(W / 2, H / 2)
    ctx.set_source_surface(dots(), 0, 0)
    ctx.paint_with_alpha(smooth(seg(t, 0.0, 1.2)))

    def reveal(x, y):
        d = math.hypot(x - cx, y - cy) / far
        return smooth(seg(t, 0.5 + d * 3.0, 1.3 + d * 3.0))

    # Oscillators run at loop speed and land on generation 0 at the end.
    draw(ctx, GPS * (t - INTRO) + PERIOD * 10, reveal)
    return surf


def loop(t):
    surf, ctx = new_frame()
    ctx.set_source_surface(dots(), 0, 0)
    ctx.paint()
    draw(ctx, GPS * t)
    return surf


if __name__ == "__main__":
    main(NAME, still, intro, INTRO, loop, LOOP)
