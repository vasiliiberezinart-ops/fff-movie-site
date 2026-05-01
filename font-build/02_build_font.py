#!/usr/bin/env python3
"""
Build FFF Hand TTF from per-glyph SVG files (potrace output).

Each SVG has:
  <svg viewBox="0 0 W_pt H_pt">
    <g transform="translate(0,H_pt) scale(0.1,-0.1)">
      <path d="M ... z M ... z"/>
    </g>
  </svg>

We parse the path, apply the inner transform, then rescale so the glyph
fits a target height in font em-units, with the baseline at y=0.
"""
import os, re, glob, json
import xml.etree.ElementTree as ET
from pathlib import Path
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen

WORK = Path.home() / "Desktop" / "cinema-platform" / "font-build"
SVG_DIR = WORK / "glyphs_svg"
PNG_DIR = WORK / "glyphs_png"
OUT_TTF = Path.home() / "Desktop" / "cinema-platform" / "assets" / "fonts" / "fff-hand.ttf"
OUT_TTF.parent.mkdir(parents=True, exist_ok=True)

# Font design parameters (em-square units)
EM = 1000
ASCENT = 850
DESCENT = -250
CAP_HEIGHT = 700
X_HEIGHT = 500
SIDE_BEARING = 50            # em units of space on each side of a glyph
WORD_SPACE_WIDTH = 350       # advance width of U+0020

# descender depth for letters with descenders (em units below baseline)
DESC_DEPTH = 200
# punctuation that sits low (vertical alignment from baseline)
PUNCT_LOW = 0          # period/comma sit at baseline
PUNCT_MID = 280        # dashes sit around mid x-height
PUNCT_HIGH = 0         # ! ? : ; baseline-aligned

NS = "{http://www.w3.org/2000/svg}"


def metrics_for(ch: str):
    """Return (target_height, y_offset_below_baseline)."""
    if ch.isupper() and ch.isalpha():
        return CAP_HEIGHT, 0
    if ch.islower() and ch.isalpha():
        # cyrillic descenders: р, у, ф, ц, щ, з-tail (none in our set has descender below)
        # latin descenders: g, p, q, y, j
        if ch in "руфцщ" or ch in "gpqyj":
            return CAP_HEIGHT, -DESC_DEPTH
        return X_HEIGHT, 0
    if ch.isdigit():
        return CAP_HEIGHT, 0
    if ch in ".,":
        return 140, 0
    if ch == "·":
        return 140, X_HEIGHT * 0.4
    if ch in ":;":
        return 480, 0
    if ch in "!?":
        return CAP_HEIGHT, 0
    if ch == "—":
        return 70, X_HEIGHT * 0.42
    if ch == "-":
        return 70, X_HEIGHT * 0.42
    if ch == "/":
        return CAP_HEIGHT + 100, -50
    if ch in "@©€●":
        return CAP_HEIGHT, 0
    return X_HEIGHT, 0


# tokenize SVG path: command letter OR number
_TOKEN_RE = re.compile(r"[MLCZmlcz]|-?\d+\.?\d*(?:[eE][-+]?\d+)?")


def parse_path_apply(d, pen, src_h_pt, scale, y_off):
    """Parse potrace path d; for each coord (x, y) in pt, output:
        x_em = x_pt * scale
        y_em = (src_h_pt - y_pt) * scale + y_off
    The flipped Y comes from potrace's outer scale(0.1,-0.1) translate(0,H).
    Coordinates in path are in 'inner units' = pt * 10, so include /10 in scale.
    """
    tokens = _TOKEN_RE.findall(d)
    n = len(tokens)
    i = 0
    cmd = None
    cur_x = cur_y = 0.0
    start_x = start_y = 0.0
    open_subpath = False

    def tx(x_inner, y_inner):
        # inner units = pt * 10; convert to pt then scale to em with flipped Y
        x_pt = x_inner / 10.0
        y_pt = y_inner / 10.0
        # potrace internal Y is already in original pt-space-flipped by the group transform,
        # but path coordinates pre-transform are in inner units of the unscaled path.
        # The outer <g> transform "translate(0,H) scale(0.1,-0.1)" maps inner(x,y) to pt(x*0.1, H - y*0.1).
        # So pt coords = (x_pt, src_h_pt - y_pt).
        x_pt_final = x_pt
        y_pt_final = src_h_pt - y_pt
        x_em = x_pt_final * scale
        y_em = y_pt_final * scale + y_off
        return (round(x_em), round(y_em))

    while i < n:
        t = tokens[i]
        if t in "MLCZmlcz":
            cmd = t
            i += 1
            if cmd in "Zz":
                if open_subpath:
                    pen.closePath()
                    open_subpath = False
                cur_x, cur_y = start_x, start_y
                continue
        if cmd == "M":
            x, y = float(tokens[i]), float(tokens[i + 1])
            cur_x, cur_y = x, y
            start_x, start_y = x, y
            if open_subpath:
                pen.endPath()
            pen.moveTo(tx(x, y))
            open_subpath = True
            i += 2
            cmd = "L"
        elif cmd == "m":
            x = cur_x + float(tokens[i])
            y = cur_y + float(tokens[i + 1])
            cur_x, cur_y = x, y
            start_x, start_y = x, y
            if open_subpath:
                pen.endPath()
            pen.moveTo(tx(x, y))
            open_subpath = True
            i += 2
            cmd = "l"
        elif cmd == "L":
            x, y = float(tokens[i]), float(tokens[i + 1])
            cur_x, cur_y = x, y
            pen.lineTo(tx(x, y))
            i += 2
        elif cmd == "l":
            x = cur_x + float(tokens[i])
            y = cur_y + float(tokens[i + 1])
            cur_x, cur_y = x, y
            pen.lineTo(tx(x, y))
            i += 2
        elif cmd == "C":
            x1, y1 = float(tokens[i]), float(tokens[i + 1])
            x2, y2 = float(tokens[i + 2]), float(tokens[i + 3])
            x, y = float(tokens[i + 4]), float(tokens[i + 5])
            cur_x, cur_y = x, y
            pen.curveTo(tx(x1, y1), tx(x2, y2), tx(x, y))
            i += 6
        elif cmd == "c":
            x1 = cur_x + float(tokens[i])
            y1 = cur_y + float(tokens[i + 1])
            x2 = cur_x + float(tokens[i + 2])
            y2 = cur_y + float(tokens[i + 3])
            x = cur_x + float(tokens[i + 4])
            y = cur_y + float(tokens[i + 5])
            cur_x, cur_y = x, y
            pen.curveTo(tx(x1, y1), tx(x2, y2), tx(x, y))
            i += 6
        else:
            # unknown — skip one token
            i += 1
    if open_subpath:
        pen.closePath()


def build_glyph(svg_path: Path, ch: str):
    """Return (glyph, advance_width_em)."""
    tree = ET.parse(svg_path)
    root = tree.getroot()
    vb = root.attrib["viewBox"].split()
    src_w_pt = float(vb[2])
    src_h_pt = float(vb[3])

    g = root.find(NS + "g")
    paths = g.findall(NS + "path")
    if not paths:
        return None, 0

    target_h, y_off = metrics_for(ch)
    if src_h_pt < 1:
        scale = 1.0
    else:
        scale = target_h / src_h_pt
    target_w = src_w_pt * scale
    advance = int(round(target_w + 2 * SIDE_BEARING))

    ttpen = TTGlyphPen(None)
    pen = Cu2QuPen(ttpen, max_err=1.5, reverse_direction=False)
    for p in paths:
        d = p.attrib.get("d", "")
        parse_path_apply(d, OffsetPen(pen, SIDE_BEARING), src_h_pt, scale, y_off)
    glyph = ttpen.glyph()
    return glyph, advance


class OffsetPen:
    """Wraps another pen, shifting all points by (dx, 0)."""

    def __init__(self, inner, dx):
        self.inner = inner
        self.dx = dx

    def moveTo(self, p):
        self.inner.moveTo((p[0] + self.dx, p[1]))

    def lineTo(self, p):
        self.inner.lineTo((p[0] + self.dx, p[1]))

    def curveTo(self, *pts):
        self.inner.curveTo(*[(p[0] + self.dx, p[1]) for p in pts])

    def qCurveTo(self, *pts):
        self.inner.qCurveTo(*[(p[0] + self.dx, p[1]) for p in pts])

    def closePath(self):
        self.inner.closePath()

    def endPath(self):
        self.inner.endPath()


def glyph_name_for(ch: str) -> str:
    """A unique, AGL-friendly glyph name."""
    cp = ord(ch)
    if ch.isascii() and ch.isalnum():
        return ch
    return f"uni{cp:04X}"


def main():
    # gather all svgs
    svgs = sorted(SVG_DIR.glob("*.svg"))
    print(f"found {len(svgs)} svgs")

    chars = {}  # ch -> svg path
    for svg in svgs:
        # filename pattern: {sheet}_U{cp:04X}.svg
        m = re.match(r".+_U([0-9A-F]+)$", svg.stem)
        if not m:
            print(f"skip (no codepoint): {svg.name}")
            continue
        cp = int(m.group(1), 16)
        ch = chr(cp)
        # if duplicate, prefer the cyrillic/latin upper sheets over lower
        if ch in chars:
            # keep the one with larger viewBox (better quality)
            old = chars[ch]
            old_size = old.stat().st_size
            new_size = svg.stat().st_size
            if new_size > old_size:
                chars[ch] = svg
        else:
            chars[ch] = svg
    print(f"unique chars: {len(chars)}")

    # build glyphs
    glyphs = {}
    advance_widths = {}
    glyph_order = [".notdef", "space"]

    # .notdef
    pen = TTGlyphPen(None)
    pen.moveTo((100, 0))
    pen.lineTo((600, 0))
    pen.lineTo((600, CAP_HEIGHT))
    pen.lineTo((100, CAP_HEIGHT))
    pen.closePath()
    pen.moveTo((150, 50))
    pen.lineTo((150, CAP_HEIGHT - 50))
    pen.lineTo((550, CAP_HEIGHT - 50))
    pen.lineTo((550, 50))
    pen.closePath()
    glyphs[".notdef"] = pen.glyph()
    advance_widths[".notdef"] = 700

    # space
    space_pen = TTGlyphPen(None)
    glyphs["space"] = space_pen.glyph()
    advance_widths["space"] = WORD_SPACE_WIDTH

    cmap = {0x0020: "space"}
    skipped = []
    for ch in sorted(chars.keys()):
        try:
            g, aw = build_glyph(chars[ch], ch)
            if g is None:
                skipped.append(ch)
                continue
            name = glyph_name_for(ch)
            # avoid clobbering reserved
            if name in glyphs:
                name = f"{name}_dup"
            glyphs[name] = g
            advance_widths[name] = aw
            cmap[ord(ch)] = name
            glyph_order.append(name)
        except Exception as e:
            print(f"  ERR {ch} ({ord(ch):04X}): {e}")
            skipped.append(ch)

    print(f"built {len(glyphs)} glyphs, skipped {len(skipped)}: {skipped}")

    # assemble TTF
    fb = FontBuilder(EM, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    metrics = {name: (advance_widths[name], 0) for name in glyph_order}
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=ASCENT, descent=DESCENT, lineGap=200)
    fb.setupNameTable(
        {
            "familyName": "FFF Hand",
            "styleName": "Regular",
            "uniqueFontIdentifier": "FFFHand-Regular-2026",
            "fullName": "FFF Hand",
            "version": "Version 1.000",
            "psName": "FFFHand-Regular",
        }
    )
    fb.setupOS2(
        sTypoAscender=ASCENT,
        sTypoDescender=DESCENT,
        sxHeight=X_HEIGHT,
        sCapHeight=CAP_HEIGHT,
        usWinAscent=ASCENT + 100,
        usWinDescent=-DESCENT + 100,
    )
    fb.setupPost()
    fb.font.save(str(OUT_TTF))
    print(f"\nWROTE {OUT_TTF}  ({OUT_TTF.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
