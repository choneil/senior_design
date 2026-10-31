"""Joint travel limits from collisions: how far a set of moving parts can slide along an axis before any of
their faces runs into a fixed part (endstop switches, carriage faces, frame)."""
import numpy as np, trimesh

EPS = 2e-5   # m; hits closer than this are coplanar/grazing contact at rest, not a stop

def _mesh(tri):
    return trimesh.Trimesh(vertices=tri.reshape(-1, 3), faces=np.arange(len(tri) * 3).reshape(-1, 3), process=True)

def _travel(a_mesh, b_mesh, d, reach):
    """Distance a_mesh can move along unit d before touching b_mesh (np.inf if never within reach)."""
    best = np.inf
    for src, dst, sign in ((a_mesh, b_mesh, 1), (b_mesh, a_mesh, -1)):   # A's vertices forward, B's backward
        o = src.vertices
        # only vertices whose ray can reach the other part's box
        lo, hi = dst.bounds
        lat = np.ones(len(o), bool)
        for k in range(3):
            if abs(d[k]) < 1e-9: lat &= (o[:, k] >= lo[k] - 1e-6) & (o[:, k] <= hi[k] + 1e-6)
        o = o[lat]
        if not len(o): continue
        dirs = np.tile(d * sign, (len(o), 1))
        locs, idx, _ = dst.ray.intersects_location(o, dirs, multiple_hits=True)
        if not len(locs): continue
        t = np.einsum('ij,ij->i', locs - o[idx], dirs[idx])
        t = t[(t > EPS) & (t < reach)]
        if len(t): best = min(best, t.min())
    return best

def sweep(moving, static, axis, reach, skip=()):
    """moving/static: lists of (name, triangles). Returns ((lower, lower_pair), (upper, upper_pair)) in metres
    along axis; skip: (moving_substring, static_substring) pairs that always slide together."""
    axis = np.asarray(axis, float) / np.linalg.norm(axis)
    mov = [(n, _mesh(t)) for n, t in moving]; sta = [(n, _mesh(t)) for n, t in static]
    out = []
    for sgn in (-1, 1):
        d = axis * sgn; best, pair = reach, None
        for mn, mm in mov:
            mlo, mhi = mm.bounds
            for sn, sm in sta:
                if any(a in mn and b in sn for a, b in skip): continue
                slo, shi = sm.bounds
                # skip pairs whose boxes never meet within reach of this sweep
                swept_lo = np.minimum(mlo, mlo + d * best); swept_hi = np.maximum(mhi, mhi + d * best)
                if np.any(swept_hi < slo - 1e-6) or np.any(swept_lo > shi + 1e-6): continue
                t = _travel(mm, sm, d, best)
                if t < best: best, pair = t, (mn, sn)
        out.append((sgn * best, pair))
    return out
