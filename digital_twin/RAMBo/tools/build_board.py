#!/usr/bin/env python3
"""
Build the RAMBo v1.2 board model for the web viewer (../index.html).

Inputs are downloaded on first run into tools/.cache/ (pinned revisions):
  - UltiMachine RAMBo 1.2h Eagle board, schematic and BOM (github.com/ultimachine/RAMBo)
  - Marlin's RAMBo pin map (pins_RAMBO.h, Marlin 2.1.2.5)

Outputs (written next to index.html):
  board.json   board outline, every part with placement, BOM data, pin/net table and a 3D body spec
  top.png      top-side texture: mask, copper, ENIG pads, silkscreen
  bottom.png   bottom-side texture (seen from below)

Only Pillow is needed:  pip install pillow
Run:  python tools/build_board.py
"""
import json
import math
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
CACHE = HERE / ".cache"

RAMBO_REV = "9c2a2cd97afd27fc756de427d165edbb03857fdc"   # branch 1.2h
RAMBO_RAW = f"https://raw.githubusercontent.com/ultimachine/RAMBo/{RAMBO_REV}/board/"
MARLIN_PINS = "https://raw.githubusercontent.com/MarlinFirmware/Marlin/2.1.2.5/Marlin/src/pins/rambo/pins_RAMBO.h"

PX_PER_MM = 20          # final texture resolution
SS = 2                  # supersampling factor for anti-aliasing
BOARD_T = 1.6           # mm (pcb_specs.txt: 0.062")

COL = {
    "mask": (20, 74, 36), "copper_masked": (34, 102, 48), "pad": (214, 178, 84),
    "silk": (240, 240, 236), "hole": (18, 18, 18), "edge": (12, 50, 26),
}


# --------------------------------------------------------------------------- inputs

def fetch(url, name):
    CACHE.mkdir(exist_ok=True)
    p = CACHE / name
    if not p.exists():
        print("download", url)
        with urllib.request.urlopen(url) as r:
            p.write_bytes(r.read())
    return p


def load_inputs():
    brd = ET.parse(fetch(RAMBO_RAW + "RAMBo.brd", "RAMBo.brd")).getroot()
    sch = ET.parse(fetch(RAMBO_RAW + "RAMBo.sch", "RAMBo.sch")).getroot()
    bom = fetch(RAMBO_RAW + "RAMBoBOM.txt", "RAMBoBOM.txt").read_text("latin-1")
    pins = fetch(MARLIN_PINS, "pins_RAMBO.h").read_text("utf-8")
    return brd, sch, bom, pins


# --------------------------------------------------------------------------- geometry helpers

def parse_rot(s):
    """Eagle rotation string 'MR90' / 'SR270' / 'R45' -> (degrees, mirrored)."""
    s = s or "R0"
    m = re.match(r"(S?)(M?)R([-\d.]+)", s)
    return float(m.group(3)), bool(m.group(2))


class Xf:
    """Package-local -> board transform (mirror about local Y, then rotate, then translate)."""

    def __init__(self, x=0.0, y=0.0, rot="R0"):
        self.x, self.y = x, y
        self.deg, self.mirror = parse_rot(rot)
        a = math.radians(self.deg)
        self.c, self.s = math.cos(a), math.sin(a)

    def __call__(self, px, py):
        if self.mirror:
            px = -px
        return (self.x + px * self.c - py * self.s, self.y + px * self.s + py * self.c)


def arc_pts(x1, y1, x2, y2, curve, seg_deg=6):
    """Points along an Eagle wire with 'curve' (CCW sweep in degrees from start to end)."""
    if not curve:
        return [(x1, y1), (x2, y2)]
    th = math.radians(curve)
    dx, dy = x2 - x1, y2 - y1
    chord = math.hypot(dx, dy)
    if chord == 0:
        return [(x1, y1)]
    r = chord / (2 * math.sin(th / 2))
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    h = r * math.cos(th / 2)                       # distance midpoint -> centre (signed with r)
    cx, cy = mx - dy / chord * h, my + dx / chord * h
    a0 = math.atan2(y1 - cy, x1 - cx)
    n = max(2, int(abs(curve) / seg_deg) + 1)
    return [(cx + abs(r) * math.cos(a0 + th * i / n), cy + abs(r) * math.sin(a0 + th * i / n))
            for i in range(n + 1)]


def poly_pts(el):
    vs = el.findall("vertex")
    pts = []
    for i, v in enumerate(vs):
        w = vs[(i + 1) % len(vs)]
        seg = arc_pts(float(v.get("x")), float(v.get("y")), float(w.get("x")), float(w.get("y")),
                      float(v.get("curve", 0)))
        pts += seg[:-1]
    return pts


def rrect(dx, dy, roundness=0, n=5):
    """Rounded rectangle outline centred on the origin (Eagle SMD roundness in %)."""
    r = min(dx, dy) / 2 * roundness / 100
    if r <= 0:
        return [(-dx / 2, -dy / 2), (dx / 2, -dy / 2), (dx / 2, dy / 2), (-dx / 2, dy / 2)]
    pts = []
    for cx, cy, a0 in ((dx / 2 - r, dy / 2 - r, 0), (-dx / 2 + r, dy / 2 - r, 90),
                       (-dx / 2 + r, -dy / 2 + r, 180), (dx / 2 - r, -dy / 2 + r, 270)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def rot_pts(pts, deg, mirror=False):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    out = []
    for x, y in pts:
        if mirror:
            x = -x
        out.append((x * c - y * s, x * s + y * c))
    return out


def tht_pad_shape(pad):
    """Outline (pad-local, unrotated) of a through-hole pad, using Eagle's default restring."""
    drill = float(pad.get("drill"))
    d = float(pad.get("diameter", 0)) or drill + 2 * min(max(0.25 * drill, 0.254), 0.508)
    shape = pad.get("shape", "round")
    if shape == "square":
        return rrect(d, d)
    if shape == "octagon":
        return [(d / 2 * math.cos(math.radians(22.5 + 45 * i)) / math.cos(math.radians(22.5)),
                 d / 2 * math.sin(math.radians(22.5 + 45 * i)) / math.cos(math.radians(22.5))) for i in range(8)]
    if shape in ("long", "offset"):
        return rrect(2 * d, d, 100)
    return rrect(d, d, 100)


# --------------------------------------------------------------------------- texture painter

class Painter:
    def __init__(self, w_mm, h_mm, bottom):
        self.s = PX_PER_MM * SS
        self.w, self.h = w_mm, h_mm
        self.bottom = bottom
        self.img = Image.new("RGB", (round(w_mm * self.s), round(h_mm * self.s)), COL["mask"])
        self.d = ImageDraw.Draw(self.img)

    def p(self, x, y):
        # top: image row 0 = board top edge.  bottom: row 0 = y=0 (seen from below, texture on a down-facing plane)
        return (x * self.s, (y if self.bottom else self.h - y) * self.s)

    def poly(self, pts, col):
        if len(pts) >= 3:
            self.d.polygon([self.p(*q) for q in pts], fill=col)

    def line(self, pts, width, col):
        w = max(1, round(width * self.s))
        q = [self.p(*a) for a in pts]
        self.d.line(q, fill=col, width=w)
        for a in q:                                      # round caps / joints
            self.circle_px(a, w / 2, col)

    def circle(self, x, y, r, col, width=0):
        cx, cy = self.p(x, y)
        rr = r * self.s
        if width:
            self.d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=col, width=max(1, round(width * self.s)))
        else:
            self.d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=col)

    def circle_px(self, c, rr, col):
        self.d.ellipse([c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr], fill=col)

    def text(self, x, y, txt, size, rot, col, font_path):
        deg, mirror = parse_rot(rot)
        if self.bottom != mirror:          # text on the other side: skip
            return
        px = max(4, round(size * self.s * 1.38))       # Eagle size ~ cap height; DejaVu cap height ~0.73 em
        try:
            font = ImageFont.truetype(font_path, px) if font_path else ImageFont.load_default()
        except OSError:
            font = ImageFont.load_default()
        bbox = font.getbbox(txt)
        tw, th = bbox[2], px
        S = 2 * int(max(tw, th) + 4)
        tile = Image.new("L", (S, S), 0)
        ImageDraw.Draw(tile).text((S // 2, S // 2), txt, font=font, fill=255, anchor="ls")
        if deg:
            tile = tile.rotate(deg, center=(S // 2, S // 2))
        cx, cy = self.p(x, y)
        self.img.paste(Image.new("RGB", (S, S), col), (round(cx - S / 2), round(cy - S / 2)), tile)

    def save(self, path):
        im = self.img.resize((self.img.width // SS, self.img.height // SS), Image.LANCZOS)
        if self.bottom:
            pass
        im.save(path, optimize=True)


def find_font():
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf",
              "/Library/Fonts/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf", "DejaVuSans.ttf"):
        try:
            ImageFont.truetype(f, 10)
            return f
        except OSError:
            continue
    return None


# --------------------------------------------------------------------------- board data

COPPER = {"1": "top", "16": "bottom"}
SILK = {"21": "top", "121": "top", "22": "bottom", "122": "bottom"}


def side_of(layer, mirror):
    if layer in COPPER:
        s = COPPER[layer]
    elif layer in SILK:
        s = SILK[layer]
    else:
        return None
    if mirror:
        s = "bottom" if s == "top" else "top"
    return s


def render(brd, font):
    plain = brd.find(".//plain")
    dims = [w for w in plain.findall("wire") if w.get("layer") == "20"]
    xs = [float(w.get(k)) for w in dims for k in ("x1", "x2")]
    ys = [float(w.get(k)) for w in dims for k in ("y1", "y2")]
    W, H = max(xs) - min(xs), max(ys) - min(ys)
    assert min(xs) == 0 and min(ys) == 0, "board outline expected at origin"

    libs = {l.get("name"): {p.get("name"): p for p in l.findall("packages/package")}
            for l in brd.findall(".//libraries/library")}
    elements = brd.findall(".//elements/element")
    signals = brd.findall(".//signals/signal")

    sides = {"top": Painter(W, H, False), "bottom": Painter(W, H, True)}

    # collect copper features per side
    pours = {"top": [], "bottom": []}           # (rank, pts, isolate, net)
    copper = {"top": [], "bottom": []}          # (kind, data, net)
    pads = {"top": [], "bottom": []}            # exposed (ENIG) pads
    holes = []                                  # (x, y, r, plated)

    for sig in signals:
        net = sig.get("name")
        for w in sig.findall("wire"):
            s = side_of(w.get("layer"), False)
            if s:
                pts = arc_pts(float(w.get("x1")), float(w.get("y1")), float(w.get("x2")), float(w.get("y2")),
                              float(w.get("curve", 0)))
                copper[s].append(("line", (pts, float(w.get("width"))), net))
        for p in sig.findall("polygon"):
            s = side_of(p.get("layer"), False)
            if s:
                pours[s].append((int(p.get("rank", 1)), poly_pts(p), float(p.get("isolate", 0.3)), net))
        for v in sig.findall("via"):
            x, y, drill = float(v.get("x")), float(v.get("y")), float(v.get("drill"))
            d = float(v.get("diameter", 0)) or drill + 2 * max(0.25 * drill, 0.254)
            for s in ("top", "bottom"):
                copper[s].append(("circle", (x, y, d / 2), net))
            holes.append((x, y, drill / 2, True))

    # net of each element pad
    padnet = {}
    for sig in signals:
        for c in sig.findall("contactref"):
            padnet[(c.get("element"), c.get("pad"))] = sig.get("name")

    silk_items = {"top": [], "bottom": []}

    for e in elements:
        pkg = libs[e.get("library")][e.get("package")]
        xf = Xf(float(e.get("x")), float(e.get("y")), e.get("rot"))
        ename = e.get("name")
        for smd in pkg.findall("smd"):
            s = side_of(smd.get("layer"), xf.mirror)
            pdeg, pm = parse_rot(smd.get("rot"))
            loc = rot_pts(rrect(float(smd.get("dx")), float(smd.get("dy")), float(smd.get("roundness", 0))), pdeg)
            pts = [xf(float(smd.get("x")) + a, float(smd.get("y")) + b) for a, b in loc]
            net = padnet.get((ename, smd.get("name")))
            copper[s].append(("poly", pts, net))
            if smd.get("stop", "yes") != "no":
                pads[s].append(pts)
        for pad in pkg.findall("pad"):
            pdeg, _ = parse_rot(pad.get("rot"))
            loc = rot_pts(tht_pad_shape(pad), pdeg)
            pts = [xf(float(pad.get("x")) + a, float(pad.get("y")) + b) for a, b in loc]
            net = padnet.get((ename, pad.get("name")))
            for s in ("top", "bottom"):
                copper[s].append(("poly", pts, net))
                if pad.get("stop", "yes") != "no":
                    pads[s].append(pts)
            cx, cy = xf(float(pad.get("x")), float(pad.get("y")))
            holes.append((cx, cy, float(pad.get("drill")) / 2, True))
        for h in pkg.findall("hole"):
            cx, cy = xf(float(h.get("x")), float(h.get("y")))
            holes.append((cx, cy, float(h.get("drill")) / 2, False))
        for item in pkg:
            s = side_of(item.get("layer"), xf.mirror)
            if not s:
                continue
            target = silk_items if item.get("layer") in SILK else None
            if item.tag == "wire":
                pts = [xf(*q) for q in arc_pts(float(item.get("x1")), float(item.get("y1")),
                                               float(item.get("x2")), float(item.get("y2")),
                                               float(item.get("curve", 0)))]
                (target[s] if target else copper[s]).append(("line", (pts, float(item.get("width"))), None))
            elif item.tag == "polygon":
                pts = [xf(*q) for q in poly_pts(item)]
                (target[s] if target else copper[s]).append(("poly", pts, None))
            elif item.tag == "circle":
                cx, cy = xf(float(item.get("x")), float(item.get("y")))
                (target[s] if target else copper[s]).append(
                    ("ring", (cx, cy, float(item.get("radius")), float(item.get("width"))), None))
            elif item.tag == "rectangle":
                x1, y1, x2, y2 = (float(item.get(k)) for k in ("x1", "y1", "x2", "y2"))
                rdeg, _ = parse_rot(item.get("rot"))
                mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                loc = rot_pts(rrect(abs(x2 - x1), abs(y2 - y1)), rdeg)
                pts = [xf(mx + a, my + b) for a, b in loc]
                (target[s] if target else copper[s]).append(("poly", pts, None))

    for item in plain:
        s = side_of(item.get("layer"), False)
        if not s or item.get("layer") not in SILK:
            continue
        if item.tag == "wire":
            pts = arc_pts(float(item.get("x1")), float(item.get("y1")), float(item.get("x2")),
                          float(item.get("y2")), float(item.get("curve", 0)))
            silk_items[s].append(("line", (pts, float(item.get("width"))), None))
        elif item.tag == "circle":
            silk_items[s].append(("ring", (float(item.get("x")), float(item.get("y")),
                                           float(item.get("radius")), float(item.get("width"))), None))
        elif item.tag == "polygon":
            silk_items[s].append(("poly", poly_pts(item), None))
        elif item.tag == "text" and item.text:
            silk_items[s].append(("text", (float(item.get("x")), float(item.get("y")), item.text.strip(),
                                           float(item.get("size")), item.get("rot")), None))

    def draw(P, kind, data, col, grow=0.0):
        if kind == "line":
            P.line(data[0], data[1] + 2 * grow, col)
        elif kind == "poly":
            if grow:
                P.line(data + data[:1], 2 * grow, col)
            P.poly(data, col)
        elif kind == "circle":
            P.circle(data[0], data[1], data[2] + grow, col)
        elif kind == "ring":
            x, y, r, w = data
            if w == 0:
                P.circle(x, y, r + grow, col)
            else:
                P.circle(x, y, r + w / 2 + grow, col, width=w + 2 * grow)

    for s, P in sides.items():
        for rank, pts, iso, net in sorted(pours[s], key=lambda t: t[0]):
            P.poly(pts, COL["copper_masked"])
            # isolation: knock out foreign-net copper with clearance, then redraw it
            for kind, data, n in copper[s]:
                if n != net:
                    draw(P, kind, data, COL["mask"], grow=max(iso, 0.2))
        for kind, data, n in copper[s]:
            draw(P, kind, data, COL["copper_masked"])
        for pts in pads[s]:
            P.poly(pts, COL["pad"])
        for kind, data, n in silk_items[s]:
            if kind == "text":
                P.text(*data[:4], data[4], COL["silk"], font)
            else:
                draw(P, kind, data, COL["silk"])
        for x, y, r, plated in holes:
            if plated:
                P.circle(x, y, r + 0.12, COL["pad"])
            P.circle(x, y, r, COL["hole"])
        # board edge
        P.line([(0, 0), (W, 0), (W, H), (0, H), (0, 0)], 0.3, COL["edge"])
        P.save(OUT / f"{s}.png")
        print("wrote", OUT / f"{s}.png")

    return W, H, libs, elements, padnet


# --------------------------------------------------------------------------- parts, BOM, pins

# ATmega2560 port pin -> Arduino/Marlin pin number (Arduino Mega map + Marlin fastio_1280 extensions 70..85)
_PORTS = {
    "A": [22, 23, 24, 25, 26, 27, 28, 29], "B": [53, 52, 51, 50, 10, 11, 12, 13],
    "C": [37, 36, 35, 34, 33, 32, 31, 30], "D": [21, 20, 19, 18, 81, 82, 83, 38],
    "E": [0, 1, 78, 5, 2, 3, 79, 80], "F": [54, 55, 56, 57, 58, 59, 60, 61],
    "G": [41, 40, 39, 71, 70, 4, None, None], "H": [17, 16, 84, 6, 7, 8, 9, 85],
    "J": [15, 14, 72, 73, 75, 76, 77, 74], "K": [62, 63, 64, 65, 66, 67, 68, 69],
    "L": [49, 48, 47, 46, 45, 44, 43, 42],
}


def port_pin(net):
    m = re.fullmatch(r"P([A-L])([0-7])(?:_\w+)?", net or "")
    if not m:
        return None
    return _PORTS[m.group(1)][int(m.group(2))]


def marlin_roles(src):
    roles = {}
    for name, num in re.findall(r"#define\s+(\w+_PIN)\s+(\d+)", src):
        n = int(num)
        if name.startswith("TEMP_") and "CS" not in name:
            n += 54                                         # analog input index -> digital pin number
        roles.setdefault(n, [])
        if name not in roles[n]:
            roles[n].append(name)
    return roles


def parse_bom(text):
    rows = {}
    for line in text.splitlines()[1:]:
        f = line.split(";")
        if len(f) < 8 or not f[7].strip():
            continue
        qty = f[0].strip()
        for ref in re.split(r"[,\s]+", f[7].strip()):
            if not re.fullmatch(r"[A-Z]+\d+", ref):
                continue
            row = {"qty": qty, "value": f[1].strip(), "desc": f[4].strip().rstrip(" �"),
                   "mfr": f[5].strip(), "mpn": f[6].strip()}
            old = rows.get(ref)
            if old is None:
                rows[ref] = row
            elif old["qty"] in ("0", "") and qty not in ("0", ""):
                row["replaces"] = old["value"]                  # e.g. D1: B240A-13-F (qty 0) -> SK310A-TP fitted
                rows[ref] = row
            elif qty in ("0", "") and old["qty"] not in ("0", ""):
                old["replaces"] = row["value"]
    return rows


def pin_names(sch):
    """(part, pad) -> schematic pin name, from the schematic's device connects."""
    libs = {l.get("name"): l for l in sch.findall(".//libraries/library")}
    out = {}
    for part in sch.findall(".//parts/part"):
        lib = libs.get(part.get("library"))
        if lib is None:
            continue
        for ds in lib.findall("devicesets/deviceset"):
            if ds.get("name") != part.get("deviceset"):
                continue
            for dev in ds.findall("devices/device"):
                if dev.get("name") != part.get("device"):
                    continue
                for c in dev.findall("connects/connect"):
                    for pad in c.get("pad").split():
                        out[(part.get("name"), pad)] = c.get("pin").split("@")[0]
    return out


# Connector functions, from the board silkscreen and Marlin's pins_RAMBO.h.
DRIVERS = {"U5": "X", "U6": "Y", "U7": "Z", "U8": "E0", "U9": "E1"}
CONNECTORS = {
    "X8": ("Motors", "X MOTOR", "Stepper output of driver U5 (X). Marlin X_STEP 37 / X_DIR 48 / X_ENABLE 29."),
    "X4": ("Motors", "Y MOTOR", "Stepper output of driver U6 (Y). Marlin Y_STEP 36 / Y_DIR 49 / Y_ENABLE 28."),
    "X14": ("Motors", "Z MOTOR 1", "Stepper output of driver U7 (Z). Marlin Z_STEP 35 / Z_DIR 47 / Z_ENABLE 27."),
    "X15": ("Motors", "Z MOTOR 2", "Wired in parallel with Z MOTOR 1 (same nets, same driver U7)."),
    "X6": ("Motors", "E0 MOTOR", "Stepper output of driver U8 (E0). Marlin E0_STEP 34 / E0_DIR 43 / E0_ENABLE 26."),
    "X7": ("Motors", "E1 MOTOR", "Stepper output of driver U9 (E1). Marlin E1_STEP 33 / E1_DIR 42 / E1_ENABLE 25."),
    "X23": ("Endstops", "X-MIN", "Endstop input, Marlin X_MIN_PIN 12."),
    "X22": ("Endstops", "Y-MIN", "Endstop input, Marlin Y_MIN_PIN 11."),
    "X21": ("Endstops", "Z-MIN", "Endstop input, Marlin Z_MIN_PIN 10."),
    "X26": ("Endstops", "X-MAX", "Endstop input, Marlin X_MAX_PIN 24 (also SERVO2 on MX3)."),
    "X25": ("Endstops", "Y-MAX", "Endstop input, Marlin Y_MAX_PIN 23 (also SERVO1 on MX2)."),
    "X24": ("Endstops", "Z-MAX", "Endstop input, Marlin Z_MAX_PIN 30 / Z_MIN_PROBE_PIN."),
    "X27": ("Thermistors", "T0", "Thermistor input, Marlin TEMP_0_PIN (A0)."),
    "X28": ("Thermistors", "T1", "Thermistor input, Marlin TEMP_1_PIN (A1)."),
    "X29": ("Thermistors", "T2", "Thermistor input, Marlin TEMP_BED_PIN (A2)."),
    "X3": ("Thermistors", "T3", "Fourth thermistor input."),
    "X11": ("Heaters & fans", "Heat 0 / Fan 0 / Heat 1 / Fan 1 / Heat2-Bed",
            "Switched 12 V outputs, pairs left to right: Heat 0 (HEATER_0 pin 9), Fan 0 (FAN0 pin 8), "
            "Heat 1 (HEATER_1 pin 7), Fan 1 (FAN1 / HEATER_2 pin 6), Heat2-Bed (HEATER_BED pin 3)."),
    "X9": ("Heaters & fans", "FAN-2", "Extra fan output, Marlin FAN2_PIN 2."),
    "X33": ("Power", "Power input", "Three 12-24 V inputs: motors/logic (via F2), heaters & fans (via F3), bed (via F4)."),
    "X30": ("Power", "VMOT AUX", "Auxiliary motor-voltage output."),
    "X1": ("Power", "5V AUX OUT", "Auxiliary 5 V output."),
    "X5": ("Power", "PS-ON", "ATX power-supply on/off, Marlin PS_ON_PIN 4."),
    "JP3": ("Power", "SMPS", "Jumper for the on-board 5 V switching regulator (U3)."),
    "X2": ("Communication", "USB", "USB-B to the ATmega32U2 USB-serial bridge (U1)."),
    "X39": ("Communication", "SERIAL", "Hardware UARTs 0-3."),
    "X10": ("Communication", "I2C", "I2C (SDA/SCL)."),
    "X12": ("Communication", "SPI", "SPI bus."),
    "X18": ("Communication", "ICSP", "ATmega2560 programming header."),
    "X17": ("Communication", "ICSP1", "ATmega32U2 programming header."),
    "X16": ("Expansion", "32u2 EXT", "Spare ATmega32U2 pins (not populated)."),
    "X13": ("Expansion", "EXT-2", "Spare ATmega2560 pins (Marlin extended pins 70-85)."),
    "X40": ("Expansion", "Analog", "Spare analog inputs."),
    "X34": ("Expansion", "PWM_EXT", "PWM header (SERVO3_PIN 5 on pin 5)."),
    "X20": ("Expansion", "MX1", "Motor-extension header 1 (SERVO0_PIN 22)."),
    "X31": ("Expansion", "MX2", "Motor-extension header 2 (SERVO1_PIN 23)."),
    "X32": ("Expansion", "MX3", "Motor-extension header 3 (SERVO2_PIN 24)."),
    "X35": ("Heaters & fans", "H0", "Heat 0 output, 2-pin auxiliary header."),
    "X36": ("Heaters & fans", "F0", "Fan 0 output, 2-pin auxiliary header."),
    "X37": ("Heaters & fans", "H1", "Heat 1 output, 2-pin auxiliary header."),
    "X38": ("Heaters & fans", "H2", "Heat2-Bed output, 2-pin auxiliary header."),
    "S1": ("Controls", "RESET", "Reset button."),
}

# How this pick-and-place uses the board (from digital_twin/URDF/serial_bridge.py and the project notes).
MACHINE = {
    "X8": "Pick-and-place X axis: twin lead screws, 8 mm lead.",
    "X4": "Pick-and-place Y axis: toolhead carriage, 20T GT2 belt (40 mm/rev).",
    "X14": "Pick-and-place Z axis: Z1/Z2 belt, 20T GT2 (40 mm/rev).",
    "X7": "The project firmware drives a separate W axis from this socket; what it is wired to is unconfirmed.",
}

# 3D bodies: package -> spec. Dimensions in mm, package-local axes (long side along local X unless noted).
CHIP = {  # L, W, H
    "R0402": (1.0, 0.5, 0.35), "C0402": (1.0, 0.5, 0.5), "R0603": (1.6, 0.8, 0.45), "C0603": (1.6, 0.8, 0.8),
    "C0603-ROUND": (1.6, 0.8, 0.8), "C0805": (2.0, 1.25, 1.0), "R1206": (3.2, 1.6, 0.55),
    "C1210K": (3.2, 2.5, 1.6), "C2220K": (5.7, 5.0, 2.0), "L1812": (4.5, 3.2, 0.9), "CAY16": (3.2, 1.6, 0.5),
    "CHIP-LED0805": (2.0, 1.25, 0.8),
}
BOX = {  # (w, d, h, colour, leads) - w/d None = from package outline
    "SOD523": (1.2, 0.8, 0.6, "#1b1b1b", False), "SOD323-R": (1.7, 1.25, 0.9, "#1b1b1b", False),
    "SMA-SM": (4.3, 2.6, 2.1, "#202020", False), "DO-214AB": (6.9, 5.9, 2.3, "#202020", False),
    "SOT23-3": (2.9, 1.3, 1.0, "#1b1b1b", True), "SOT669": (4.8, 3.9, 1.1, "#1b1b1b", True),
    "QFN32TROUND": (5.0, 5.0, 0.9, "#222222", False), "MLF32": (5.0, 5.0, 0.9, "#222222", False),
    "TQFP100": (14.0, 14.0, 1.2, "#1c1c1c", True), "TSSOP24": (7.8, 4.4, 1.1, "#1c1c1c", True),
    "QSOP16": (4.9, 3.9, 1.5, "#1c1c1c", True), "SOIC127P600X170-9N": (4.9, 3.9, 1.7, "#1c1c1c", True),
    "CRYSTAL-3.2-2.5": (3.2, 2.5, 0.8, "#c8c8c8", False), "NR8040": (8.0, 8.0, 4.0, "#222222", False),
    "OMNI-BLOK": (None, None, 4.0, "#e6dcc4", False), "PN61729": (12.0, 16.3, 10.9, "#c9c9c9", False),
    "FUSE-ATO-SMD": (None, None, 2.5, "#1e1e1e", False), "B3F-31XX": (7.4, 6.2, 3.5, "#3a3a3a", False),
}
CYL = {"E3,5-8": (8.0, 11.5, "#1e1e1e"), "C12,5-5": (12.5, 20.0, "#8a9097"), "MINIMELF": (1.6, 3.5, "#c46a6a")}
HEADER = {"1X02", "1X05", "1X06", "2X03", "2X4", "2X8", "2X10"}
MOLEX = {"70543-02", "70543-03", "70543-04", "4POL254"}
# Molex Eurostyle 5.08 mm headers per the BOM: 39531-1010 vertical, 39532-1006 right angle (drawings
# SD-39531-002, SD-39532-002). Housing length along the plug axis; plug entry side.
TERMINAL = {"MSTBV10": (12.0, "top"), "MSTBA6": (12.0, "front")}
# Fitted per the BOM line but bare pads on UltiMachine's photos of the shipped board (docs/images).
# The BOM quantities agree: 1 of JP3/X35-X38 (2211S-02G), 6 of the 8 two-pin C-Grids (70543-0001).
NOT_FITTED = {"X1", "X30", "X35", "X36", "X37", "X38"}
# MX2 (X31) has no BOM line: it and MX3 (X32) are adjacent 1x5 footprints covered by the single 2x5 header
# the BOM lists under X32 (2213S-10G), as the Aux Connectors photo shows.
BOM_SHARED = {"X31": "X32"}
BOM_SHARED_NOTE = "Fitted as one 2x5 header (2213S-10G) spanning MX2 (X31) and MX3 (X32)."
NO_BODY = {"B1,27TH", "B1,27", "FIDUCIAL-1X2", "SJ", "3,0-WAVE-HOLE", "1X01", "OSHW_8X150_NOTEXT"}


def outline_bbox(pkg):
    xs, ys = [], []
    for w in pkg.findall("wire"):
        if w.get("layer") in ("21", "51", "121"):
            xs += [float(w.get("x1")), float(w.get("x2"))]
            ys += [float(w.get("y1")), float(w.get("y2"))]
    if not xs:
        for p in pkg.findall("smd") + pkg.findall("pad"):
            xs.append(float(p.get("x")))
            ys.append(float(p.get("y")))
    return min(xs), max(xs), min(ys), max(ys)


def body_spec(ref, name, pkg):
    pads = [(float(p.get("x")), float(p.get("y"))) for p in pkg.findall("pad")]
    smds = pkg.findall("smd")
    x0, x1, y0, y1 = outline_bbox(pkg)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if name in NO_BODY:
        return None
    if name in CHIP:
        L, Wd, Hh = CHIP[name]
        xs = [float(s.get("x")) for s in smds]
        ys = [float(s.get("y")) for s in smds]
        along_y = (max(ys) - min(ys)) > (max(xs) - min(xs))
        kind = "led" if name.startswith("CHIP-LED") else "chip"
        col = "#1a1a1a" if ref[0] in "R" else ("#5a5a5a" if ref[0] == "L" else "#b79f74")
        if ref.startswith("F"):
            col = "#c58b2a"
        return {"kind": kind, "cx": 0, "cy": 0, "w": Wd if along_y else L, "d": L if along_y else Wd, "h": Hh,
                "axis": "y" if along_y else "x", "color": col}
    if name in BOX:
        w, d, h, col, leads = BOX[name]
        if w is None:
            w, d = x1 - x0, y1 - y0
        else:
            cx = cy = 0.0
        if name == "PN61729":
            cx, cy = 0.0, (y0 + y1) / 2
        if name == "SOT669":
            cy = 0.3
        spec = {"kind": "box", "cx": cx, "cy": cy, "w": w, "d": d, "h": h, "color": col}
        if leads:
            ls = []
            for s in smds:
                dx, dy = float(s.get("dx")), float(s.get("dy"))
                if dx * dy > 2.0:
                    continue
                deg, _ = parse_rot(s.get("rot"))
                if deg % 180:
                    dx, dy = dy, dx
                ls.append([float(s.get("x")), float(s.get("y")), dx * 0.6, dy * 0.8])
            spec["leads"] = ls
            # dual-row packages: the body's long side runs along the lead rows
            if len({round(q[0], 1) for q in ls}) == 2 and spec["w"] > spec["d"] \
                    or len({round(q[1], 1) for q in ls}) == 2 and spec["d"] > spec["w"]:
                spec["w"], spec["d"] = spec["d"], spec["w"]
        if name == "SOT669":
            spec["tab"] = [0.0, 2.6, 4.2, 0.9]            # exposed drain tab behind the body
        if name == "FUSE-ATO-SMD":
            spec["fuse"] = "#3b6fd6"                    # 15 A ATO blade fuse (blue) lying flat, per the RAMBo BOM
            spec["marking"] = ["15", 9.0, 3.8 + 2.5]
        if name == "NR8040":
            spec["marking"] = ["330", 6.0, 4.0]
        if name == "OMNI-BLOK":
            spec["window"] = "#7a5a3a"                  # fuse element window on top
        if name == "B3F-31XX":                          # side-actuated tactile switch, plunger toward local -y
            cy = -0.45
            spec.update(cy=cy, plunger=[0.0, -4.4, 2.6, 1.6, 1.0, 1.8])
        return spec
    if name in CYL:
        d, h, col = CYL[name]
        if name == "MINIMELF":
            return {"kind": "melf", "cx": 0, "cy": 0, "d": d, "len": h, "color": col}
        px = [p[0] for p in pads]
        py = [p[1] for p in pads]
        return {"kind": "cyl", "cx": sum(px) / len(px), "cy": sum(py) / len(py), "d": d, "h": h, "color": col}
    if name in HEADER or name == "AVR_ICSP":           # plain pin headers (SERIAL included, per photos)
        xs = [p[0] for p in pads]
        ys = [p[1] for p in pads]
        return {"kind": "header", "cx": (min(xs) + max(xs)) / 2, "cy": (min(ys) + max(ys)) / 2,
                "w": max(xs) - min(xs) + 2.54, "d": max(ys) - min(ys) + 2.54, "h": 2.5, "pins": pads,
                "pin_h": 8.5, "color": "#151515"}
    if name in MOLEX:                                   # black shrouded C-Grid headers, latch slot on the -y wall
        return {"kind": "molex", "cx": cx, "cy": cy, "w": x1 - x0, "d": y1 - y0, "h": 6.3, "wall": 0.8,
                "slot": 2.2, "pins": pads, "pin_h": 6.0, "color": "#1a1a1a"}
    if name in TERMINAL:
        h, entry = TERMINAL[name]
        return {"kind": "terminal", "cx": cx, "cy": cy, "w": x1 - x0, "d": y1 - y0, "h": h, "entry": entry,
                "pins": pads, "pitch": 5.08, "color": "#1c1c1c"}
    # fallback
    return {"kind": "box", "cx": cx, "cy": cy, "w": max(x1 - x0, 0.5), "d": max(y1 - y0, 0.5), "h": 1.0,
            "color": "#303030"}


def build_parts(elements, libs, padnet, pinname, bom, roles):
    netpads = {}
    for (el, pad), net in padnet.items():
        netpads.setdefault(net, []).append((el, pad))
    parts = []
    for e in elements:
        ref = e.get("name")
        lib, pname = e.get("library"), e.get("package")
        pkg = libs[lib][pname]
        deg, mirror = parse_rot(e.get("rot"))
        b = bom.get(BOM_SHARED.get(ref, ref), {})
        pins = []
        for p in pkg.findall("smd") + pkg.findall("pad"):
            net = padnet.get((ref, p.get("name")))
            if not net:
                continue
            pn = pinname.get((ref, p.get("name")))
            ard = port_pin(net)
            if ard is None and ref == "U2" and pn:              # the ATmega2560 itself: port from the pin name
                m = re.search(r"P([A-L])([0-7])$", pn)
                ard = _PORTS[m.group(1)][int(m.group(2))] if m else None
            row = {"pad": p.get("name"), "net": net}
            if ref.startswith("U"):                             # pad position, for the package cutaway's bond wires
                row["at"] = [round(float(p.get("x")), 3), round(float(p.get("y")), 3)]
            if pn and not pn.isdigit() and pn != p.get("name"):
                row["pin"] = pn
            if net.startswith("N$") and not ref.startswith("U"):
                ends = [f"{el} {pinname.get((el, pad), pad)}" for el, pad in netpads.get(net, ())
                        if el != ref and el.startswith("U")]
                if ends:
                    row["to"] = ends
            if ard is not None:
                row["arduino"] = ard
                if roles.get(ard):
                    row["marlin"] = roles[ard]
            pins.append(row)
        pins.sort(key=lambda r: (int(r["pad"]) if r["pad"].isdigit() else 999, r["pad"]))
        # a component with no BOM line at all (R11/R13 "NP", the Z3 ESD-patch varistor) is not fitted;
        # test points, fiducials, holes and the logo have no line either but are not components
        dnp = b.get("qty") == "0" or ref in NOT_FITTED or (not b and body_spec(ref, pname, pkg) is not None)
        group, label, func = CONNECTORS.get(ref, (None, None, None))
        if group is None:
            group = {"U": "ICs", "R": "Passives", "C": "Passives", "L": "Passives", "D": "Diodes & LEDs",
                     "LED": "Diodes & LEDs", "Q": "Transistors", "F": "Power", "Y": "ICs", "Z": "Passives",
                     "RN": "Passives"}.get(re.match(r"[A-Z]+", ref).group(0), "Other")
        if ref in DRIVERS:
            func = f"A4982 stepper driver for the {DRIVERS[ref]} motor socket."
        value = e.get("value") or b.get("value", "")
        if b.get("replaces") and value == b["replaces"]:   # board file still names the part the BOM swapped out
            value = b["value"]
        if ref in BOM_SHARED or ref in BOM_SHARED.values():
            func = (func + " " if func else "") + BOM_SHARED_NOTE
        part = {"ref": ref, "value": value, "package": pname, "x": float(e.get("x")),
                "y": float(e.get("y")), "rot": deg, "mirror": mirror, "group": group}
        for k in ("desc", "mfr", "mpn"):
            if b.get(k):
                part[k] = b[k]
        if label:
            part["label"] = label
        if func:
            part["func"] = func
        if ref in MACHINE:
            part["machine"] = MACHINE[ref]
        if dnp:
            part["dnp"] = True
        if pins:
            part["pins"] = pins
        body = None if dnp else body_spec(ref, pname, pkg)
        if body:
            for k, v in list(body.items()):
                if isinstance(v, float):
                    body[k] = round(v, 4)
            part["body"] = body
        parts.append(part)
    return parts


def main():
    brd, sch, bom_txt, pins_src = load_inputs()
    font = find_font()
    if not font:
        print("warning: no TrueType font found, silkscreen text will be coarse", file=sys.stderr)
    W, H, libs, elements, padnet = render(brd, font)
    parts = build_parts(elements, libs, padnet, pin_names(sch), parse_bom(bom_txt), marlin_roles(pins_src))
    data = {
        "name": "RAMBo v1.2h", "source": f"github.com/ultimachine/RAMBo @ {RAMBO_REV[:7]} (CC BY-SA 3.0)",
        "width": round(W, 4), "height": round(H, 4), "thickness": BOARD_T, "parts": parts,
    }
    (OUT / "board.json").write_text(json.dumps(data, separators=(",", ":")))
    print("wrote", OUT / "board.json", f"({len(parts)} parts)")


if __name__ == "__main__":
    main()
