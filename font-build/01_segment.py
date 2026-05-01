#!/usr/bin/env python3
"""
Segment Vasya's hand-drawn alphabet sheets into per-glyph PGM files.

Pipeline:
  1. Load PNG, convert to grayscale, binarize (ink=foreground)
  2. Connected-components labeling
  3. Drop noise (tiny components)
  4. Group "diacritic + base" pairs into single glyphs (Ё, Й, ё, й, i, j)
  5. Sort into rows (by y-center), then left-to-right within each row
  6. Map ordered glyph list to expected character sequence (per-row)
  7. Crop bbox + write PGM (potrace input) + debug PNG
"""
import os, sys, json
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw, ImageFont
import numpy as np
from scipy import ndimage

SRC = Path.home() / "Downloads"
WORK = Path.home() / "Desktop" / "cinema-platform" / "font-build"
PGM_DIR = WORK / "glyphs_pgm"
PNG_DIR = WORK / "glyphs_png"
DBG_DIR = WORK / "debug"
for d in (PGM_DIR, PNG_DIR, DBG_DIR):
    d.mkdir(exist_ok=True, parents=True)

SHEETS = [
    {
        "file": "IMG_0177.PNG",
        "name": "cyr_upper",
        "rows": ["АБВГДЕЁЖЗ", "ИЙКЛМНОПР", "СТУФХЦЧШ", "ЩЪЫЬЭЮЯ"],
        "case": "upper",
    },
    {
        "file": "IMG_0176.PNG",
        "name": "cyr_lower",
        "rows": ["абвгдеёжзий", "клмнопрстуф", "хцчшщъыьэ", "юя"],
        "case": "lower",
    },
    {
        "file": "IMG_0180.PNG",
        "name": "lat_upper",
        "rows": ["ABCDEFGHIJ", "KLMNOPQ", "RSTUVWXY", "Z"],
        "case": "upper",
    },
    {
        "file": "IMG_0179.PNG",
        "name": "lat_lower",
        "rows": ["abcdefghij", "klmnopqrst", "uvwxyz"],
        "case": "lower",
    },
    {
        "file": "IMG_0178.PNG",
        "name": "digits_punct",
        # row 3 punct order: . , : ; ! ? — - · /
        "rows": ["012345", "6789", [".", ",", ":", ";", "!", "?", "—", "-", "·", "/"], ["@", "©", "€", "●"]],
        "case": "punct",
    },
]

NOISE_AREA = 80          # min pixels to keep as a component
DIACRITIC_MAX_AREA = 1500  # components below this might be diacritics
ROW_GAP_FACTOR = 0.55    # how much vertical gap (relative to median glyph height) starts a new row


def binarize(pil_img: Image.Image) -> np.ndarray:
    """Return uint8 array, 1 = ink, 0 = paper."""
    # flatten transparency onto a white canvas first
    if pil_img.mode in ("RGBA", "LA") or (pil_img.mode == "P" and "transparency" in pil_img.info):
        rgba = pil_img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[-1])
        pil_img = bg
    g = pil_img.convert("L")
    arr = np.asarray(g, dtype=np.uint8)
    # marker is dark blue/navy → low L-values; paper is bright
    hist = np.bincount(arr.flatten(), minlength=256)
    bg_peak = np.argmax(hist[200:]) + 200
    thr = max(80, bg_peak - 60)
    binary = (arr < thr).astype(np.uint8)
    # tiny morph close to fill marker holes
    binary = ndimage.binary_closing(binary, iterations=2).astype(np.uint8)
    return binary


def cc_segment(binary: np.ndarray):
    """Return list of dicts: {bbox: (y0,x0,y1,x1), area, mask}."""
    # 8-connectivity for hand-drawn marker
    structure = np.ones((3, 3), dtype=int)
    labeled, n = ndimage.label(binary, structure=structure)
    comps = []
    for i in range(1, n + 1):
        ys, xs = np.where(labeled == i)
        if len(ys) < NOISE_AREA:
            continue
        y0, y1 = int(ys.min()), int(ys.max())
        x0, x1 = int(xs.min()), int(xs.max())
        comps.append(
            {
                "bbox": (y0, x0, y1, x1),
                "cy": (y0 + y1) / 2,
                "cx": (x0 + x1) / 2,
                "h": y1 - y0,
                "w": x1 - x0,
                "area": int(len(ys)),
                "label": i,
            }
        )
    return comps, labeled


def group_diacritics(comps):
    """Merge tiny dot/check components ABOVE a larger base component into one glyph.

    Rules:
      - small comp (area < DIACRITIC_MAX_AREA) is candidate
      - sits above a larger comp with x-overlap
      - vertical gap < base height
    Returns list of glyph dicts: {bbox: union, members: [comp,...]}
    """
    comps = list(comps)
    median_h = np.median([c["h"] for c in comps])

    bases = []
    diacritics = []
    for c in comps:
        if c["area"] < DIACRITIC_MAX_AREA and c["h"] < median_h * 0.55:
            diacritics.append(c)
        else:
            bases.append(c)

    # for each diacritic find best base below
    used = set()
    glyphs = []
    for d in diacritics:
        best = None
        best_dy = 1e9
        for b in bases:
            if b["label"] in used:
                continue
            # x-overlap?
            bx0, bx1 = b["bbox"][1], b["bbox"][3]
            dx0, dx1 = d["bbox"][1], d["bbox"][3]
            overlap = min(bx1, dx1) - max(bx0, dx0)
            if overlap < min(b["w"], d["w"]) * 0.25:
                continue
            # diacritic must be above
            if d["bbox"][2] >= b["bbox"][0] - 2:  # bottom of diac above top of base
                # not above; allow some leniency
                if d["bbox"][2] > b["bbox"][0] + b["h"] * 0.3:
                    continue
            dy = b["bbox"][0] - d["bbox"][2]
            if dy < best_dy and dy < median_h * 1.0:
                best_dy = dy
                best = b
        if best is not None:
            # merge
            y0 = min(d["bbox"][0], best["bbox"][0])
            x0 = min(d["bbox"][1], best["bbox"][1])
            y1 = max(d["bbox"][2], best["bbox"][2])
            x1 = max(d["bbox"][3], best["bbox"][3])
            glyphs.append(
                {
                    "bbox": (y0, x0, y1, x1),
                    "cy": (y0 + y1) / 2,
                    "cx": (x0 + x1) / 2,
                    "members": [best, d],
                }
            )
            used.add(best["label"])
        else:
            # treat diacritic as standalone (eg. period)
            glyphs.append(
                {
                    "bbox": d["bbox"],
                    "cy": d["cy"],
                    "cx": d["cx"],
                    "members": [d],
                }
            )

    for b in bases:
        if b["label"] in used:
            continue
        glyphs.append(
            {
                "bbox": b["bbox"],
                "cy": b["cy"],
                "cx": b["cx"],
                "members": [b],
            }
        )
    return glyphs


def cluster_rows(glyphs):
    """Sort into rows by y-center, return list of rows (each row sorted by cx)."""
    if not glyphs:
        return []
    ys = sorted(g["cy"] for g in glyphs)
    heights = [g["bbox"][2] - g["bbox"][0] for g in glyphs]
    median_h = np.median(heights)

    glyphs_sorted = sorted(glyphs, key=lambda g: g["cy"])
    rows = []
    current = [glyphs_sorted[0]]
    for g in glyphs_sorted[1:]:
        gap = g["cy"] - current[-1]["cy"]
        if gap > median_h * ROW_GAP_FACTOR + median_h * 0.3:
            rows.append(sorted(current, key=lambda x: x["cx"]))
            current = [g]
        else:
            current.append(g)
    rows.append(sorted(current, key=lambda x: x["cx"]))
    return rows


def render_pgm(binary, glyph, out_path, pad=20):
    y0, x0, y1, x1 = glyph["bbox"]
    y0p = max(0, y0 - pad)
    x0p = max(0, x0 - pad)
    y1p = min(binary.shape[0], y1 + pad + 1)
    x1p = min(binary.shape[1], x1 + pad + 1)
    crop = binary[y0p:y1p, x0p:x1p].astype(np.uint8) * 255
    # potrace expects PGM with foreground = dark; we have ink=255, so invert for PGM
    inv = 255 - crop
    img = Image.fromarray(inv, mode="L")
    img.save(out_path, format="PPM")  # PGM via PPM-L


def render_png_preview(binary, glyph, out_path, pad=20):
    y0, x0, y1, x1 = glyph["bbox"]
    y0p = max(0, y0 - pad)
    x0p = max(0, x0 - pad)
    y1p = min(binary.shape[0], y1 + pad + 1)
    x1p = min(binary.shape[1], x1 + pad + 1)
    crop = binary[y0p:y1p, x0p:x1p].astype(np.uint8) * 255
    img = Image.fromarray(crop, mode="L")
    img.save(out_path)


def safe_filename(ch: str, sheet_name: str) -> str:
    # encode unicode codepoint
    return f"{sheet_name}_U{ord(ch):04X}"


def process_sheet(sheet):
    img = Image.open(SRC / sheet["file"])
    print(f"\n=== {sheet['name']} ({sheet['file']}) {img.size} ===")

    binary = binarize(img)
    print(f"  ink pixels: {binary.sum():,}")

    comps, labeled = cc_segment(binary)
    print(f"  components: {len(comps)}")

    glyphs = group_diacritics(comps)
    print(f"  glyphs after grouping: {len(glyphs)}")

    rows = cluster_rows(glyphs)
    print(f"  rows detected: {len(rows)}")
    for i, r in enumerate(rows):
        print(f"    row {i}: {len(r)} glyphs")

    # save row-overlay debug
    dbg = Image.fromarray((binary * 255).astype(np.uint8)).convert("RGB")
    draw = ImageDraw.Draw(dbg)
    palette = [(231, 76, 60), (241, 196, 15), (46, 204, 113), (52, 152, 219), (155, 89, 182), (230, 126, 34)]

    expected_rows = sheet["rows"]
    mapping = {}
    for ri, row in enumerate(rows):
        if ri >= len(expected_rows):
            print(f"  ! extra row {ri}, skipping")
            continue
        exp = expected_rows[ri]
        if isinstance(exp, str):
            exp = list(exp)
        # if too many components found, merge the closest neighbour pairs until counts match
        while len(row) > len(exp):
            best_d = float("inf")
            best_i = 0
            for i in range(len(row) - 1):
                dx = abs(row[i + 1]["cx"] - row[i]["cx"])
                dy = abs(row[i + 1]["cy"] - row[i]["cy"])
                d = dx + dy * 0.4
                if d < best_d:
                    best_d = d
                    best_i = i
            a, b = row[best_i], row[best_i + 1]
            y0 = min(a["bbox"][0], b["bbox"][0])
            x0 = min(a["bbox"][1], b["bbox"][1])
            y1 = max(a["bbox"][2], b["bbox"][2])
            x1 = max(a["bbox"][3], b["bbox"][3])
            merged = {
                "bbox": (y0, x0, y1, x1),
                "cy": (y0 + y1) / 2,
                "cx": (x0 + x1) / 2,
                "members": a.get("members", [a]) + b.get("members", [b]),
            }
            row = row[:best_i] + [merged] + row[best_i + 2:]
        n = min(len(row), len(exp))
        if len(row) != len(exp):
            print(f"  ! row {ri}: found {len(row)} glyphs, expected {len(exp)} ('{''.join(exp)}')")
        else:
            print(f"  row {ri}: matched {len(exp)} glyphs ('{''.join(exp)}')")
        for ci in range(n):
            ch = exp[ci]
            mapping[ch] = row[ci]
            color = palette[ri % len(palette)]
            y0, x0, y1, x1 = row[ci]["bbox"]
            draw.rectangle([x0, y0, x1, y1], outline=color, width=3)
            draw.text((x0, max(0, y0 - 16)), ch, fill=color)

    dbg.save(DBG_DIR / f"{sheet['name']}_segmentation.png")

    # crop & save
    for ch, g in mapping.items():
        fname = safe_filename(ch, sheet["name"])
        render_pgm(binary, g, PGM_DIR / f"{fname}.pgm")
        render_png_preview(binary, g, PNG_DIR / f"{fname}.png")
    print(f"  saved {len(mapping)} glyphs")
    return mapping


def main():
    all_glyphs = {}
    for sheet in SHEETS:
        m = process_sheet(sheet)
        for ch, g in m.items():
            if ch in all_glyphs:
                print(f"  ! duplicate char {ch}, overwriting from {sheet['name']}")
            all_glyphs[ch] = {"sheet": sheet["name"], "bbox": g["bbox"]}

    # write index
    with open(WORK / "glyphs_index.json", "w") as f:
        json.dump({ch: v for ch, v in all_glyphs.items()}, f, ensure_ascii=False, indent=2)
    print(f"\n=== TOTAL: {len(all_glyphs)} glyphs ===")
    print(f"chars: {''.join(sorted(all_glyphs.keys()))}")


if __name__ == "__main__":
    main()
