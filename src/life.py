"""03 — Life. Conway's B3/S23: a Gosper glider gun feeding an eater, beside a
specimen catalogue of oscillators and still lifes.

Every pattern has a period that divides 30, and the eater removes each glider,
so the universe repeats exactly every 30 generations. At 2 generations per
second the loop is 15 s long and has no seam.
"""

import math

import cairo
import numpy as np

from common import *
from life_sim import EATER, GUN, orients, rle, step

NAME = "3-life"
INTRO = 7.0
LOOP = 15.0
GPS = 2.0  # generations per second in the loop
PERIOD = 30
G0 = 330  # first steady-state generation; a multiple of the period
LX = 260

P = 22
COLS, ROWS = W // P, 98
OX, OY = (W - COLS * P) // 2, (H - ROWS * P) // 2
FIELD_C0 = 52  # no grid behind the text column

GUN_AT = (56, 10) if WIDE else (54, 10)
K = 8 if WIDE else -2
EATER_AT = (GUN_AT[0] + 81 + K, GUN_AT[1] + 68 + K)
EATER_PAT = orients(EATER)[3]

SPECIMENS = [
    # name, label, pattern, (col, row)
    ("PULSAR", "P3", rle("2b3o3b3o2b2$o4bobo4bo$o4bobo4bo$o4bobo4bo$2b3o3b3o2b2$2b3o3b3o2b$o4bobo4bo$o4bobo4bo$o4bobo4bo2$2b3o3b3o!"), (108, 11) if WIDE else (97, 11)),
    ("PENTADECATHLON", "P15", rle("2bo4bo2b$2ob4ob2o$2bo4bo2b!"), (131, 16) if WIDE else (116, 17)),
    ("BEACON", "P2", rle("2o2b$2o2b$2b2o$2b2o!"), (156, 13) if WIDE else (134, 12)),
    ("TOAD", "P2", rle("b3o$3o!"), (157, 27) if WIDE else (133, 27)),
    ("BLINKER", "P2", rle("3o!"), (137, 30) if WIDE else (120, 32)),
    ("BLOCK", "STILL", rle("2o$2o!"), (63, 64)),
    ("BEEHIVE", "STILL", rle("b2o$o2bo$b2o!"), (74, 63)),
    ("LOAF", "STILL", rle("b2o$o2bo$bobo$2bo!"), (86, 63)),
    ("BOAT", "STILL", rle("2o$obo$bo!"), (98, 63)),
]

GLIDER_PHASES = [rle("bo$2bo$3o!")]
for _ in range(3):
    g = np.zeros((7, 7), np.uint8)
    g[2:5, 2:5] = GLIDER_PHASES[-1][:3, :3]
    g = step(g)
    ys, xs = np.nonzero(g)
    GLIDER_PHASES.append(g[ys.min():ys.max() + 1, xs.min():xs.max() + 1])


def place(grid, pat, c, r):
    grid[r : r + pat.shape[0], c : c + pat.shape[1]] |= pat


def simulate():
    pad = 12
    gun = np.zeros((ROWS + 2 * pad, COLS + 2 * pad), np.uint8)
    place(gun, GUN, GUN_AT[0] + pad, GUN_AT[1] + pad)
    place(gun, EATER_PAT, EATER_AT[0] + pad, EATER_AT[1] + pad)
    spec = np.zeros_like(gun)
    for _, _, pat, (c, r) in SPECIMENS:
        place(spec, pat, c + pad, r + pad)
    gun_states = []
    for _ in range(G0 + PERIOD + 1):
        gun_states.append(gun[pad:-pad, pad:-pad].copy())
        gun = step(gun)
    spec_states = []
    for _ in range(PERIOD + 1):
        spec_states.append(spec[pad:-pad, pad:-pad].copy())
        spec = step(spec)
    assert np.array_equal(gun_states[G0], gun_states[G0 + PERIOD]), "gun universe not periodic"
    assert np.array_equal(spec_states[0], spec_states[PERIOD]), "specimens not periodic"
    return np.array(gun_states), np.array(spec_states[:PERIOD])


GUN_STATES, SPEC_STATES = simulate()


def gun_state(g):
    """Gun universe at integer generation g; periodic after G0."""
    if g < 0:
        return np.zeros((ROWS, COLS), np.uint8)
    if g <= G0:
        return GUN_STATES[g]
    return GUN_STATES[G0 + (g - G0) % PERIOD]


def spec_state(g):
    return SPEC_STATES[g % PERIOD]


EATER_BOX = (EATER_AT[0] - 2, EATER_AT[1] - 2, EATER_AT[0] + 6, EATER_AT[1] + 6)


def cell_xy(c, r):
    return OX + c * P, OY + r * P


# ---------------------------------------------------------------- layers ---

_grid = None


def grid_layer():
    global _grid
    if _grid:
        return _grid
    surf, ctx = layer()
    for r in range(ROWS):
        for c in range(FIELD_C0, COLS):
            x, y = cell_xy(c, r)
            cx, cy = x + P / 2, y + P / 2
            if c % 10 == 0 and r % 10 == 0:
                rgba(ctx, MUTED, 0.9)
                ctx.set_line_width(1.5)
                crosshair(ctx, cx, cy, 7, 0)
            else:
                rgba(ctx, LINE, 0.75)
                ctx.rectangle(cx - 1, cy - 1, 2, 2)
                ctx.fill()
    _grid = surf
    return surf


def rounded(ctx, x, y, s, rad):
    ctx.new_sub_path()
    ctx.arc(x + s - rad, y + rad, rad, -math.pi / 2, 0)
    ctx.arc(x + s - rad, y + s - rad, rad, 0, math.pi / 2)
    ctx.arc(x + rad, y + s - rad, rad, math.pi / 2, math.pi)
    ctx.arc(x + rad, y + rad, rad, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def draw_cells(ctx, state_fn, g, reveal=None):
    """Cells at fractional generation g with birth/death easing and afterglow."""
    g0 = math.floor(g)
    f = smooth((g - g0) / 0.55)
    s0, s1 = state_fn(g0), state_fn(g0 + 1)
    hist = [state_fn(g0 - k) for k in (1, 2, 3)]
    glow = np.zeros(s0.shape, np.float32)
    for k, h in enumerate(hist):
        glow = np.maximum(glow, h * (0.17, 0.10, 0.05)[k])
    glow *= (1 - s0)
    # Dying cells hand over to their afterglow; born cells grow in.
    alive = s0 * (1 - f) + s1 * f
    dying = (s0 == 1) & (s1 == 0)
    glow = np.where(dying, 0.17 * f, glow * (1 - 0.35 * f))
    ys, xs = np.nonzero((alive > 0.01) | (glow > 0.01))
    ex0, ey0, ex1, ey1 = EATER_BOX
    for r, c in zip(ys.tolist(), xs.tolist()):
        a = float(alive[r, c])
        rv = 1.0 if reveal is None else reveal(c, r)
        if rv <= 0:
            continue
        x, y = cell_xy(c, r)
        red = ex0 <= c <= ex1 and ey0 <= r <= ey1
        gl = float(glow[r, c])
        if gl > 0.01:
            rgba(ctx, RED if red else DIM, gl * rv * 1.4)
            rounded(ctx, x + 3, y + 3, P - 6, 3)
            ctx.fill()
        if a > 0.01:
            s = (P - 6) * (0.55 + 0.45 * a) * (0.6 + 0.4 * rv)
            o = (P - s) / 2
            rgba(ctx, RED if red else INK, (0.88 * a) * rv)
            rounded(ctx, x + o, y + o, s, 3)
            ctx.fill()


def box(ctx, c0, r0, c1, r1, label, sub, p):
    """Specimen frame: corner brackets and a two-part label."""
    if p <= 0:
        return
    x0, y0 = cell_xy(c0, r0)
    x1, y1 = cell_xy(c1, r1)
    ctx.set_line_width(1.6)
    rgba(ctx, DIM, 0.65)
    corner_brackets(ctx, x0, y0, x1, y1, 16, p)
    w = text(ctx, x0, y1 + 30, label, 17, DIM, 1, 0.14, chars=p * 1.5 * len(label))
    text(ctx, x0 + w + 16, y1 + 30, sub, 17, MUTED, 1, 0.14, chars=max(0, p * 1.5 - 0.5) * len(sub))


def spec_bounds(pat, c, r):
    """Bounding box over one full period, so frames never clip a phase."""
    sub = SPEC_STATES[:, max(0, r - 4) : r + pat.shape[0] + 4, max(0, c - 4) : c + pat.shape[1] + 4]
    any_ = sub.max(axis=0)
    ys, xs = np.nonzero(any_)
    return (max(0, c - 4) + xs.min() - 1, max(0, r - 4) + ys.min() - 1,
            max(0, c - 4) + xs.max() + 2, max(0, r - 4) + ys.max() + 2)


BOUNDS = [spec_bounds(pat, c, r) for _, _, pat, (c, r) in SPECIMENS]


DATA = [
    ("RULE", "B3 / S23"),
    ("PERIOD", "30 GEN"),
    ("EMISSION", "1 GLIDER / 30"),
    ("SPEED", "c / 4"),
    ("SPECIMENS", f"{len(SPECIMENS) + 1:02d}"),
]


def scene(ctx, s):
    ctx.set_line_width(2)
    rgba(ctx, DIM, 0.7)
    corner_brackets(ctx, 110, 150, W - 110, H - 110, 70, s["frame"])

    # Grid
    if s["grid"] > 0:
        gx, gy = cell_xy(GUN_AT[0] + 18, GUN_AT[1] + 4)
        rad = (W * 1.3) * ease_out(s["grid"], 2)
        g = cairo.RadialGradient(gx, gy, max(1, rad - 500), gx, gy, rad + 1)
        g.add_color_stop_rgba(0, 0, 0, 0, 1)
        g.add_color_stop_rgba(1, 0, 0, 0, 0)
        ctx.set_source_surface(grid_layer(), 0, 0)
        ctx.mask(g)

    # Lane annotation along the glider stream
    if s["lane"] > 0:
        a = smooth(s["lane"])
        x0, y0 = cell_xy(GUN_AT[0] + 30, GUN_AT[1] + 15)
        x1, y1 = cell_xy(EATER_AT[0] - 2, EATER_AT[1] - 2)
        dx, dy = (x1 - x0), (y1 - y0)
        n = math.hypot(dx, dy)
        px, py = -dy / n * 70, dx / n * 70
        ctx.set_line_width(1.3)
        ctx.set_dash([8, 10])
        rgba(ctx, MUTED, 0.8 * a)
        partial_line(ctx, x0 + px, y0 + py, x1 + px, y1 + py, ease_out(s["lane"]))
        ctx.set_dash([])
        mx, my = x0 + dx * 0.5 + px * 1.6, y0 + dy * 0.5 + py * 1.6
        ctx.save()
        ctx.translate(mx, my)
        ctx.rotate(math.atan2(dy, dx))
        text(ctx, 0, 0, "GLIDER STREAM  ·  c/4  →", 17, DIM, a, 0.14, "center")
        ctx.restore()

    # Gun universe
    reveal_gun = None
    if s["gun_reveal"] < 1:
        rv = s["gun_reveal"]

        def reveal_gun(c, r):
            h = ((c * 73856093) ^ (r * 19349663)) % 1000 / 1000
            return smooth(seg(rv, h * 0.6, h * 0.6 + 0.4))

    draw_cells(ctx, gun_state, s["g"], reveal_gun)

    # Specimens
    for i, ((name, sub, pat, (c, r)), bnd) in enumerate(zip(SPECIMENS, BOUNDS)):
        p = s["spec"][i]
        box(ctx, *bnd, name, sub, p)
    rs = s["spec"]

    def reveal_spec(c, r):
        for i, (c0, r0, c1, r1) in enumerate(BOUNDS):
            if c0 <= c <= c1 and r0 <= r <= r1:
                return smooth(seg(rs[i], 0.2, 1.0))
        return 0.0

    draw_cells(ctx, spec_state, s["gs"], reveal_spec)

    # Glider phase plate (static)
    gp = s["glider"]
    if gp > 0:
        c0, r0 = 63, 76
        for k, pat in enumerate(GLIDER_PHASES):
            for (r, c) in zip(*np.nonzero(pat)):
                x, y = cell_xy(c0 + k * 9 + c, r0 + r)
                a = smooth(seg(gp, k * 0.15, k * 0.15 + 0.5))
                rgba(ctx, INK, 0.8 * a)
                rounded(ctx, x + 3, y + 3, P - 6, 3)
                ctx.fill()
            x, y = cell_xy(c0 + k * 9, r0 + 4)
            text(ctx, x, y + 26, f"T+{k}", 16, MUTED, smooth(seg(gp, k * 0.15, k * 0.15 + 0.5)), 0.1)
        box(ctx, c0 - 2, r0 - 2, c0 + 30, r0 + 6, "GLIDER", "4 PHASES  ·  c/4", gp)

    # Moore neighbourhood diagram (static)
    nb = s["glider"]
    if nb > 0:
        c0, r0 = (149, 44) if WIDE else (123, 42)
        box(ctx, c0 - 1, r0 - 1, c0 + 10, r0 + 10, "MOORE", "r = 1  ·  8 NEIGHBOURS", nb)
        k = 0
        for j in range(3):
            for i in range(3):
                x, y = cell_xy(c0 + i * 3, r0 + j * 3)
                a = smooth(seg(nb, k * 0.06, k * 0.06 + 0.5))
                ctx.set_line_width(1.6)
                if i == 1 and j == 1:
                    rgba(ctx, RED, 0.9 * a)
                    ctx.rectangle(x + 4, y + 4, 3 * P - 8, 3 * P - 8)
                    ctx.stroke()
                    text(ctx, x + 1.5 * P, y + 1.5 * P + 8, "c", 22, RED, a, 0, "center")
                else:
                    k += 1
                    rgba(ctx, DIM, 0.6 * a)
                    ctx.rectangle(x + 4, y + 4, 3 * P - 8, 3 * P - 8)
                    ctx.stroke()
                    text(ctx, x + 1.5 * P, y + 1.5 * P + 8, str(k), 20, DIM, a, 0, "center")

    # Gun and eater labels
    lx, ly = cell_xy(GUN_AT[0], GUN_AT[1] - 2)
    text(ctx, lx, ly, "GOSPER GLIDER GUN", 19, DIM, 1, 0.14, chars=s["labels"] * 17)
    text(ctx, lx + 400, ly, "P30", 19, MUTED, 1, 0.14, chars=max(0, s["labels"] * 2 - 1) * 3)
    ex, ey = cell_xy(EATER_AT[0] + 7, EATER_AT[1] + 2) if WIDE else cell_xy(EATER_AT[0] - 1, EATER_AT[1] + 7)
    rgba(ctx, RED, smooth(s["labels"]))
    ctx.rectangle(ex, ey - 12, 10, 10)
    ctx.fill()
    text(ctx, ex + 22, ey, "EATER 1", 19, DIM, 1, 0.14, chars=s["labels"] * 7)

    # Left column
    text(ctx, LX - 6, 560, "LIFE", 124, INK, 1, 0.04, chars=s["title"] * 4)
    text(ctx, LX, 628, "CONWAY'S GAME OF LIFE", 25, DIM, 1, 0.14, chars=s["sub"] * 21)
    ctx.set_line_width(1.5)
    rgba(ctx, LINE, 1)
    partial_line(ctx, LX, 740, LX + 820, 740, ease_out(s["data"]))
    rows = DATA + [("POPULATION", f"{s['pop']:03d}")]
    for i, (k, v) in enumerate(rows):
        p = seg(s["data"], i * 0.08, i * 0.08 + 0.5)
        y = 820 + i * 56
        text(ctx, LX, y, k, 24, MUTED, 1, 0.16, chars=p * len(k))
        text(ctx, LX + 300, y, v, 24, INK, 1, 0.16, chars=p * len(v))
    partial_line(ctx, LX, 1190, LX + 820, 1190, ease_out(s["data"]))
    ph = s["phase"]
    line = f"PHASE {ph:02d} / 30"
    text(ctx, LX, 1270, line, 40, INK, 1, 0.12, chars=s["gen"] * len(line))
    if s["gen"] > 0:
        for k in range(30):
            on = k == ph
            rgba(ctx, INK if on else (DIM if k < ph else LINE), (1 if on else 0.6) * smooth(s["gen"]))
            ctx.rectangle(LX + k * 27.5, 1330, 14, 28 if k % 5 == 0 else 18)
            ctx.fill()


def population(g_gun, g_spec):
    return int(gun_state(math.floor(g_gun)).sum() + spec_state(math.floor(g_spec)).sum())


def full(g, gs):
    return dict(frame=1, grid=1, lane=1, g=g, gun_reveal=1, gs=gs, spec=[1] * len(SPECIMENS),
                glider=1, labels=1, label=1, title=1, sub=1, data=1, gen=1,
                pop=population(g, gs), phase=math.floor(gs) % PERIOD)


def still():
    surf, ctx = new_frame()
    scene(ctx, full(G0, 0))
    return surf


def intro(t):
    surf, ctx = new_frame()
    u = seg(t, 1.3, INTRO)
    g = G0 * smooth(u) ** 1.15 if u < 1 else G0
    gs = GPS * (t - INTRO)
    n = len(SPECIMENS)
    s = dict(
        frame=seg(t, 0.0, 0.9),
        grid=seg(t, 0.2, 2.2),
        lane=seg(t, 3.0, 4.2),
        g=g,
        gun_reveal=seg(t, 0.6, 1.5),
        gs=gs,
        spec=[seg(t, 1.6 + i * 0.16, 2.4 + i * 0.16) for i in range(n)],
        glider=seg(t, 3.2, 4.4),
        labels=seg(t, 1.2, 2.0),
        label=seg(t, 0.3, 0.9),
        title=seg(t, 0.55, 1.1),
        sub=seg(t, 1.0, 1.9),
        data=seg(t, 1.6, 3.2),
        gen=seg(t, 2.8, 3.2),
        pop=population(g, gs),
        phase=math.floor(gs) % PERIOD,
    )
    scene(ctx, s)
    return surf


def loop(t):
    surf, ctx = new_frame()
    g = GPS * t
    scene(ctx, full(G0 + g, g))
    return surf


if __name__ == "__main__":
    main(NAME, still, intro, INTRO, loop, LOOP)
