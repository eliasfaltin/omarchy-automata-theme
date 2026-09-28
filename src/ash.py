"""06 — Ash. What a random Game of Life soup leaves behind.

A soup with uneven density (clusters and empty plains) runs under B3/S23 on
a board with an absorbing margin, so escaping gliders vanish. After a few
thousand generations only ash is left: blocks, beehives, boats, blinkers and
the odd pulsar. The whole universe then repeats with period 2, 3 or 6, so a
6-generation loop is exact. Oscillating cells are drawn brighter than the
static debris.

The intro is the real evolution from the soup, fast at first and slowing into
the ash. Skipped generations are averaged, so the chaos reads as grain.
"""

import math
from collections import deque

import cairo
import numpy as np

from common import *
from life_sim import step

NAME = "6-ash"
P = 18
COLS, ROWS = W // P, H // P
PAD = 60
INTRO = 8.0
LOOP_GENS = 6
GPS = 0.75
LOOP = LOOP_GENS / GPS


def soup(seed):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:ROWS, 0:COLS]
    f = np.zeros((ROWS, COLS))
    for _ in range(6):
        a = rng.uniform(0, math.tau)
        fr = rng.uniform(0.01, 0.035)
        f += np.sin((xx * math.cos(a) + yy * math.sin(a)) * fr + rng.uniform(0, math.tau))
    f = (f - f.min()) / (f.max() - f.min())
    density = np.clip((f - 0.3) * 1.0, 0, 0.5)
    u = np.zeros((ROWS + 2 * PAD, COLS + 2 * PAD), np.uint8)
    u[PAD:PAD + ROWS, PAD:PAD + COLS] = rng.random((ROWS, COLS)) < density
    return u


def settle(seed):
    """Evolve until the whole board repeats; return visible states and G0."""
    u = soup(seed)
    states = [u[PAD:PAD + ROWS, PAD:PAD + COLS].copy()]
    recent = deque([u.copy()], maxlen=4 * LOOP_GENS + 1)
    for g in range(1, 20000):
        u = step(u)
        u[:2, :] = 0
        u[-2:, :] = 0
        u[:, :2] = 0
        u[:, -2:] = 0
        states.append(u[PAD:PAD + ROWS, PAD:PAD + COLS].copy())
        recent.append(u.copy())
        if g > 300 and len(recent) == recent.maxlen and all(
            np.array_equal(recent[-1 - k * LOOP_GENS], recent[-1]) for k in (1, 2, 3, 4)
        ):
            # Static ash (period 1) would make a dead loop; require motion.
            if not np.array_equal(recent[-1], recent[-2]):
                # u(g) == u(g - 6), so every state from g - 6 on repeats.
                # Start the loop at g and keep one more cycle of states, so
                # the loop and its two afterglow states all lie in the cycle.
                for _ in range(LOOP_GENS + 2):
                    u = step(u)
                    states.append(u[PAD:PAD + ROWS, PAD:PAD + COLS].copy())
                return states, g
            return None
    return None


for _seed in range(1, 60):
    _result = settle(_seed)
    if _result:
        STATES, G0 = _result
        break
else:
    raise SystemExit("no seed settled into moving ash")

STACK = np.array(STATES[G0:G0 + LOOP_GENS])
# Cells that ever change during the loop are oscillators; the rest is debris.
ACTIVE = (STACK.max(axis=0) != STACK.min(axis=0)).astype(np.float32)


def state(g):
    if g > G0 + LOOP_GENS:
        g = G0 + (g - G0) % LOOP_GENS
    return STATES[max(0, g)].astype(np.float32)


_cache = {}


def paper():
    """Paper, grain, cell stamp mask and faint grid dots, built once."""
    if not _cache:
        surf = base_surface()
        stride = surf.get_stride()
        base = np.ndarray((H, stride // 4, 4), np.uint8, surf.get_data())[:, :W, :3].astype(np.float32)
        stamp = np.zeros((P, P), np.float32)
        yy, xx = np.mgrid[0:P, 0:P] + 0.5
        inset, rad = 3.0, 3.5
        dx = np.maximum(np.abs(xx - P / 2) - (P / 2 - inset - rad), 0)
        dy = np.maximum(np.abs(yy - P / 2) - (P / 2 - inset - rad), 0)
        stamp = np.clip(rad + 0.5 - np.hypot(dx, dy), 0, 1)
        dot = np.zeros((P, P), np.float32)
        dot[P // 2 - 1:P // 2 + 1, P // 2 - 1:P // 2 + 1] = 1
        pad = ((0, H - ROWS * P), (0, W - COLS * P))
        _cache["base"] = base
        _cache["stamp"] = np.pad(np.tile(stamp, (ROWS, COLS)), pad)
        _cache["dot"] = np.pad(np.tile(dot, (ROWS, COLS)), pad)
    return _cache["base"], _cache["stamp"], _cache["dot"]


def up(field):
    a = np.repeat(np.repeat(field, P, 0), P, 1)
    return np.pad(a, ((0, H - a.shape[0]), (0, W - a.shape[1])))


INK_BGR = np.array(INK[::-1], np.float32) * 255
DIM_BGR = np.array(DIM[::-1], np.float32) * 255
LINE_BGR = np.array(LINE[::-1], np.float32) * 255


def compose(v, glow, fade=1.0, grid=1.0):
    """v: live value per cell; glow: afterglow per cell (both 0..1)."""
    base, stamp, dot = paper()
    act = up(ACTIVE)[..., None]
    colour = DIM_BGR * (1 - act) + INK_BGR * act
    strength = 0.58 + 0.32 * act  # oscillators read brighter than debris
    a_cell = (up(v)[..., None] * strength + up(glow)[..., None] * 0.18) * stamp[..., None] * fade
    a_dot = dot[..., None] * 0.45 * grid
    rgb = base * (1 - a_dot) + LINE_BGR * a_dot
    rgb = rgb * (1 - a_cell) + colour * a_cell
    out = np.empty((H, W, 4), np.uint8)
    out[..., :3] = np.clip(rgb + 0.5, 0, 255)
    out[..., 3] = 255
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    data = np.ndarray((H, surf.get_stride() // 4, 4), np.uint8, surf.get_data())
    data[:, :W] = out
    surf.mark_dirty()
    return surf


def at(g):
    """Live value and afterglow at fractional generation g.

    Each birth or death fades across the whole generation, so blinkers breathe
    instead of flicker.
    """
    g0 = math.floor(g)
    f = smooth(g - g0)
    s0, s1 = state(g0), state(g0 + 1)
    v = s0 * (1 - f) + s1 * f
    glow = np.maximum(state(g0 - 1), state(g0 - 2) * 0.5) * (1 - s0)
    glow = glow * (1 - f) + np.maximum(s0, state(g0 - 1) * 0.5) * (1 - s1) * f
    return v, glow


def still():
    return compose(*at(G0))


def warp(t):
    """Generation shown at intro time t: fast through the soup, slowing to rest."""
    u = seg(t, 0.5, INTRO)
    return G0 * (1 - (1 - u) ** 3)


def intro(t):
    fade = smooth(seg(t, 0.0, 1.0))
    g = warp(t)
    lo = math.floor(warp(max(0.0, t - 1 / 60)))
    hi = math.floor(g)
    if t >= INTRO:
        v, glow = at(G0)
    elif hi - lo >= 2:
        # Motion blur over the generations this frame skipped.
        v = np.mean([state(k) for k in range(lo + 1, hi + 1)], axis=0)
        glow = np.zeros_like(v)
    else:
        v, glow = at(g)
    return compose(v, glow, fade, fade)


def loop(t):
    return compose(*at(G0 + GPS * t))


if __name__ == "__main__":
    main(NAME, still, intro, INTRO, loop, LOOP, loop_fps=60)
