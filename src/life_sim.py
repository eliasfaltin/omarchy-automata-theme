"""Game of Life helpers: RLE parsing, stepping, eater placement search."""
import numpy as np

def rle(s):
    rows, row, n = [], [], ""
    for ch in s.replace("\n", ""):
        if ch.isdigit():
            n += ch; continue
        k = int(n) if n else 1; n = ""
        if ch == "b": row += [0] * k
        elif ch == "o": row += [1] * k
        elif ch == "$":
            rows.append(row); rows += [[]] * (k - 1); row = []
        elif ch == "!":
            rows.append(row); break
    w = max(len(r) for r in rows)
    a = np.zeros((len(rows), w), np.uint8)
    for i, r in enumerate(rows): a[i, :len(r)] = r
    return a

def step(a):
    n = sum(np.roll(np.roll(a, dy, 0), dx, 1) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx)
    return ((n == 3) | ((a == 1) & (n == 2))).astype(np.uint8)

GUN = rle("24bo$22bobo$12b2o6b2o12b2o$11bo3bo4b2o12b2o$2o8bo5bo3b2o$2o8bo3bob2o4bobo$10bo5bo7bo$11bo3bo$12b2o!")
EATER = rle("2o$bo$bobo$2b2o!")

def orients(p):
    out = []
    for k in range(4):
        r = np.rot90(p, k)
        out += [r, np.fliplr(r)]
    return out
