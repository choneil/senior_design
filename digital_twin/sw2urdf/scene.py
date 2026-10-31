import io, os, numpy as np
from sw import streams
import tree
from tree import load, walk, top
from asmtess import component_tess
from parts import part_mesh
def instances(asm):
    """List of dicts: path tuple, file name, world 4x4, world triangles. Hidden/suppressed and mesh-less parts skipped.
    asm: local path to the top .SLDASM of the unpacked Pack and Go."""
    S = streams(asm)
    files, models = load(io.BytesIO(S['swXmlContents/COMPINSTANCETREE'])); C = component_tess(S); top_name = models[top(models, files)[0]].get('swName')
    tree.set_root(files[models[top(models, files)[0]].get('swFileRef')].get('swPath'), asm)
    out = []
    for path, m, f, T, off, isasm in walk(files, models, top(models, files)[0]):
        if isasm or off: continue
        parents = (top_name,) + tuple(p.rsplit('-', 1)[0] for p in path[:-1])
        key = '/'.join(f'{p}@{q}' for p, q in zip(path, parents))
        tri = C.get(key)
        if tri is None or len(tri) == 0: tri = part_mesh(f, S)
        if tri is None or len(tri) == 0: continue
        W = tri.reshape(-1, 3) @ T[:3, :3].T + T[:3, 3]
        out.append(dict(path=path, file=f.get('swPath').replace('\\', '/').split('/')[-1], T=T, tri=W.reshape(-1, 3, 3)))
    return out
def long_axis(P):
    """Unit direction of the longest principal axis and extent of points P along it."""
    c = P.mean(0); u, s, vt = np.linalg.svd(P - c, full_matrices=False); a = vt[0]
    t = (P - c) @ a; return a, c, t.min(), t.max()
