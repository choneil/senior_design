"""
twinlib.py - shared machinery for the PnP digital twin URDF pipeline.

Conventions (established over the project):
- glbs are exported from SolidWorks in assembly-global coordinates.
- glTF is Y-up; the URDF/model world is Z-up. Native -> world is a +90deg
  rotation about X:  world = (x, -z, y)  [matrix RX90 below].
- Link visual origins map glb-native -> link frame. For a link whose frame is
  world-axis-aligned at world position p:  visual = [RX90 | -p_applied_after].
- The model's rest pose is the ORIGINAL export session. Later exports may be
  parked elsewhere; anchor them by registering the carriage glb to
  Toolhead_Carriage.STL (link coords) or by a measured park delta.

Requires: numpy, scipy, pygltflib
"""
import math
import struct

import numpy as np
from pygltflib import GLTF2
from scipy.spatial import cKDTree

RX90 = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float)


# ---------------------------------------------------------------- glb / stl
def load_glb_points(path):
    """All mesh vertices of a glb, in its native (glTF) coordinates."""
    g = GLTF2().load(path)
    parent = {}
    for i, n in enumerate(g.nodes):
        for c in (n.children or []):
            parent[c] = i

    def nm(n):
        if n.matrix:
            return np.array(n.matrix, float).reshape(4, 4).T
        M = np.eye(4)
        if n.translation:
            M[:3, 3] = n.translation
        if n.rotation:
            x, y, z, w = n.rotation
            M[:3, :3] = np.array([
                [1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
        if n.scale:
            M[:3, :3] = M[:3, :3] @ np.diag(n.scale)
        return M

    def world(i):
        M = nm(g.nodes[i])
        while i in parent:
            i = parent[i]
            M = nm(g.nodes[i]) @ M
        return M

    out = []
    for i, n in enumerate(g.nodes):
        if n.mesh is None:
            continue
        W = world(i)
        for prim in g.meshes[n.mesh].primitives:
            acc = g.accessors[prim.attributes.POSITION]
            bv = g.bufferViews[acc.bufferView]
            buf = g.buffers[bv.buffer]
            blob = g.get_data_from_buffer_uri(buf.uri) if buf.uri else g.binary_blob()
            off = (bv.byteOffset or 0) + (acc.byteOffset or 0)
            arr = np.frombuffer(blob, dtype=np.float32, count=acc.count * 3,
                                offset=off).reshape(acc.count, 3)
            out.append((W @ np.c_[arr, np.ones(len(arr))].T).T[:, :3])
    return np.vstack(out)


def load_stl_points(path):
    """Unique vertices of a binary STL."""
    data = open(path, 'rb').read()
    n = struct.unpack('<I', data[80:84])[0]
    tris = np.frombuffer(data, dtype=np.uint8, count=n * 50, offset=84).reshape(n, 50)
    v = tris[:, 12:48].copy().view('<f4').reshape(n, 3, 3).reshape(-1, 3).astype(np.float64)
    key = np.round(v * 1e6).astype(np.int64)
    _, i = np.unique(key, axis=0, return_index=True)
    return v[i]


# ---------------------------------------------------------------- rotations
def rpy_to_R(r, p, y):
    cr, sr = math.cos(r), math.sin(r)
    cp, sp = math.cos(p), math.sin(p)
    cy, sy = math.cos(y), math.sin(y)
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return Rz @ Ry @ Rx


def R_to_rpy(R):
    p = math.atan2(-R[2, 0], math.hypot(R[0, 0], R[1, 0]))
    if abs(math.cos(p)) < 1e-9:
        y = 0.0
        r = math.atan2(R[0, 1], R[1, 1]) * (1 if p > 0 else -1)
    else:
        y = math.atan2(R[1, 0], R[0, 0])
        r = math.atan2(R[2, 1], R[2, 2])
    return r, p, y


def T_of(xyz, rpy):
    M = np.eye(4)
    M[:3, :3] = rpy_to_R(*rpy)
    M[:3, 3] = xyz
    return M


def fmt(v):
    return " ".join(f"{x:.9g}" for x in np.asarray(v).ravel())


# ---------------------------------------------------------------- URDF
class Urdf:
    def __init__(self, path):
        import xml.etree.ElementTree as ET
        self.ET = ET
        self.path = path
        self.tree = ET.parse(path)
        self.root = self.tree.getroot()
        self.reindex()

    def reindex(self):
        self.links = {l.get('name'): l for l in self.root.findall('link')}
        self.joints = {j.get('name'): j for j in self.root.findall('joint')}
        self._parent_of = {}
        for j in self.root.findall('joint'):
            o = j.find('origin')
            xyz = [float(v) for v in o.get('xyz').split()]
            rpy = [float(v) for v in o.get('rpy').split()]
            self._parent_of[j.find('child').get('link')] = (
                j.find('parent').get('link'), T_of(xyz, rpy))
        self._memo = {}

    def world_T(self, link):
        """Rest-pose world transform of a link (joints at zero)."""
        if link in self._memo:
            return self._memo[link]
        if link not in self._parent_of:
            M = np.eye(4)
        else:
            p, Tj = self._parent_of[link]
            M = self.world_T(p) @ Tj
        self._memo[link] = M
        return M

    def set_joint_origin(self, joint, T):
        o = self.joints[joint].find('origin')
        o.set('xyz', fmt(T[:3, 3]))
        o.set('rpy', fmt(R_to_rpy(T[:3, :3])))

    def set_visual_origin(self, link, T):
        o = self.links[link].find('visual').find('origin')
        o.set('xyz', fmt(T[:3, 3]))
        o.set('rpy', fmt(R_to_rpy(T[:3, :3])))

    def save(self, path=None):
        self.ET.indent(self.tree, space='  ')
        self.tree.write(path or self.path, xml_declaration=True, encoding='utf-8')


# ---------------------------------------------------------------- fits
def fit_vertical_circle(P):
    """Circle fit in the native x-z plane (axis = native y / world Z).
    Returns (center_xyz_native, fit_radius)."""
    xz = P[:, [0, 2]]
    A = np.c_[2 * xz, np.ones(len(xz))]
    b = (xz ** 2).sum(axis=1)
    (cx, cz, c0), *_ = np.linalg.lstsq(A, b, rcond=None)
    return np.array([cx, P[:, 1].mean(), cz]), math.sqrt(max(c0 + cx*cx + cz*cz, 0))


def fit_axis_line(P, r_max=0.0055, r_std_max=0.002, bin_mm=4.0):
    """Per-height circle fits keeping slender clean sections; line fit through
    their centers. Returns (point_native, dir_native, n_sections)."""
    h = P[:, 1]
    bins = np.arange(h.min(), h.max() + bin_mm/1000, bin_mm/1000)
    idx = np.digitize(h, bins)
    cs = []
    for i in range(1, len(bins)):
        m = idx == i
        if m.sum() < 40:
            continue
        xz = P[m][:, [0, 2]]
        A = np.c_[2 * xz, np.ones(len(xz))]
        b = (xz ** 2).sum(axis=1)
        (cx, cz, c0), *_ = np.linalg.lstsq(A, b, rcond=None)
        R = math.sqrt(max(c0 + cx*cx + cz*cz, 0))
        r = np.sqrt((xz[:, 0]-cx)**2 + (xz[:, 1]-cz)**2)
        if R < r_max and r.std() < r_std_max:
            cs.append((bins[i-1] + bin_mm/2000, cx, cz))
    cs = np.array(cs)
    if len(cs) < 2:
        raise RuntimeError(f"only {len(cs)} clean sections; relax r_max/r_std_max")
    kx, bx = np.polyfit(cs[:, 0], cs[:, 1], 1)
    kz, bz = np.polyfit(cs[:, 0], cs[:, 2], 1)
    y0 = cs[:, 0].mean()
    p = np.array([kx*y0 + bx, y0, kz*y0 + bz])
    d = np.array([kx, 1.0, kz])
    return p, d / np.linalg.norm(d), len(cs)


def count_teeth(P, axis_native):
    """Tooth count via angular FFT of the tooth band. Tessellation makes the
    2nd harmonic dominate: if the top frequency is even and its half is also a
    strong candidate, teeth = top/2."""
    ax = np.asarray(axis_native, float)
    ax /= np.linalg.norm(ax)
    c = P.mean(0)
    X = P - c
    tmp = np.array([0, 0, 1.0]) if abs(ax[2]) < 0.9 else np.array([1.0, 0, 0])
    u = np.cross(tmp, ax); u /= np.linalg.norm(u)
    v = np.cross(ax, u)
    Q = np.c_[X @ u, X @ v]
    A = np.c_[2*Q, np.ones(len(Q))]
    b = (Q**2).sum(axis=1)
    (cu, cv, _), *_ = np.linalg.lstsq(A, b, rcond=None)
    Q0 = Q - [cu, cv]
    r = np.sqrt((Q0**2).sum(axis=1)) * 1000
    th = np.arctan2(Q0[:, 1], Q0[:, 0])
    flange = np.percentile(r, 99.5)
    hist, edges = np.histogram(r[(r < flange-0.6) & (r > flange-4)], bins=60)
    tooth_r = edges[np.argmax(hist)]
    band = (r > tooth_r-0.35) & (r < tooth_r+0.35)
    dens, _ = np.histogram(th[band], bins=720, range=(-np.pi, np.pi))
    F = np.abs(np.fft.rfft(dens - dens.mean()))
    k = int(np.argmax(F[5:120]) + 5)
    if k % 2 == 0 and F[k//2] > 0.3 * F[k]:
        k = k // 2
    return k, tooth_r * 2  # teeth, tooth OD mm


# ---------------------------------------------------------------- registration
def register(src_pts, tgt_pts, trim=0.6, iters=40, init_R=None, init_t=None,
             allow_pca_init=True, seed=0):
    """Trimmed ICP src->tgt. Returns (R, t, trimmed_rms_m, median_m).
    Pass init_R=np.eye(3) to forbid the symmetric-flip failure mode."""
    tree = cKDTree(tgt_pts)
    rng = np.random.default_rng(seed)
    src = src_pts[rng.choice(len(src_pts), min(9000, len(src_pts)), replace=False)]

    if init_R is not None:
        R = init_R.copy()
        t = init_t if init_t is not None else tgt_pts.mean(0) - R @ src_pts.mean(0)
    elif allow_pca_init:
        def pca(P):
            c = P.mean(0); X = P - c
            w, V = np.linalg.eigh(X.T @ X / len(X))
            V = V[:, np.argsort(w)[::-1]]
            if np.linalg.det(V) < 0:
                V[:, 2] *= -1
            return c, V
        c_t, V_t = pca(tgt_pts); c_s, V_s = pca(src_pts)
        best = None
        for F in [np.diag(d) for d in [(1,1,1),(1,-1,-1),(-1,1,-1),(-1,-1,1)]]:
            R0 = V_t @ F @ V_s.T
            t0 = c_t - R0 @ c_s
            d, _ = tree.query((R0 @ src[:4000].T).T + t0)
            rms = np.sqrt((np.sort(d)[:int(trim*len(d))]**2).mean())
            if best is None or rms < best[0]:
                best = (rms, R0, t0)
        R, t = best[1], best[2]
    else:
        R = np.eye(3); t = tgt_pts.mean(0) - src_pts.mean(0)

    for _ in range(iters):
        P = (R @ src.T).T + t
        d, j = tree.query(P)
        keep = d < np.percentile(d, trim * 100)
        A = src[keep]; B = tgt_pts[j[keep]]
        ca = A.mean(0); cb = B.mean(0)
        H = (A - ca).T @ (B - cb)
        U, S, Vt = np.linalg.svd(H)
        Rn = Vt.T @ U.T
        if np.linalg.det(Rn) < 0:
            Vt[-1] *= -1
            Rn = Vt.T @ U.T
        R, t = Rn, cb - Rn @ ca
    P = (R @ src.T).T + t
    d, _ = tree.query(P)
    rms = np.sqrt((np.sort(d)[:int(trim*len(d))]**2).mean())
    return R, t, rms, float(np.median(d))
