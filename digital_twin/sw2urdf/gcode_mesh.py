"""Rebuild printed parts from Cura G-code as STL meshes, one per object (;MESH: comments), in printer coordinates (mm).

Each layer's outer-wall loops are filled even-odd (the walls around holes are outer walls too) and grown by half a
line width from the nozzle path to the part surface; runs of identical layers become one prism. Support, skirt and
infill are ignored, so the result is the part's shell as printed, at layer resolution.

    python gcode_mesh.py "<file>.gcode" <output dir> [line width, default 0.4]
"""
import os, re, sys, collections
import numpy as np, trimesh
from shapely.geometry import Polygon

NUM = re.compile(r'([XYZE])(-?\d*\.?\d+)')

def outer_walls(path):
    """{object: {layer: (z_top, [loop point lists])}} from the WALL-OUTER extrusion moves."""
    x = y = z = e = 0.0; mesh = typ = None; layer = -1; cur = None
    out = collections.defaultdict(dict)
    for line in open(path):
        if line.startswith(';'):
            if line.startswith(';LAYER:'): layer = int(line[7:])
            elif line.startswith(';MESH:'): mesh = line[6:].strip()
            elif line.startswith(';TYPE:'): typ = line[6:].strip()
            else: continue
            cur = None; continue
        code = line.split(';', 1)[0]; c = code.split()
        if not c: continue
        w = dict((k, float(v)) for k, v in NUM.findall(code))
        if c[0] == 'G92': e = w.get('E', e); continue
        if c[0] not in ('G0', 'G1'): continue
        nx, ny, nz, ne = w.get('X', x), w.get('Y', y), w.get('Z', z), w.get('E', e)
        moves = 'X' in w or 'Y' in w
        if c[0] == 'G1' and moves and ne > e + 1e-6 and typ == 'WALL-OUTER' and mesh and mesh != 'NONMESH':
            if cur is None:
                cur = [(x, y)]
                out[mesh].setdefault(layer, (nz, []))[1].append(cur)
            cur.append((nx, ny))
        elif moves:
            cur = None
        x, y, z, e = nx, ny, nz, ne
    return out

def layer_shape(loops, half_width):
    g = None
    for lp in loops:
        if len(lp) < 4: continue
        p = Polygon(lp).buffer(0)
        g = p if g is None else g.symmetric_difference(p)
    return None if g is None else g.buffer(half_width, join_style=2).simplify(0.05)

def object_mesh(layers, layer_h, half_width):
    """Stack each run of identical layer outlines into one prism."""
    runs = []                                            # [shape, z_bottom, z_top]
    for k in sorted(layers):
        z_top, loops = layers[k]
        g = layer_shape(loops, half_width)
        if g is None or g.is_empty: continue
        if runs and abs(runs[-1][2] - (z_top - layer_h)) < 1e-3 and runs[-1][0].symmetric_difference(g).area < 0.5:
            runs[-1][2] = z_top
        else:
            runs.append([g, z_top - layer_h, z_top])
    parts = []
    for g, z0, z1 in runs:
        for p in getattr(g, 'geoms', [g]):
            m = trimesh.creation.extrude_polygon(p, z1 - z0); m.apply_translation([0, 0, z0]); parts.append(m)
    return trimesh.util.concatenate(parts), len(runs)

if __name__ == '__main__':
    gcode, out = sys.argv[1], sys.argv[2]
    half = float(sys.argv[3]) / 2 if len(sys.argv) > 3 else 0.2
    head = open(gcode).read(4000)
    layer_h = float(re.search(r';Layer height: *([\d.]+)', head).group(1))
    os.makedirs(out, exist_ok=True)
    for name, layers in outer_walls(gcode).items():
        m, n = object_mesh(layers, layer_h, half)
        base = re.sub(r'(?i)(\.sldprt)?\.stl', '', name)             # "Printed Clamp.SLDPRT.STL(1)" -> "Printed Clamp(1)"
        m.export(os.path.join(out, base + '.stl'))
        print(f'{base:24} {n:3} prisms {len(m.faces):6} tris  bounds {np.round(m.bounds, 1).tolist()}')
