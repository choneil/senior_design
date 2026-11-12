"""Render a KiCad board's top side to a texture for the URDF: solder mask, copper tracks under the mask, exposed pads
(ENIG gold), front silkscreen (lines and text), unplated holes. Writes <name>.png (board outline only, top-left =
KiCad's top-left) and <name>.json (outline in mm, thickness, KiCad's place/drill origin).

    python kicad_board.py <board>.kicad_pcb <output dir> [px per mm, default 20]
"""
import json, math, os, re, sys
from PIL import Image, ImageDraw, ImageFont

COL = {'mask': (30, 90, 48), 'track': (47, 122, 61), 'pad': (212, 178, 92), 'silk': (240, 240, 235), 'hole': (17, 17, 17)}
FONT = '/System/Library/Fonts/Supplemental/Arial.ttf'

def sexp(text):
    """Parse an s-expression into nested lists of strings."""
    out, stack = [], []
    for m in re.finditer(r'"((?:[^"\\]|\\.)*)"|([()])|([^\s()"]+)', text):
        q, br, atom = m.groups()
        if br == '(': stack.append(out); out = []
        elif br == ')': done = out; out = stack.pop(); out.append(done)
        else: out.append(q if q is not None else atom)
    return out[0]

def kids(n, tag): return [c for c in n[1:] if isinstance(c, list) and c and c[0] == tag]
def kid(n, tag): k = kids(n, tag); return k[0] if k else None
def nums(n): return [float(v) for v in n[1:] if isinstance(v, str) and re.fullmatch(r'-?[\d.]+', v)]
def layer(n): l = kid(n, 'layer'); return l[1] if l else None

def rot(lx, ly, a):
    """KiCad local -> board offset; positive angles turn counter-clockwise on screen (y down)."""
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return lx * c + ly * s, -lx * s + ly * c

def render(path, k):
    b = sexp(open(path).read())
    edge = [n for n in kids(b, 'gr_rect') if layer(n) == 'Edge.Cuts']
    x0, y0 = nums(kid(edge[0], 'start')); x1, y1 = nums(kid(edge[0], 'end'))
    W, H = x1 - x0, y1 - y0
    im = Image.new('RGB', (round(W * k), round(H * k)), COL['mask']); d = ImageDraw.Draw(im)
    P = lambda x, y: ((x - x0) * k, (y - y0) * k)
    def seg(a, c, w, col):
        d.line([P(*a), P(*c)], fill=col, width=max(1, round(w * k)))
        for q in (a, c): px, py = P(*q); r = w * k / 2; d.ellipse([px - r, py - r, px + r, py + r], fill=col)
    for s in kids(b, 'segment'):
        if layer(s) == 'F.Cu': seg(nums(kid(s, 'start')), nums(kid(s, 'end')), nums(kid(s, 'width'))[0], COL['track'])
    holes = []
    for f in kids(b, 'footprint'):
        at = nums(kid(f, 'at')); X, Y, A = at[0], at[1], (at[2] if len(at) > 2 else 0)
        for ln in kids(f, 'fp_line'):
            if layer(ln) != 'F.SilkS': continue
            a, c = nums(kid(ln, 'start')), nums(kid(ln, 'end'))
            w = nums(kid(kid(ln, 'stroke'), 'width'))[0]
            a = rot(*a, A); c = rot(*c, A)
            seg((X + a[0], Y + a[1]), (X + c[0], Y + c[1]), w, COL['silk'])
        for p in kids(f, 'pad'):
            pat = nums(kid(p, 'at')); pa = pat[2] if len(pat) > 2 else A
            ox, oy = rot(pat[0], pat[1], A); cx, cy = X + ox, Y + oy
            sw, sh = nums(kid(p, 'size'))
            if p[2] == 'np_thru_hole':
                dr = nums(kid(p, 'drill'))[0] if kid(p, 'drill') else sw; holes.append((cx, cy, dr / 2)); continue
            lays = kid(p, 'layers')[1:]
            if not any(l in ('F.Mask', '*.Mask') for l in lays): continue
            if p[3] == 'circle':
                px, py = P(cx, cy); r = sw * k / 2; d.ellipse([px - r, py - r, px + r, py + r], fill=COL['pad'])
            else:
                pts = [rot(u, v, pa) for u, v in ((-sw/2, -sh/2), (sw/2, -sh/2), (sw/2, sh/2), (-sw/2, sh/2))]
                d.polygon([P(cx + u, cy + v) for u, v in pts], fill=COL['pad'])
    for ln in kids(b, 'gr_line'):
        if layer(ln) == 'F.SilkS':
            seg(nums(kid(ln, 'start')), nums(kid(ln, 'end')), nums(kid(kid(ln, 'stroke'), 'width'))[0], COL['silk'])
    for t in kids(b, 'gr_text'):
        if layer(t) != 'F.SilkS': continue
        at = nums(kid(t, 'at')); size = nums(kid(kid(kid(t, 'effects'), 'font'), 'size'))[0]
        just = kid(kid(t, 'effects'), 'justify'); anchor = 'lm' if just and 'left' in just else 'rm' if just and 'right' in just else 'mm'
        font = ImageFont.truetype(FONT, max(6, round(size * k * 1.38)))       # KiCad size ~ cap height
        d.text(P(at[0], at[1]), t[1], fill=COL['silk'], font=font, anchor=anchor)
    for cx, cy, r in holes:
        px, py = P(cx, cy); d.ellipse([px - r * k, py - r * k, px + r * k, py + r * k], fill=COL['hole'])
    setup = kid(b, 'setup'); org = nums(kid(setup, 'aux_axis_origin')) if setup and kid(setup, 'aux_axis_origin') else [x0, y1]
    thick = nums(kid(kid(b, 'general'), 'thickness'))[0]
    return im, {'width': W, 'height': H, 'thickness': thick, 'origin': [org[0] - x0, org[1] - y0],
                'note': 'mm; x right, y down from the board top-left (KiCad); origin = KiCad place/drill origin'}

if __name__ == '__main__':
    pcb, out = sys.argv[1], sys.argv[2]; k = float(sys.argv[3]) if len(sys.argv) > 3 else 20
    name = os.path.splitext(os.path.basename(pcb))[0]
    os.makedirs(out, exist_ok=True)
    im, meta = render(pcb, k)
    im.save(os.path.join(out, name + '.png'), optimize=True)
    json.dump(meta, open(os.path.join(out, name + '.json'), 'w'), indent=1)
    print(name, im.size, meta)
