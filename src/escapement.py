"""02 — Escapement. A lever escapement and gear train, drawn as a technical plate.

Loop maths (60 s, one beat per second):
  escape wheel E   15 T, 5 spokes    1/30 rev per beat  -> 2 rev per loop
  pinion pE        10 L on E         20 teeth per loop  -> drives W
  wheel W          60 T, 6 spokes    20/60 = 1/3 rev    -> 2 spoke periods
  wheel B          80 T, 8 spokes    20/80 = 1/4 rev    -> 2 spoke periods
Every part returns to an identical image after 60 s, so the loop has no seam.
"""

import math

import cairo

from common import *

NAME = "2-escapement"
INTRO = 6.5
LOOP = 60.0
TAU = math.tau
LX = 260

MOD = 12
NB, NW, NPE, NE = 80, 60, 10, 15
RB, RW, RPE = MOD * NB / 2, MOD * NW / 2, MOD * NPE / 2
RE = 172


def polar(c, r, a):
    return c[0] + r * math.cos(a), c[1] + r * math.sin(a)


CB = (2230, 1350)
A_BW = math.radians(-38)
CW = polar(CB, RB + RW, A_BW)
A_WE = math.radians(25)
CE = polar(CW, RW + RPE, A_WE)
A_EF = math.radians(95)
CF = polar(CE, RE * 1.52, A_EF)
CBAL = polar(CF, 430, A_EF)
RBAL = 205


def mesh_phase(n_a, ph_a, n_b, alpha):
    """Phase for gear B so its gap meets gear A's tooth on the line of centres.

    alpha is the direction from A to B. Tooth centres sit at phase + k * pitch.
    B turns by -delta * n_a / n_b whenever A turns by delta, so one alignment
    at rest keeps the pair meshed for every later angle.
    """
    o = (alpha - ph_a) % (TAU / n_a)
    return alpha + math.pi + o * n_a / n_b + math.pi / n_b


# ------------------------------------------------------------ kinematics ---

def beat_ease(f):
    """One escapement drop: fast lift, small recoil, then rest."""
    if f >= 0.16:
        return 1.0
    return ease_out_back(f / 0.16, 2.2)


def mech(tm, spin=0.0, amp=1.0):
    """Angles for mechanical time tm (seconds). spin adds extra E turns."""
    beats = math.floor(tm) + beat_ease(tm - math.floor(tm))
    e_rev = beats / 30 + spin
    teeth = e_rev * NPE  # teeth passed at the pE / W mesh
    a_e = TAU * e_rev
    a_w = -TAU * teeth / NW
    a_b = TAU * teeth / NB
    k = math.floor(tm)
    f = tm - k
    prev = 1 if (k - 1) % 2 == 0 else -1
    cur = 1 if k % 2 == 0 else -1
    lever = math.radians(6) * lerp(prev, cur, smooth(f / 0.16))
    bal = math.radians(165) * amp * math.sin(math.pi * tm)
    return dict(e=a_e, w=a_w, b=a_b, lever=lever, bal=bal, beat=k % 60, flash=1 - smooth(f / 0.5))


# Phases so the three meshes interlock at rest.
PH_W0 = 0.0
PH_B0 = mesh_phase(NW, PH_W0, NB, A_BW + math.pi)
PH_E0 = mesh_phase(NW, PH_W0, NPE, A_WE)


# --------------------------------------------------------------- drawing ---

def gear_points(c, n, r, m, phase, profile="clock", samples=14):
    ra, rd = r + m * (1.05 if profile != "pinion" else 0.9), r - m * 1.25
    pts = []
    for k in range(n):
        for j in range(samples):
            u = j / samples
            a = phase + (k + u - 0.5) * TAU / n
            if profile == "escape":
                # Club tooth: long leaning flank, short drop face.
                if u < 0.12:
                    h = 0
                elif u < 0.78:
                    h = ((u - 0.12) / 0.66) ** 0.8
                elif u < 0.86:
                    h = 1
                else:
                    h = max(0, 1 - (u - 0.86) / 0.05)
            else:
                d = abs(u - 0.5)
                w0, w1 = (0.27, 0.10) if profile == "clock" else (0.30, 0.16)
                if d < w1:
                    h = 1
                elif d > w0:
                    h = 0
                else:
                    x = (d - w1) / (w0 - w1)
                    h = math.sqrt(max(0, 1 - x * x))
            rr = rd + (ra - rd) * h
            pts.append(polar(c, rr, a))
    return pts


def path_poly(ctx, pts):
    ctx.move_to(*pts[0])
    for p in pts[1:]:
        ctx.line_to(*p)
    ctx.close_path()


def spoke_windows(ctx, c, n, r_in, r_hub, phase, curve=0.22, half_w=11):
    """Cut-outs between constant-width curved crossings, as closed paths."""
    steps = 24

    def theta(k, rho):
        return phase + k * TAU / n + curve * (rho - r_hub) / (r_in - r_hub)

    for k in range(n):
        rhos = [lerp(r_hub, r_in, i / steps) for i in range(steps + 1)]
        e1 = [polar(c, rho, theta(k, rho) + math.asin(half_w / rho)) for rho in rhos]
        e2 = [polar(c, rho, theta(k + 1, rho) - math.asin(half_w / rho)) for rho in reversed(rhos)]
        o0 = theta(k, r_in) + math.asin(half_w / r_in)
        o1 = theta(k + 1, r_in) - math.asin(half_w / r_in)
        i0 = theta(k + 1, r_hub) - math.asin(half_w / r_hub)
        i1 = theta(k, r_hub) + math.asin(half_w / r_hub)
        ctx.move_to(*e1[0])
        for p in e1[1:]:
            ctx.line_to(*p)
        ctx.arc(c[0], c[1], r_in, o0, o1)
        for p in e2:
            ctx.line_to(*p)
        ctx.arc_negative(c[0], c[1], r_hub, i0, i1)
        ctx.close_path()


def wheel(ctx, c, n, r, phase, spokes, reveal=1.0, profile="clock", m=MOD,
          rim=0.82, hub=0.2, curve=0.22, rings=()):
    if reveal <= 0:
        return
    pts = gear_points(c, n, r, m, phase, profile)
    a = smooth(reveal)
    # Body with spoke windows cut out (even-odd).
    ctx.save()
    ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    path_poly(ctx, pts)
    if spokes:
        spoke_windows(ctx, c, spokes, r * rim, r * hub + 26, phase, curve)
    rgba(ctx, SURFACE, 0.94 * a)
    ctx.fill_preserve()
    ctx.save()
    ctx.clip_preserve()
    ctx.set_line_width(1)
    rgba(ctx, INK, 0.045 * a)
    rr = 14.0
    while rr < r + m:
        ctx.new_path()
        ctx.arc(c[0], c[1], rr, 0, TAU)
        ctx.stroke()
        rr += 5.0
    ctx.restore()
    ctx.new_path()
    path_poly(ctx, pts)
    if spokes:
        spoke_windows(ctx, c, spokes, r * rim, r * hub + 26, phase, curve)
    ctx.set_line_width(2.4)
    rgba(ctx, INK, 0.78 * a)
    ctx.stroke()
    ctx.restore()
    # Engraving: concentric rings on the rim and hub.
    ctx.set_line_width(1.3)
    rgba(ctx, DIM, 0.28 * a)
    for f in rings:
        ctx.arc(c[0], c[1], r * f, 0, TAU)
        ctx.stroke()
    if spokes:
        ctx.arc(c[0], c[1], r * rim + 10, 0, TAU)
        ctx.stroke()
        ctx.arc(c[0], c[1], r * hub + 26, 0, TAU)
        ctx.stroke()


def arc_dashed(ctx, c, r, a0, a1, dash=(10, 12)):
    ctx.set_dash(dash)
    ctx.arc(c[0], c[1], r, a0, a1)
    ctx.stroke()
    ctx.set_dash([])


def jewel(ctx, c, a=1.0, r=11):
    rgba(ctx, RED, 0.95 * a)
    ctx.arc(c[0], c[1], r, 0, TAU)
    ctx.fill()
    ctx.set_line_width(2)
    rgba(ctx, INK, 0.7 * a)
    ctx.arc(c[0], c[1], r + 7, 0, TAU)
    ctx.stroke()
    rgba(ctx, INK_HI, 0.5 * a)
    ctx.arc(c[0] - 3, c[1] - 3, 3, 0, TAU)
    ctx.fill()


def hairspring(ctx, c, bal, a):
    """Archimedean spiral; the inner end turns with the balance, the stud holds
    the outer end, so the coils breathe as the balance swings."""
    turns, r0, r1 = 11, 22, 128
    steps = 900
    ctx.set_line_width(1.4)
    rgba(ctx, INK, 0.55 * a)
    for i in range(steps + 1):
        u = i / steps
        ang = TAU * turns * u + bal * (1 - u) + math.radians(-60)
        rr = r0 + (r1 - r0) * u + 2.2 * math.sin(bal) * u * (1 - u)
        p = polar(c, rr, ang)
        if i == 0:
            ctx.move_to(*p)
        else:
            ctx.line_to(*p)
    ctx.stroke()
    # Stud
    s = polar(c, r1 + 6, TAU * turns + math.radians(-60))
    rgba(ctx, INK, 0.8 * a)
    ctx.arc(s[0], s[1], 6, 0, TAU)
    ctx.fill()


def balance(ctx, st, a):
    if a <= 0:
        return
    c, r, ang = CBAL, RBAL, st["bal"]
    ctx.save()
    ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    ctx.arc(c[0], c[1], r, 0, TAU)
    ctx.new_sub_path()
    ctx.arc(c[0], c[1], r - 22, 0, TAU)
    rgba(ctx, SURFACE, 0.95 * a)
    ctx.fill_preserve()
    ctx.set_line_width(2.4)
    rgba(ctx, INK, 0.8 * a)
    ctx.stroke()
    ctx.restore()
    # Three arms
    ctx.set_line_width(12)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    rgba(ctx, SURFACE, a)
    for k in range(3):
        q = polar(c, r - 20, ang + k * TAU / 3)
        ctx.move_to(*c)
        ctx.line_to(*q)
    ctx.stroke()
    ctx.set_line_width(2)
    rgba(ctx, INK, 0.75 * a)
    for k in range(3):
        for s in (-1, 1):
            p0 = polar(c, 16, ang + k * TAU / 3 + s * 0.35)
            p1 = polar(c, r - 22, ang + k * TAU / 3 + s * 0.03)
            ctx.move_to(*p0)
            ctx.line_to(*p1)
    ctx.stroke()
    ctx.set_line_cap(cairo.LINE_CAP_BUTT)
    # Rim screws
    for k in range(16):
        q = polar(c, r + 2, ang + k * TAU / 16 + 0.1)
        rgba(ctx, RAISED, a)
        ctx.arc(q[0], q[1], 9, 0, TAU)
        ctx.fill_preserve()
        ctx.set_line_width(1.6)
        rgba(ctx, INK, 0.7 * a)
        ctx.stroke()
        s0 = polar(q, 6, ang + k * TAU / 16 + 0.1)
        s1 = polar(q, -6, ang + k * TAU / 16 + 0.1)
        ctx.move_to(*s0)
        ctx.line_to(*s1)
        ctx.stroke()
    hairspring(ctx, c, ang, a)
    # Roller with impulse pin
    rgba(ctx, INK, 0.7 * a)
    ctx.set_line_width(2)
    ctx.arc(c[0], c[1], 34, 0, TAU)
    ctx.stroke()
    pin = polar(c, 34, ang - math.pi / 2 - math.radians(5) + math.pi)
    rgba(ctx, RED, 0.9 * a)
    ctx.arc(pin[0], pin[1], 6, 0, TAU)
    ctx.fill()
    jewel(ctx, c, a, 9)


def lever(ctx, st, a):
    """Pallet fork: two pallet stones at the escape wheel, a fork at the roller."""
    if a <= 0:
        return
    base = math.atan2(CE[1] - CF[1], CE[0] - CF[0])
    ang = base + st["lever"]
    ctx.save()
    ctx.translate(*CF)
    ctx.rotate(ang)
    d = math.hypot(CE[0] - CF[0], CE[1] - CF[1])
    # Arms toward the wheel
    L = d - RE * 0.86
    spread = 0.62
    arm_pts = [(0, -16), (L * math.cos(spread) * 0.95, -L * math.sin(spread)),
               (L * math.cos(spread) * 0.95 + 18, -L * math.sin(spread) + 14),
               (40, 0),
               (L * math.cos(spread) * 0.95 + 18, L * math.sin(spread) - 14),
               (L * math.cos(spread) * 0.95, L * math.sin(spread)), (0, 16)]
    # Tail toward the balance
    tail = d * 0 + (math.hypot(CBAL[0] - CF[0], CBAL[1] - CF[1]) - 34)
    ctx.move_to(*arm_pts[0])
    for p in arm_pts[1:]:
        ctx.line_to(*p)
    ctx.line_to(-tail + 30, 12)
    ctx.line_to(-tail, 24)
    ctx.line_to(-tail + 10, 6)
    ctx.line_to(-tail + 10, -6)
    ctx.line_to(-tail, -24)
    ctx.line_to(-tail + 30, -12)
    ctx.close_path()
    rgba(ctx, RAISED, 0.96 * a)
    ctx.fill_preserve()
    ctx.set_line_width(2.2)
    rgba(ctx, INK, 0.8 * a)
    ctx.stroke()
    # Pallet stones (rubies)
    for s in (-1, 1):
        x, y = L * math.cos(spread) * 0.95 + 9, s * (L * math.sin(spread) - 5)
        ctx.save()
        ctx.translate(x, y)
        ctx.rotate(-s * 0.9)
        ctx.rectangle(-5, -14, 10, 28)
        rgba(ctx, RED, 0.9 * a)
        ctx.fill()
        ctx.restore()
    ctx.restore()
    jewel(ctx, CF, a, 8)


def construction(ctx, p, st):
    """Static technical-drawing layer: pitch circles, centre lines, dimensions."""
    if p <= 0:
        return
    a = smooth(p)
    ctx.set_line_width(1.2)
    rgba(ctx, MUTED, 0.55 * a)
    sweep = TAU * ease_out(p)
    for c, r in ((CB, RB), (CW, RW), (CE, RPE), (CE, RE + 40), (CBAL, RBAL + 40)):
        arc_dashed(ctx, c, r, -math.pi / 2, -math.pi / 2 + sweep, (6, 10))
    # Centre lines through each arbor
    rgba(ctx, LINE, 0.9 * a)
    for (c0, c1) in ((CB, CW), (CW, CE), (CE, CF), (CF, CBAL)):
        dx, dy = c1[0] - c0[0], c1[1] - c0[1]
        n = math.hypot(dx, dy)
        ux, uy = dx / n, dy / n
        partial_line(ctx, c0[0] - ux * 60, c0[1] - uy * 60, c1[0] + ux * 60, c1[1] + uy * 60, ease_out(p))
    for c in (CB, CW, CE, CF, CBAL):
        rgba(ctx, DIM, 0.6 * a)
        crosshair(ctx, c[0], c[1], 30 * a + 1, 22)
    # Graduated ring around B
    ctx.set_line_width(1.5)
    r0 = RB + 70
    n = int(120 * ease_out(p))
    for k in range(n):
        ang = -math.pi / 2 + k * TAU / 120
        L = 24 if k % 10 == 0 else 12
        rgba(ctx, DIM if k % 10 == 0 else MUTED, 0.8 * a)
        ctx.move_to(*polar(CB, r0, ang))
        ctx.line_to(*polar(CB, r0 + L, ang))
        ctx.stroke()
    for k in range(12):
        if k * 10 >= n:
            break
        ang = -math.pi / 2 + k * TAU / 12
        q = polar(CB, r0 + 58, ang)
        text(ctx, q[0], q[1] + 7, f"{k * 5:02d}", 19, MUTED, a, 0.05, "center")
    ctx.arc(CB[0], CB[1], r0, -math.pi / 2, -math.pi / 2 + TAU * ease_out(p))
    rgba(ctx, LINE, a)
    ctx.stroke()
    # Labels
    labels = [
        (polar(CB, RB + 175, math.radians(145)), "B  ·  80 T  ·  m 0.12"),
        (polar(CW, RW + 90, math.radians(-120)), "W  ·  60 T"),
        (polar(CE, RE + 95, math.radians(-40)), "E  ·  15 T  CLUB"),
        (polar(CBAL, RBAL + 110, math.radians(160)), "BALANCE  ·  ±165°"),
        (polar(CF, 150, math.radians(185)), "PALLET FORK"),
    ]
    for (x, y), s in labels:
        text(ctx, x, y, s, 19, DIM, a, 0.14, "center", chars=p * 1.4 * len(s))
    # Dimension B–W
    mx, my = (CB[0] + CW[0]) / 2, (CB[1] + CW[1]) / 2
    text(ctx, mx + 36, my + 40, f"C {RB + RW:.0f}", 17, MUTED, a, 0.05)


DATA = [
    ("TRAIN", "80 · 60 / 10"),
    ("ESCAPE", "15 T CLUB"),
    ("BEAT", "1.0 Hz · 3 600 VPH"),
    ("AMPLITUDE", "±165°"),
    ("LIFT", "12°"),
    ("RATIO", "B : E = 1 : 8"),
]


def scene(ctx, st, s):
    ctx.set_line_width(2)
    rgba(ctx, DIM, 0.7)
    corner_brackets(ctx, 110, 150, W - 110, H - 110, 70, s["frame"])
    ctx.set_line_width(1.5)
    rgba(ctx, LINE, 1)
    tick_ruler(ctx, 1240, H - 150, W - 150, H - 150, 32, 5, 8, 18, s["frame"], -1)

    ctx.save()
    if not WIDE:
        # The 3:2 frame is 600 px narrower: shrink the machine about its
        # vertical centre and park it 250 px from the right edge.
        k = 0.86
        ctx.translate(W - 250 - k * 3500, 1195 * (1 - k))
        ctx.scale(k, k)
    construction(ctx, s["build"], st)
    wr = s["wheels"]
    wheel(ctx, CB, NB, RB, PH_B0 + st["b"], 8, wr[0], rings=(0.94, 0.12), curve=0.16)
    wheel(ctx, CW, NW, RW, PH_W0 + st["w"], 6, wr[1], rings=(0.12,), curve=-0.2)
    # Escape wheel sits on its own plane above W, with its pinion under it.
    wheel(ctx, CE, NPE, RPE, PH_E0 + st["e"], 0, wr[2], profile="pinion", rings=(0.45,))
    wheel(ctx, CE, NE, RE, PH_E0 + st["e"], 5, wr[2], profile="escape", m=26,
          rim=0.7, hub=0.18, curve=0.3, rings=(0.62,))
    lever(ctx, st, s["lever"])
    balance(ctx, st, s["balance"])
    for c, p in ((CB, wr[0]), (CW, wr[1]), (CE, wr[2])):
        if p > 0:
            jewel(ctx, c, smooth(p))
    ctx.restore()

    # Left column
    text(ctx, LX - 6, 560, "ESCAPEMENT", 118, INK, 1, 0.02, chars=s["title"] * 10)
    text(ctx, LX, 628, "SWISS LEVER  ·  GEAR TRAIN", 25, DIM, 1, 0.14, chars=s["sub"] * 26)
    ctx.set_line_width(1.5)
    rgba(ctx, LINE, 1)
    partial_line(ctx, LX, 740, LX + 820, 740, ease_out(s["data"]))
    for i, (k, v) in enumerate(DATA):
        p = seg(s["data"], i * 0.08, i * 0.08 + 0.5)
        y = 820 + i * 56
        text(ctx, LX, y, k, 24, MUTED, 1, 0.16, chars=p * len(k))
        text(ctx, LX + 300, y, v, 24, INK, 1, 0.16, chars=p * len(v))
    partial_line(ctx, LX, 1190, LX + 820, 1190, ease_out(s["data"]))
    tick = f"TICK {st['beat']:02d}"
    text(ctx, LX, 1270, tick, 40, INK, 1, 0.12, chars=s["gen"] * len(tick))
    if s["gen"] >= 1:
        rgba(ctx, RED, 0.25 + 0.75 * st["flash"])
        ctx.arc(LX + text_width(ctx, tick + "  ", 40, 0.12) + 8, 1256, 9, 0, TAU)
        ctx.fill()
    # Beat strip: 60 marks, the current one lit.
    if s["gen"] > 0:
        for k in range(60):
            x = LX + k * 13.6
            on = k == st["beat"]
            past = k < st["beat"]
            rgba(ctx, INK if on else (DIM if past else LINE), (1 if on else 0.6) * smooth(s["gen"]))
            ctx.rectangle(x, 1400, 7, 28 if k % 5 == 0 else 18)
            ctx.fill()


def full():
    return dict(frame=1, build=1, wheels=(1, 1, 1), lever=1, balance=1,
                label=1, title=1, sub=1, data=1, gen=1)


def still():
    surf, ctx = new_frame()
    scene(ctx, mech(0.0), full())
    return surf


def intro(t):
    surf, ctx = new_frame()
    # The train spins down into its rest position as the balance starts.
    spin_p = seg(t, 1.6, INTRO)
    spin = -4.0 * (1 - ease_out(spin_p, 3))
    amp = smooth(seg(t, 3.8, INTRO))
    st = mech(0.0, spin)
    st["bal"] = math.radians(165) * amp * math.sin(math.pi * (t - INTRO))
    s = dict(
        frame=seg(t, 0.0, 0.9),
        build=seg(t, 0.3, 2.4),
        wheels=(seg(t, 1.0, 2.0), seg(t, 1.3, 2.3), seg(t, 1.6, 2.6)),
        lever=seg(t, 2.0, 2.8),
        balance=seg(t, 2.3, 3.2),
        label=seg(t, 0.3, 0.9),
        title=seg(t, 0.55, 1.35),
        sub=seg(t, 1.0, 1.9),
        data=seg(t, 1.6, 3.2),
        gen=seg(t, 2.8, 3.2),
    )
    scene(ctx, st, s)
    return surf


def loop(t):
    surf, ctx = new_frame()
    scene(ctx, mech(t), full())
    return surf


if __name__ == "__main__":
    main(NAME, still, intro, INTRO, loop, LOOP)
