"""01 — Rule 110. An elementary cellular automaton computed row by row."""

import cairo
import numpy as np

from common import *

NAME = "1-rule-110"
INTRO = 6.0
LOOP = 12.0

PITCH, CELL = 13, 9
FX0, FY0 = 1180, 320
COLS = (W - 200 - FX0) // PITCH
ROWS = (1960 - FY0) // PITCH
FX1, FY1 = FX0 + COLS * PITCH, FY0 + ROWS * PITCH
LX = 260  # left text column

RULE = 110
TABLE = [(n, (RULE >> n) & 1) for n in range(7, -1, -1)]


def evolve():
    pad = 160
    w = COLS + 2 * pad
    rng = np.random.default_rng(0x5F3A)
    row = (rng.random(w) < 0.5).astype(np.uint8)
    out = np.zeros((ROWS, COLS), np.uint8)
    for r in range(ROWS):
        out[r] = row[pad : pad + COLS]
        l, c, rr = np.roll(row, 1), row, np.roll(row, -1)
        row = ((RULE >> (l * 4 + c * 2 + rr)) & 1).astype(np.uint8)
    return out


GRID = evolve()

_layers = None


def layers():
    """Dots, cells and highlighted cells, drawn once per worker."""
    global _layers
    if _layers:
        return _layers
    dots, dc = layer()
    cells, cc = layer()
    hi, hc = layer()
    rgba(dc, LINE, 0.9)
    rgba(cc, INK, 0.52)
    rgba(hc, INK_HI, 1.0)
    off = (PITCH - CELL) / 2
    for r in range(ROWS):
        y = FY0 + r * PITCH
        for c in range(COLS):
            x = FX0 + c * PITCH
            if GRID[r, c]:
                cc.rectangle(x + off, y + off, CELL, CELL)
                hc.rectangle(x + off - 1, y + off - 1, CELL + 2, CELL + 2)
            else:
                dc.rectangle(x + PITCH / 2 - 1, y + PITCH / 2 - 1, 2, 2)
    dc.fill()
    cc.fill()
    hc.fill()
    _layers = (dots, cells, hi)
    return _layers


def paint_rows(ctx, surf, r0, r1, alpha=1.0):
    """Paint rows [r0, r1) of a field layer; r may be fractional."""
    if r1 <= r0:
        return
    ctx.save()
    ctx.rectangle(FX0 - 4, FY0 + r0 * PITCH, FX1 - FX0 + 8, (r1 - r0) * PITCH)
    ctx.clip()
    ctx.set_source_surface(surf, 0, 0)
    ctx.paint_with_alpha(alpha)
    ctx.restore()


def head(ctx, surf, y, alpha, trail=7):
    """Brighten whole rows at a read head on y, with an afterglow above it.

    A row lights up while the line crosses it and then fades over `trail`
    rows. Rows below the line stay dark, so the glow never runs ahead of or
    behind the line, and no cell is ever cut in half.
    """
    if alpha <= 0:
        return
    last = min(ROWS - 1, int((y - FY0) / PITCH))
    for r in range(max(0, last - trail - 1), last + 1):
        u = (y - (FY0 + r * PITCH)) / PITCH  # 0 at the row's top edge, 1 at its bottom
        w = smooth(u) * (1 - clamp((u - 1) / trail)) ** 2
        if w > 0.01:
            paint_rows(ctx, surf, r, r + 1, alpha * w)


def scanline(ctx, y, alpha, label):
    if alpha <= 0:
        return
    g = cairo.LinearGradient(0, y - 90, 0, y + 90)
    g.add_color_stop_rgba(0, *INK, 0)
    g.add_color_stop_rgba(0.5, *INK, 0.05 * alpha)
    g.add_color_stop_rgba(1, *INK, 0)
    ctx.rectangle(FX0, y - 90, FX1 - FX0, 180)
    ctx.set_source(g)
    ctx.fill()
    ctx.set_line_width(1.5)
    rgba(ctx, INK, 0.35 * alpha)
    ctx.move_to(FX0 - 30, y)
    ctx.line_to(FX1 + 30, y)
    ctx.stroke()
    rgba(ctx, RED, alpha)
    ctx.move_to(FX0 - 34, y)
    ctx.line_to(FX0 - 52, y - 9)
    ctx.line_to(FX0 - 52, y + 9)
    ctx.close_path()
    ctx.fill()
    text(ctx, FX1 + 44, y + 8, label, 20, DIM, alpha)


def rule_table(ctx, t_in):
    """Eight neighbourhoods and their outputs. t_in[i] is entry i's reveal."""
    s, g = 30, 6
    ew = 3 * s + 2 * g
    for i, (n, bit) in enumerate(TABLE):
        p = t_in[i]
        if p <= 0:
            continue
        col, row = i % 4, i // 4
        x = LX + col * (ew + 46)
        y = 820 + row * 150
        k = ease_out_back(p)
        a = clamp(p * 2)
        ctx.save()
        ctx.translate(x + ew / 2, y + s)
        ctx.scale(k, k)
        ctx.translate(-(x + ew / 2), -(y + s))
        for j in range(3):
            on = (n >> (2 - j)) & 1
            cx = x + j * (s + g)
            if on:
                rgba(ctx, INK, 0.85 * a)
                ctx.rectangle(cx, y, s, s)
                ctx.fill()
            else:
                ctx.set_line_width(2)
                rgba(ctx, DIM, 0.6 * a)
                ctx.rectangle(cx + 1, y + 1, s - 2, s - 2)
                ctx.stroke()
        ox = x + s + g
        if bit:
            rgba(ctx, INK, 0.85 * a)
            ctx.rectangle(ox, y + s + g + 4, s, s)
            ctx.fill()
        else:
            ctx.set_line_width(2)
            rgba(ctx, DIM, 0.6 * a)
            ctx.rectangle(ox + 1, y + s + g + 5, s - 2, s - 2)
            ctx.stroke()
        ctx.restore()


DATA = [
    ("WIDTH", f"{COLS}"),
    ("EPOCHS", f"{ROWS}"),
    ("SEED", "0x5F3A"),
    ("RADIUS", "r = 1"),
    ("STATES", "k = 2"),
    ("BOUNDARY", "PERIODIC"),
]


def scene(ctx, s):
    """Draw every element. `s` holds the reveal state of each element."""
    # Frame
    ctx.set_line_width(2)
    rgba(ctx, DIM, 0.7)
    corner_brackets(ctx, 110, 150, W - 110, H - 110, 70, s["frame"])
    ctx.set_line_width(1.5)
    rgba(ctx, LINE, 1)
    tick_ruler(ctx, FX0, FY0 - 22, FX1, FY0 - 22, PITCH * 4, 4, 8, 16, s["ruler"], -1)
    tick_ruler(ctx, FX0 - 22, FY0, FX0 - 22, FY1, PITCH * 4, 5, 8, 16, s["ruler"], -1)
    if s["ruler"] > 0:
        a = smooth(s["ruler"])
        for c in range(0, COLS, 16):
            text(ctx, FX0 + c * PITCH, FY0 - 52, f"{c:03d}", 17, MUTED, a, 0.05)
        for r in range(0, ROWS, 20):
            text(ctx, FX0 - 46, FY0 + r * PITCH + 6, f"{r:03d}", 17, MUTED, a, 0.05, "right")

    # Field corner marks
    ctx.set_line_width(2)
    rgba(ctx, INK, 0.55)
    corner_brackets(ctx, FX0 - 10, FY0 - 10, FX1 + 10, FY1 + 10, 28, s["frame"])

    dots, cells, hi = layers()
    if s["dots"] > 0:
        ctx.set_source_surface(dots, 0, 0)
        ctx.paint_with_alpha(smooth(s["dots"]))
    front = s["front"]
    # Whole rows only: finished rows at full strength, the row under the
    # line fading in as the line crosses it.
    done = int(front)
    paint_rows(ctx, cells, 0, done)
    if done < ROWS:
        paint_rows(ctx, cells, done, done + 1, smooth(front - done))
    if s["front_glow"] > 0:
        yf = FY0 + front * PITCH
        head(ctx, hi, yf, s["front_glow"])
        scanline(ctx, yf, s["front_glow"], f"GEN {min(ROWS, int(front)):03d}")
    if s["scan"] is not None:
        y, a = s["scan"]
        head(ctx, hi, y, 0.85 * a)
        row = int(clamp((y - FY0) / PITCH, 0, ROWS - 1))
        scanline(ctx, y, a, f"GEN {row:03d}")

    # Left column
    text(ctx, LX - 6, 560, "RULE 110", 124, INK, 1, 0.04, chars=s["title"] * 8)
    text(ctx, LX, 628, "ELEMENTARY CELLULAR AUTOMATON", 25, DIM, 1, 0.14, chars=s["sub"] * 29)
    ctx.set_line_width(1.5)
    rgba(ctx, LINE, 1)
    partial_line(ctx, LX, 740, LX + 820, 740, ease_out(s["rule"]))
    rule_table(ctx, s["entries"])
    text(ctx, LX, 1180, "0b01101110 = 110", 26, INK, 1, 0.14, chars=s["bits"] * 16)
    partial_line(ctx, LX, 1250, LX + 820, 1250, ease_out(s["data"]))
    for i, (k, v) in enumerate(DATA):
        p = seg(s["data"], i * 0.08, i * 0.08 + 0.5)
        y = 1320 + i * 52
        text(ctx, LX, y, k, 24, MUTED, 1, 0.16, chars=p * len(k))
        text(ctx, LX + 300, y, v, 24, INK, 1, 0.16, chars=p * len(v))
    partial_line(ctx, LX, 1690, LX + 820, 1690, ease_out(s["data"]))
    gen = f"GEN {min(ROWS, int(front)):03d}"
    text(ctx, LX, 1760, gen, 40, INK, 1, 0.12, chars=s["gen"] * len(gen))
    if s["gen"] >= 1 and s["cursor"]:
        rgba(ctx, INK, 0.85)
        ctx.rectangle(LX + text_width(ctx, gen + " ", 40, 0.12), 1728, 22, 38)
        ctx.fill()


def final_state():
    return dict(frame=1, ruler=1, dots=1, front=ROWS, front_glow=0, scan=None,
                label=1, title=1, sub=1, rule=1, entries=[1] * 8, bits=1,
                data=1, gen=1, cursor=True)


def still():
    surf, ctx = new_frame()
    scene(ctx, final_state())
    return surf


def intro(t):
    surf, ctx = new_frame()
    comp = seg(t, 1.4, 5.1)
    front = ROWS * ease_in_out(comp)
    s = dict(
        frame=seg(t, 0.0, 0.9),
        ruler=ease_out(seg(t, 0.2, 1.5)),
        dots=seg(t, 0.5, 1.6),
        front=front,
        front_glow=smooth(seg(t, 1.3, 1.6)) * (1 - smooth(seg(t, 5.1, 5.7))),
        scan=None,
        label=seg(t, 0.3, 0.9),
        title=seg(t, 0.55, 1.35),
        sub=seg(t, 1.0, 1.9),
        rule=seg(t, 1.1, 1.8),
        entries=[seg(t, 1.2 + i * 0.09, 1.65 + i * 0.09) for i in range(8)],
        bits=seg(t, 2.0, 2.6),
        data=seg(t, 1.9, 3.3),
        gen=seg(t, 1.5, 1.8),
        cursor=cursor_on(t - INTRO),
    )
    scene(ctx, s)
    return surf


def loop(t):
    surf, ctx = new_frame()
    s = final_state()
    travel = (FY1 - FY0) + 480
    y = FY0 - 240 + travel * (t / LOOP)
    inside = clamp(min(y - (FY0 - 200), (FY1 + 200) - y) / 160)
    s["scan"] = (y, smooth(inside))
    s["cursor"] = cursor_on(t)
    scene(ctx, s)
    return surf


if __name__ == "__main__":
    # 60 fps so the scan line glides instead of stepping 6 px per frame.
    main(NAME, still, intro, INTRO, loop, LOOP, loop_fps=60)
