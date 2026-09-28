"""Shared plumbing for the Automata background renders.

Every piece exposes a pure function frame(t) -> cairo.ImageSurface. The still,
the last intro frame and the first loop frame all come from the same state, so
OWE can hand over between them without a visible jump.
"""

import math
import multiprocessing as mp
import os
import subprocess
import sys

import cairo
import numpy as np

# One layout per display shape. Both share the 2160 px height, so vertical
# positions stay identical and only the horizontal composition reflows.
ASPECTS = {"16x9": (3840, 2160), "3x2": (3240, 2160)}
ASPECT = os.environ.get("AUTOMATA_ASPECT", "16x9")
W, H = ASPECTS[ASPECT]
WIDE = ASPECT == "16x9"
MODE = os.environ.get("AUTOMATA_MODE", "dark")
LIGHT = MODE == "light"
VARIANTS = os.path.expanduser("~/.local/share/automata/variants")
# Dark renders live in <aspect>/, light renders in light-<aspect>/.
VARIANT_DIR = ("light-" if LIGHT else "") + ASPECT
# Any installed monospace family works; the published renders use Berkeley Mono.
FONT = os.environ.get("AUTOMATA_FONT", "Berkeley Mono")


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))


# The t3themes NieR: Automata palette. The names describe roles, not
# brightness: INK is the drawing colour and BG the paper, in either mode.
if not LIGHT:
    BG = hexrgb("#2b2923")
    BG_DEEP = hexrgb("#211f1b")
    BG_LIFT = hexrgb("#2f2d26")
    SURFACE = hexrgb("#36342c")
    RAISED = hexrgb("#3b3930")
    LINE = hexrgb("#4f4d45")
    MUTED = hexrgb("#6f6c5e")
    DIM = hexrgb("#a8a593")
    INK = hexrgb("#d1cdb7")
    INK_HI = hexrgb("#dcd8c2")
    RED = hexrgb("#c96b57")
else:
    BG = hexrgb("#ccc8b1")
    BG_DEEP = hexrgb("#bcb8a0")
    BG_LIFT = hexrgb("#d3cfb9")
    SURFACE = hexrgb("#c3bfa7")
    RAISED = hexrgb("#bab69e")
    LINE = hexrgb("#a29e89")
    MUTED = hexrgb("#7f7b67")
    DIM = hexrgb("#4d4b3f")
    INK = hexrgb("#211f1b")
    INK_HI = hexrgb("#15130f")
    RED = hexrgb("#a94a38")


# ---------------------------------------------------------------- easing ---

def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def seg(t, a, b):
    """Progress of t through the window [a, b], clamped to 0..1."""
    return clamp((t - a) / (b - a)) if b > a else float(t >= b)


def smooth(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out(x, p=3):
    x = clamp(x)
    return 1 - (1 - x) ** p


def ease_in_out(x):
    x = clamp(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_out_back(x, s=1.4):
    x = clamp(x) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def lerp(a, b, x):
    return a + (b - a) * x


# ----------------------------------------------------------------- base ---

_base_cache = None


def base_surface():
    """Charcoal paper: soft radial falloff plus static grain.

    The grain is identical on every frame, so it dithers gradient banding in
    8-bit video without costing bitrate.
    """
    global _base_cache
    if _base_cache is not None:
        return _base_cache
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = W * 0.56, H * 0.48
    d = np.sqrt(((xx - cx) / (W * 0.62)) ** 2 + ((yy - cy) / (H * 0.78)) ** 2)
    v = np.clip(d, 0, 1.25) / 1.25
    v = v * v * (3 - 2 * v)
    lift, deep = np.array(BG_LIFT), np.array(BG_DEEP)
    rgb = lift[None, None, :] * (1 - v[..., None]) + deep[None, None, :] * v[..., None]
    rng = np.random.default_rng(7)
    grain = rng.normal(0, 1.1, (H, W)).astype(np.float32)
    rgb = np.clip(rgb * 255 + grain[..., None], 0, 255).astype(np.uint8)
    buf = np.empty((H, W, 4), np.uint8)
    buf[..., 0], buf[..., 1], buf[..., 2], buf[..., 3] = rgb[..., 2], rgb[..., 1], rgb[..., 0], 255
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    stride = surf.get_stride()
    data = np.ndarray((H, stride // 4, 4), np.uint8, surf.get_data())
    data[:, :W, :] = buf
    surf.mark_dirty()
    _base_cache = surf
    return surf


def new_frame():
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    ctx.set_source_surface(base_surface(), 0, 0)
    ctx.paint()
    return surf, ctx


def layer():
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    return surf, cairo.Context(surf)


# ----------------------------------------------------------------- draw ---

def rgba(ctx, c, a=1.0):
    ctx.set_source_rgba(c[0], c[1], c[2], a)


def text(ctx, x, y, s, size=26, color=INK, alpha=1.0, track=0.12,
         align="left", weight=cairo.FONT_WEIGHT_NORMAL, chars=None):
    """Draw tracked monospace text. `chars` reveals only the first n glyphs."""
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, weight)
    ctx.set_font_size(size)
    adv = ctx.text_extents("M").x_advance + size * track
    total = adv * len(s) - size * track
    if align == "right":
        x -= total
    elif align == "center":
        x -= total / 2
    n = len(s) if chars is None else max(0, min(len(s), int(chars)))
    rgba(ctx, color, alpha)
    for i, ch in enumerate(s[:n]):
        ctx.move_to(x + i * adv, y)
        ctx.show_text(ch)
    return total


def text_width(ctx, s, size=26, track=0.12):
    ctx.select_font_face(FONT)
    ctx.set_font_size(size)
    adv = ctx.text_extents("M").x_advance + size * track
    return adv * len(s) - size * track


def partial_line(ctx, x0, y0, x1, y1, p):
    if p <= 0:
        return
    ctx.move_to(x0, y0)
    ctx.line_to(lerp(x0, x1, p), lerp(y0, y1, p))
    ctx.stroke()


def corner_brackets(ctx, x0, y0, x1, y1, arm=60, p=1.0):
    """Four L-shaped corner marks; p grows the arms from the corners."""
    a = arm * ease_out(p)
    if a <= 0:
        return
    for cx, cy, sx, sy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        ctx.move_to(cx + sx * a, cy)
        ctx.line_to(cx, cy)
        ctx.line_to(cx, cy + sy * a)
        ctx.stroke()


def tick_ruler(ctx, x0, y0, x1, y1, step, major=5, short=10, long=22, p=1.0, side=1):
    """Ticks along a horizontal or vertical line, revealed left-to-right by p."""
    horizontal = abs(y1 - y0) < abs(x1 - x0)
    length = abs(x1 - x0) if horizontal else abs(y1 - y0)
    n = int(length // step)
    shown = int((n + 1) * clamp(p))
    for i in range(shown):
        L = long if i % major == 0 else short
        if horizontal:
            x = x0 + i * step
            ctx.move_to(x, y0)
            ctx.line_to(x, y0 + side * L)
        else:
            y = y0 + i * step
            ctx.move_to(x0, y)
            ctx.line_to(x0 + side * L, y)
    ctx.stroke()


def crosshair(ctx, x, y, r=14, gap=5):
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ctx.move_to(x + dx * gap, y + dy * gap)
        ctx.line_to(x + dx * r, y + dy * r)
    ctx.stroke()


def cursor_on(t, period=1.0):
    """Block cursor blink. On at t = 0 so the still matches loop frame 0."""
    return (t % period) < period * 0.5


# --------------------------------------------------------------- output ---

def surface_bytes(surf):
    surf.flush()
    stride = surf.get_stride()
    data = np.ndarray((H, stride), np.uint8, surf.get_data())
    return bytes(data[:, : W * 4])


def save_png(surf, path):
    surf.write_to_png(path)
    print(f"wrote {path}", file=sys.stderr)


_frame_fn = None
_frame_times = None


def _render_index(i):
    return surface_bytes(_frame_fn(_frame_times[i]))


def encode(frame_fn, times, fps, out, crf=16, workers=None):
    """Render frame_fn at each time and encode an H.264 file OWE can decode."""
    global _frame_fn, _frame_times
    _frame_fn, _frame_times = frame_fn, list(times)
    tmp = out + ".part.mp4"
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
        "-vf", "scale=out_color_matrix=bt709:out_range=tv:flags=accurate_rnd+full_chroma_int,format=yuv420p",
        "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-tune", "animation",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
        "-movflags", "+faststart", "-an", tmp,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    ctx = mp.get_context("fork")
    workers = workers or max(1, os.cpu_count() - 2)
    n = len(_frame_times)
    with ctx.Pool(workers) as pool:
        for k, buf in enumerate(pool.imap(_render_index, range(n), chunksize=2)):
            proc.stdin.write(buf)
            if k % 30 == 0:
                print(f"  {os.path.basename(out)} {k}/{n}", file=sys.stderr, flush=True)
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit(f"ffmpeg failed for {out}")
    os.replace(tmp, out)
    print(f"wrote {out}", file=sys.stderr)


INTRO_HOLD = 1.0


def intro_times(duration, fps, hold=INTRO_HOLD):
    n = int(round(duration * fps)) + 1
    # The last intro frame lands exactly on t = duration, the still's state.
    # A held tail lets automata-intro hand over to the still before OWE sees
    # end of file, so the handover never depends on EOF timing.
    return [duration * i / (n - 1) for i in range(n)] + [duration] * int(hold * fps)


def loop_times(duration, fps):
    n = int(round(duration * fps))
    # Frame n would equal frame 0, so the file stops one frame short.
    return [duration * i / n for i in range(n)]


def main(name, still_fn, intro_fn, intro_dur, loop_fn, loop_dur, out_dir=None,
         intro_fps=60, loop_fps=30):
    """CLI: still | intro | loop | blank | preview T [intro|loop] | all.

    Set AUTOMATA_ASPECT=16x9 or 3x2. Output goes to VARIANTS/<aspect>/.
    """
    args = sys.argv[1:] or ["all"]
    out = os.path.join(VARIANTS, VARIANT_DIR)
    os.makedirs(out, exist_ok=True)
    what = args[0]
    if what == "preview":
        t = float(args[1])
        kind = args[2] if len(args) > 2 else "intro"
        fn = intro_fn if kind == "intro" else loop_fn
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preview",
                            f"{name}-{VARIANT_DIR}-{kind}-{t:05.2f}.png")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        save_png(fn(t), path)
        return
    if what in ("blank", "all"):
        save_png(base_surface(), os.path.join(out, "blank.png"))
    if what in ("still", "all"):
        save_png(still_fn(), os.path.join(out, f"{name}.png"))
    if what in ("intro", "all"):
        encode(intro_fn, intro_times(intro_dur, intro_fps), intro_fps,
               os.path.join(out, f"intro-{name}.mp4"))
    if what in ("loop", "all"):
        encode(loop_fn, loop_times(loop_dur, loop_fps), loop_fps,
               os.path.join(out, f"loop-{name}.mp4"), crf=18)
