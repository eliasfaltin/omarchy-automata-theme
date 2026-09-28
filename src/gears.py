"""05 — Gears. A text-free lattice of meshing gears.

Large (36 T, 6 spokes) and small (24 T, 4 spokes) gears alternate on a square
lattice, so every horizontal and vertical neighbour pair meshes and diagonal
neighbours clear each other. Over the 30 s loop the small gears turn 1/4 rev
and the large ones 1/6 rev: one spoke period each, so the loop has no seam.
"""

import math

import cairo

from common import *

NAME = "5-gears"
TAU = math.tau
NS, NB = 24, 36
RS = 118.0
RB = RS * NB / NS
MOD = 2 * RS / NS
SPACING = RS + RB
INTRO = 6.0
LOOP = 30.0
TURN_S = 0.25  # small-gear revolutions per loop


def gear_path(ctx, n, r, phase):
    ra, rd = r + MOD, r - 1.25 * MOD
    samples = 12
    for k in range(n):
        for j in range(samples):
            u = j / samples
            a = phase + (k + u - 0.5) * TAU / n
            d = abs(u - 0.5)
            w0, w1 = 0.27, 0.10
            if d < w1:
                h = 1.0
            elif d > w0:
                h = 0.0
            else:
                x = (d - w1) / (w0 - w1)
                h = math.sqrt(max(0.0, 1 - x * x))
            rr = rd + (ra - rd) * h
            p = (rr * math.cos(a), rr * math.sin(a))
            if k == 0 and j == 0:
                ctx.move_to(*p)
            else:
                ctx.line_to(*p)
    ctx.close_path()


def windows(ctx, spokes, r_in, r_hub, phase, half_w):
    """Cut-outs between straight spokes of constant width."""
    for k in range(spokes):
        t0 = phase + k * TAU / spokes
        t1 = t0 + TAU / spokes
        o0 = t0 + math.asin(half_w / r_in)
        o1 = t1 - math.asin(half_w / r_in)
        i0 = t1 - math.asin(half_w / r_hub)
        i1 = t0 + math.asin(half_w / r_hub)
        ctx.move_to(r_hub * math.cos(i1), r_hub * math.sin(i1))
        ctx.arc(0, 0, r_in, o0, o1)
        ctx.arc_negative(0, 0, r_hub, i0, i1)
        ctx.close_path()


def sprite(n, r, spokes, angle):
    """One gear, centred in its own surface, at the given angle."""
    size = int(2 * (r + MOD) + 8)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(surf)
    ctx.translate(size / 2, size / 2)
    ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    gear_path(ctx, n, r, angle)
    windows(ctx, spokes, r * 0.78, r * 0.26, angle, r * 0.055)
    rgba(ctx, SURFACE, 0.92)
    ctx.fill_preserve()
    ctx.set_line_width(2.0)
    rgba(ctx, INK, 0.30)
    ctx.stroke()
    ctx.set_line_width(1.2)
    rgba(ctx, INK, 0.12)
    for f in (0.84, 0.16):
        ctx.arc(0, 0, r * f, 0, TAU)
        ctx.stroke()
    rgba(ctx, BG_DEEP, 1)
    ctx.arc(0, 0, r * 0.07, 0, TAU)
    ctx.fill()
    ctx.set_line_width(1.5)
    rgba(ctx, INK, 0.35)
    ctx.arc(0, 0, r * 0.07 + 4, 0, TAU)
    ctx.stroke()
    return surf


def lattice():
    """Gear centres covering the frame, with a border so edges stay full."""
    cols = int(W / SPACING) + 3
    rows = int(H / SPACING) + 3
    ox = (W - (cols - 1) * SPACING) / 2
    oy = (H - (rows - 1) * SPACING) / 2
    out = []
    for j in range(rows):
        for i in range(cols):
            out.append((ox + i * SPACING, oy + j * SPACING, (i + j) % 2 == 0))
    return out


CENTRES = lattice()
# Phases that mesh every lattice pair: large gears have a tooth on each axis,
# small gears a gap there (36 and 24 are both divisible by 4).
PH_B, PH_S = 0.0, math.pi / NS


def scene(ctx, turn, reveal=None):
    """turn: small-gear revolutions. reveal(x, y) -> 0..1 per gear, or None."""
    a_s = PH_S + TAU * turn
    a_b = PH_B - TAU * turn * NS / NB
    big = sprite(NB, RB, 6, a_b)
    small = sprite(NS, RS, 4, a_s)
    for x, y, is_big in CENTRES:
        spr = big if is_big else small
        p = 1.0 if reveal is None else reveal(x, y)
        if p <= 0:
            continue
        half = spr.get_width() / 2
        ctx.save()
        ctx.translate(x, y)
        if p < 1:
            k = 0.9 + 0.1 * ease_out(p)
            ctx.scale(k, k)
        ctx.set_source_surface(spr, -half, -half)
        ctx.paint_with_alpha(smooth(p))
        ctx.restore()


def still():
    surf, ctx = new_frame()
    scene(ctx, 0.0)
    return surf


def intro(t):
    surf, ctx = new_frame()
    cx, cy = W / 2, H / 2
    far = math.hypot(W / 2, H / 2) + SPACING

    def reveal(x, y):
        d = math.hypot(x - cx, y - cy) / far
        return seg(t, 0.2 + d * 2.4, 1.2 + d * 2.4)

    # The whole train spins down into its rest angle.
    turn = -0.6 * (1 - ease_out(seg(t, 0.2, INTRO), 3))
    scene(ctx, turn, reveal)
    return surf


def loop(t):
    surf, ctx = new_frame()
    scene(ctx, TURN_S * t / LOOP)
    return surf


if __name__ == "__main__":
    main(NAME, still, intro, INTRO, loop, LOOP)
