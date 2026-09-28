"""06 — Colony. A busy Game of Life universe that never stops moving.

Glider guns in all eight orientations, each with its own stream length, fire
across the board into eaters. Oscillators and still lifes fill the gaps. The
layout is random but checked: every part's footprint over a full period is
kept clear of every other part's, and the whole board is simulated until it
repeats. Every part has a period dividing 30, so a 30-generation loop is
exact. Moving cells are drawn brighter than the static ones.

The intro starts the guns cold and runs fast until every stream reaches its
eater, then slows into the loop.
"""

import math

import cairo
import numpy as np

from common import *
from life_sim import EATER, GUN, orients, rle, step

NAME = "6-colony"
P = 12
COLS, ROWS = W // P, H // P
MARGIN = 40  # simulated but off screen, so streams can enter from the edges
SW, SH = COLS + 2 * MARGIN, ROWS + 2 * MARGIN
PERIOD = 30
GPS = 2.5
INTRO = 8.0
LOOP = PERIOD / GPS
EATER_SE = orients(EATER)[3]

SMALL = {
    "pulsar": rle("2b3o3b3o2b2$o4bobo4bo$o4bobo4bo$o4bobo4bo$2b3o3b3o2b2$2b3o3b3o2b$o4bobo4bo$o4bobo4bo$o4bobo4bo2$2b3o3b3o!"),
    "penta": rle("2bo4bo2b$2ob4ob2o$2bo4bo2b!"),
    "blinker": rle("3o!"),
    "toad": rle("b3o$3o!"),
    "beacon": rle("2o2b$2o2b$2b2o$2b2o!"),
    "block": rle("2o$2o!"),
    "beehive": rle("b2o$o2bo$b2o!"),
    "loaf": rle("b2o$o2bo$bobo$2bo!"),
    "boat": rle("2o$obo$bo!"),
}
SMALL_WEIGHTS = {"pulsar": 1, "penta": 1, "blinker": 3, "toad": 2, "beacon": 2,
                 "block": 5, "beehive": 5, "loaf": 3, "boat": 4}


def gun_assembly(d):
    """Gosper gun firing south-east into an eater d cells further down the lane."""
    a = np.zeros((32 + d + 4, 45 + d + 4), np.uint8)
    a[0:9, 0:36] |= GUN
    a[32 + d:36 + d, 45 + d:49 + d] |= EATER_SE
    return a


def footprint(pat, gens):
    """Cells a pattern touches over one period once running, grown by 2."""
    pad = 6
    u = np.pad(pat, pad)
    for _ in range(gens):
        u = step(u)
    seen = np.zeros_like(u)
    for _ in range(PERIOD):
        u = step(u)
        seen |= u
    grown = seen.copy()
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            grown |= np.roll(np.roll(seen, dy, 0), dx, 1)
    return grown, pad


def transform(a, k):
    r = np.rot90(a, k % 4)
    return np.fliplr(r) if k >= 4 else r


def layout(seed):
    rng = np.random.default_rng(seed)
    board = np.zeros((SH, SW), np.uint8)
    taken = np.zeros((SH, SW), np.uint8)

    def try_place(pat, fp, pad, tries, lo=(0, 0), hi=None):
        h, w = fp.shape
        hi = hi or (SH - h, SW - w)
        for _ in range(tries):
            r = int(rng.integers(lo[0], max(lo[0] + 1, hi[0])))
            c = int(rng.integers(lo[1], max(lo[1] + 1, hi[1])))
            if r + h > SH or c + w > SW:
                continue
            if (taken[r:r + h, c:c + w] & fp).any():
                continue
            taken[r:r + h, c:c + w] |= fp
            ph, pw = pat.shape
            board[r + pad:r + pad + ph, c + pad:c + pad + pw] |= pat
            return True
        return False

    guns = 0
    for _ in range(40):
        if guns >= 10:
            break
        d = int(rng.integers(0, 30)) * 2
        k = int(rng.integers(0, 8))
        pat = transform(gun_assembly(d), k)
        fp, pad = footprint(pat, 4 * (d + 60) + 120)
        h, w = fp.shape
        # Keep each assembly's centre on screen; its edges may run off.
        lo = (max(0, MARGIN - h // 2), max(0, MARGIN - w // 2))
        hi = (min(SH - h, MARGIN + ROWS - h // 2), min(SW - w, MARGIN + COLS - w // 2))
        guns += try_place(pat, fp, pad, 80, lo, hi)

    names = list(SMALL_WEIGHTS)
    weights = np.array([SMALL_WEIGHTS[n] for n in names], float)
    weights /= weights.sum()
    prints = {n: footprint(SMALL[n], 60) for n in names}
    # Cluster the small parts: a smooth random field decides where they may go.
    yy, xx = np.mgrid[0:SH, 0:SW]
    field = np.zeros((SH, SW))
    for _ in range(5):
        a = rng.uniform(0, math.tau)
        field += np.sin((xx * math.cos(a) + yy * math.sin(a)) * rng.uniform(0.02, 0.05) + rng.uniform(0, math.tau))
    field = (field - field.min()) / (field.max() - field.min())
    for _ in range(320):
        n = names[int(rng.choice(len(names), p=weights))]
        k = int(rng.integers(0, 8))
        pat = transform(SMALL[n], k)
        fp, pad = prints[n]
        fp = transform(fp, k)
        r, c = int(rng.integers(MARGIN - 6, SH - MARGIN)), int(rng.integers(MARGIN - 6, SW - MARGIN))
        if rng.random() > field[min(r, SH - 1), min(c, SW - 1)] ** 2:
            continue
        try_place(pat, fp, pad, 1, (r, c), (r + 1, c + 1))
    return board, guns


def simulate():
    for seed in range(1, 40):
        board, guns = layout(seed)
        if guns < 6:
            continue
        u = board.copy()
        states, snaps = [], {}
        for g in range(700):
            states.append(u[MARGIN:MARGIN + ROWS, MARGIN:MARGIN + COLS].copy())
            if g % PERIOD == 0:
                snaps[g] = u.copy()
            u = step(u)
            u[:2] = 0
            u[-2:] = 0
            u[:, :2] = 0
            u[:, -2:] = 0
        # u(g0) == u(g0 + 30) makes every later state repeat; start one
        # period later so the afterglow states are inside the cycle too.
        for g0 in range(PERIOD, 700 - 2 * PERIOD, PERIOD):
            if np.array_equal(snaps[g0], snaps[g0 + PERIOD]) and np.array_equal(snaps[g0], snaps[g0 + 2 * PERIOD]):
                return np.array(states), g0 + PERIOD, guns
    raise SystemExit("no colony layout settled")


STATES, G0, GUNS = simulate()
STACK = STATES[G0:G0 + PERIOD]
ACTIVE = (STACK.max(axis=0) != STACK.min(axis=0)).astype(np.float32)


def state(g):
    if g > G0 + PERIOD:
        g = G0 + (g - G0) % PERIOD
    return STATES[max(0, g)].astype(np.float32)


_cache = {}


def paper():
    if not _cache:
        surf = base_surface()
        stride = surf.get_stride()
        base = np.ndarray((H, stride // 4, 4), np.uint8, surf.get_data())[:, :W, :3].astype(np.float32)
        yy, xx = np.mgrid[0:P, 0:P] + 0.5
        inset, rad = 2.0, 2.5
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


def compose(v, glow, fade=1.0):
    base, stamp, dot = paper()
    act = up(ACTIVE)[..., None]
    colour = DIM_BGR * (1 - act) + INK_BGR * act
    strength = 0.5 + 0.35 * act
    a_cell = (up(v)[..., None] * strength + up(glow)[..., None] * 0.2) * stamp[..., None] * fade
    a_dot = dot[..., None] * 0.45 * fade
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
    """Live value and afterglow at fractional generation g; changes ease
    across the whole generation, and gliders leave a short trail."""
    g0 = math.floor(g)
    f = smooth(g - g0)
    s0, s1 = state(g0), state(g0 + 1)
    v = s0 * (1 - f) + s1 * f
    trail0 = np.maximum(state(g0 - 1), state(g0 - 2) * 0.5) * (1 - s0)
    trail1 = np.maximum(s0, state(g0 - 1) * 0.5) * (1 - s1)
    return v, trail0 * (1 - f) + trail1 * f


def still():
    return compose(*at(G0))


def warp(t):
    """Generation shown at intro time t: guns start cold, streams race to
    their eaters, then everything slows into the loop."""
    u = seg(t, 0.8, INTRO)
    return G0 * (1 - (1 - u) ** 2.2)


def intro(t):
    fade = smooth(seg(t, 0.0, 1.2))
    g = warp(t)
    lo = math.floor(warp(max(0.0, t - 1 / 60)))
    hi = math.floor(g)
    if t >= INTRO:
        v, glow = at(G0)
    elif hi - lo >= 2:
        v = np.mean([state(k) for k in range(lo + 1, hi + 1)], axis=0)
        glow = np.zeros_like(v)
    else:
        v, glow = at(g)
    return compose(v, glow, fade)


def loop(t):
    return compose(*at(G0 + GPS * t))


if __name__ == "__main__":
    main(NAME, still, intro, INTRO, loop, LOOP, loop_fps=60)
