"""04 — Cyclic. Griffeath's cyclic cellular automaton as a text-free texture.

Eight states; a cell advances to the next state when at least three cells in
its radius-2 Moore neighbourhood already hold it. Random noise organises into
spiral waves. Once the spirals own the whole torus, every cell cycles through
all eight states, so the field repeats exactly every 8 generations.

The intro is the real evolution from noise, fast at first and slowing into
the steady spirals. Skipped generations are averaged, so the early noise reads
as grain instead of flicker.
"""

import math

import cairo
import numpy as np

from common import *

NAME = "4-cyclic"
N, RADIUS, THRESHOLD = 8, 2, 3
PITCH, GAP = 10, 2
COLS, ROWS = W // PITCH, H // PITCH
INTRO = 8.0
GPS = 1.0  # generations per second in the loop
LOOP = N / GPS
OFFS = [(a, b) for a in range(-RADIUS, RADIUS + 1) for b in range(-RADIUS, RADIUS + 1) if a or b]


def step(s):
    nxt = (s + 1) % N
    cnt = np.zeros(s.shape, np.int8)
    for a, b in OFFS:
        cnt += np.roll(np.roll(s, a, 0), b, 1) == nxt
    return np.where(cnt >= THRESHOLD, nxt, s).astype(np.int8)


def settle():
    """Run from noise until the field repeats with period N, then round the
    steady start up to a multiple of N."""
    rng = np.random.default_rng(11)
    s = rng.integers(0, N, (ROWS, COLS)).astype(np.int8)
    states = [s]
    g = 0
    while True:
        s = step(s)
        states.append(s)
        g += 1
        if g > N and g % N == 0 and np.array_equal(states[g], states[g - N]):
            break
        assert g < 20000, "cyclic automaton never settled"
    g0 = g - N
    return states, g0


STATES, G0 = settle()
# Brightness per state: the wave crest (state 0) is brightest.


def level(phase):
    """Brightness for a continuous phase in [0, N).

    The crest (phase 0) is brightest and decays over the next N - 1 states;
    the last state rises linearly back to the crest, so the profile has no
    jump anywhere and a travelling wave reads as one gliding front.
    """
    p = np.mod(phase, N).astype(np.float32)
    rise = np.clip(p - (N - 1), 0, 1)
    decay = np.clip(1 - p / (N - 1), 0, 1) ** 2.4
    # A linear rise keeps the front moving at an even pace across each step.
    return np.where(p > N - 1, rise, decay).astype(np.float32)


def wrap(g):
    return G0 + (g - G0) % N if g > G0 + N else g


def state_value(g):
    return level(STATES[wrap(g)])


_base = None
_mask = None


def base_rgb():
    global _base, _mask
    if _base is None:
        surf = base_surface()
        stride = surf.get_stride()
        arr = np.ndarray((H, stride // 4, 4), np.uint8, surf.get_data())[:, :W, :3]
        _base = arr.astype(np.float32)  # BGR
        cell = np.zeros((PITCH, PITCH), np.float32)
        cell[GAP // 2 : PITCH - GAP // 2, GAP // 2 : PITCH - GAP // 2] = 1
        _mask = np.tile(cell, (ROWS, COLS))
        _mask = np.pad(_mask, ((0, H - _mask.shape[0]), (0, W - _mask.shape[1])))
    return _base, _mask


CREST = np.array(INK[::-1], np.float32) * 255  # BGR
PEAK = 0.46  # crest opacity; keeps the texture behind windows


def compose(v, fade=1.0):
    """Paint a per-cell value field (0..1) over the paper."""
    base, mask = base_rgb()
    a = np.repeat(np.repeat(v, PITCH, 0), PITCH, 1)
    a = np.pad(a, ((0, H - a.shape[0]), (0, W - a.shape[1])))
    a = (a * mask * PEAK * fade)[..., None]
    rgb = base * (1 - a) + CREST * a
    out = np.empty((H, W, 4), np.uint8)
    out[..., :3] = np.clip(rgb + 0.5, 0, 255)
    out[..., 3] = 255
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    data = np.ndarray((H, surf.get_stride() // 4, 4), np.uint8, surf.get_data())
    data[:, :W] = out
    surf.mark_dirty()
    return surf


def at(g):
    """Value field at fractional generation g.

    Each cell that advances this generation moves its phase linearly from
    one state to the next, so the waves travel at constant speed instead of
    stepping once per generation.
    """
    g0 = math.floor(g)
    f = g - g0
    s0, s1 = STATES[wrap(g0)], STATES[wrap(g0 + 1)]
    advancing = s1 != s0
    return level(s0 + f * advancing)


def still():
    return compose(state_value(G0))


def warp(t):
    """Generation shown at intro time t: fast through the noise, slowing to rest."""
    u = seg(t, 0.4, INTRO)
    return G0 * (1 - (1 - u) ** 3)


def intro(t):
    fade = smooth(seg(t, 0.0, 1.2))
    g = warp(t)
    prev = warp(max(0.0, t - 1 / 60))
    lo, hi = math.floor(prev), math.floor(g)
    if hi - lo >= 2:
        # Motion blur over the generations this frame skipped.
        v = np.mean([state_value(k) for k in range(lo + 1, hi + 1)], axis=0)
    elif t >= INTRO:
        v = state_value(G0)
    else:
        v = at(g)
    return compose(v, fade)


def loop(t):
    return compose(at(G0 + GPS * t))


if __name__ == "__main__":
    main(NAME, still, intro, INTRO, loop, LOOP, loop_fps=60)
