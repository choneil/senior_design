"""Build a URDF + per-link GLB meshes from the SolidWorks Pack and Go of the final pick-and-place assembly.

Placements come from the assembly's COMPINSTANCETREE (exact SolidWorks transforms), meshes from the
SolidWorks display tessellation. Mates aren't decoded, so link grouping and joint axes are set here from
the assembly structure and the measured rail / lead-screw geometry.
"""
import os, re, sys, json, math
import numpy as np, trimesh
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from scene import instances, long_axis
from limits import sweep

if len(sys.argv) != 3:
    sys.exit('usage: build_urdf.py "<Pack and Go>/.../Pick and Place.SLDASM" <output dir, e.g. ../URDF>')
ASM, OUT = sys.argv[1], sys.argv[2]
os.makedirs(os.path.join(OUT, 'meshes'), exist_ok=True)
I = instances(ASM)

def has(i, *names): return any(n in '/'.join(i['path']) for n in names)
def under(i, prefix): return '/'.join(i['path']).startswith(prefix)

# ---- CAD fix: the toolhead carriage rests ON the Y-rail blocks ----------------
# In the assembly the carriage plate overlaps the HGH15 blocks (their tops end up flush with the plate's top
# face). Lift the whole Toolhead Carriage subassembly until the plate's underside sits on the block tops.
_blocks = [i for i in I if under(i, 'Y-Axis-2/Linear Rail-1/HGH15CA')]
_bt = np.vstack([b['tri'].reshape(-1, 3) for b in _blocks]); BLOCK_TOP = _bt[:, 2].max()
# the carriage plate: Base-1 (printed) in older Pack and Gos, base.step-1 (imported sheet metal) in the current one
_base = next(i for i in I if under(i, 'Toolhead Carriage-1/') and re.fullmatch(r'(?i)base(\.step)?-1', i['path'][-1]))['tri']
_n = np.cross(_base[:, 1] - _base[:, 0], _base[:, 2] - _base[:, 0])
_down = _n[:, 2] < -0.99 * np.linalg.norm(_n, axis=1)            # downward-facing plate faces
_c = _base.mean(1)
_over = np.zeros(len(_base), bool)                                 # ... directly above a block
for b in _blocks:
    lo, hi = b['tri'].reshape(-1, 3).min(0), b['tri'].reshape(-1, 3).max(0)
    _over |= (_c[:, 0] > lo[0]) & (_c[:, 0] < hi[0]) & (_c[:, 1] > lo[1]) & (_c[:, 1] < hi[1]) \
             & (_c[:, 2] > lo[2]) & (_c[:, 2] <= hi[2] + 1e-6)
CARRIAGE_LIFT = BLOCK_TOP - _c[_down & _over, 2].min() if (_down & _over).any() else 0.0
for i in I:
    if under(i, 'Toolhead Carriage-1/'): i['tri'] = i['tri'] + np.array([0, 0, CARRIAGE_LIFT])
print(f'toolhead carriage lifted {CARRIAGE_LIFT*1000:.2f} mm to sit on the Y-rail blocks')

# ---- parts the Pack and Go is missing (owner's description) ------------------
# The machine stands on four 150 mm 4040 feet, one under each end of the two foundation 4040s, pushed against the
# corner brackets (220 mm between the feet of a pair), with two 600 mm 2040 rails bolted under the foundation 4040s
# in that gap, parallel to the lead screws. Built from the Pack and Go's own extrusion meshes. Assumed (not given):
# the rails stand on edge, 40 mm tall like the feet, against the feet's inner ends.
FOOT_L, RAIL_L = 0.150, 0.600       # (the Pack and Go's "2040 Extrusion 600mm" is modelled 590 mm long)
def _box(t): P = t.reshape(-1, 3); return P.min(0), P.max(0)
_found = [i for i in I if under(i, 'Foundation Frame-1/4040 Extrusion 600mm')]
_brk = [_box(i['tri']) for i in I if under(i, 'Foundation Frame-1/') and 'Corner Bracket' in i['path'][-1]]
_added, _gap = [], None
for e in _found:
    lo, hi = _box(e['tri']); k = int(np.argmax(hi - lo)); mid = (lo[k] + hi[k]) / 2
    ends = [b for b in _brk if b[0][1 - k] < hi[1 - k] and b[1][1 - k] > lo[1 - k]]      # brackets at this beam's ends
    a = max(b[1][k] for b in ends if b[1][k] < mid); z = min(b[0][k] for b in ends if b[0][k] > mid)
    _gap = (a + FOOT_L, z - FOOT_L)
    for x0 in (a, z - FOOT_L):
        P = e['tri'].reshape(-1, 3).copy()
        P[:, k] = x0 + (P[:, k] - lo[k]) * FOOT_L / (hi[k] - lo[k])   # cut to length: the profile is uniform along it
        P[:, 2] -= hi[2] - lo[2]                                       # directly under the beam
        _added.append(('4040 Extrusion 150mm', '4040 Extrusion 150mm.SLDPRT', P))
_src = next(i for i in I if under(i, 'Foundation Frame-1/X-Axis-1/2040 Extrusion 600mm'))['tri'].reshape(-1, 3)
_c = (_src.min(0) + _src.max(0)) / 2
_R = np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]])                     # quarter turn about its length: on edge
_Q = (_src - _c) @ _R.T; _Q[:, 1] *= RAIL_L / np.ptp(_Q[:, 1]); _Q -= _Q.min(0)
_ztop = min(_box(e['tri'])[0][2] for e in _found)
for x0 in (_gap[0], _gap[1] - np.ptp(_Q[:, 0])):                      # centred front to back on the frame
    _added.append(('2040 Extrusion 600mm', '2040 Extrusion 600mm.SLDPRT',
                   _Q + [x0, _c[1] - RAIL_L / 2, _ztop - np.ptp(_Q[:, 2])]))
for n, (name, file, P) in enumerate(_added, 1):
    I.append(dict(path=('Feet and Rails (added)', f'{name}-{n}'), file=file, T=np.eye(4), tri=P.reshape(-1, 3, 3)))
print(f'added {len(_added)} parts missing from the Pack and Go: feet {FOOT_L*1000:.0f} mm, '
      f'{(_gap[1] - _gap[0])*1000:.0f} mm between them, rails under the foundation in that gap')

# ---- link membership -------------------------------------------------------
ROD_PARTS = ('Threaded Rod - Cosmetic Thread', 'GT2 Pulley for Threaded Rod', '5mm-8mm Flex Coupling')
# 0816 feeder: servo arm -> advancer lever + sprocket pin -> carrier tape; the N20 gear pair pulls the cover
# tape across the spring-loaded tension lever, which tips onto the microswitch that stops the motor.
# vorspanner_rad is the fixed L-shaped gear housing.
FEEDER_LINK = {'servoarm': 'feeder_servo_arm', 'lever_servo_advancer': 'feeder_rod',
               'feeder_pin_new': 'feeder_advancer', 'tape_stripe': 'feeder_tape',
               'schaft_g12-n20_Predeterminado': 'feeder_spool_drive',
               'lever_coverswitch_pullingSpring': 'feeder_tension_lever'}
def link_of(i):
    p = i['path']
    if p[0].startswith('assembly_feeder'):
        return FEEDER_LINK.get(re.sub(r'(\.step)?-\d+$', '', p[-1]), 'base_link')
    if under(i, 'Foundation Frame-1/X-Axis-2/') and p[-1].rsplit('-', 1)[0] in ROD_PARTS: return 'leadscrew_l'
    if under(i, 'Foundation Frame-1/X-Axis-1/') and p[-1].rsplit('-', 1)[0] in ROD_PARTS: return 'leadscrew_r'
    if under(i, 'Y-Axis-2/Linear Rail-1/HGH15CA'): return 'toolhead_carriage'   # Y-rail blocks ride with the toolhead
    # Y belt: 20T GT2 on the Y motor and a 20T idler at the far end of the gantry
    if under(i, 'Y-Axis-2/') and p[-1] == 'GT2 Pulley - 20T-1': return 'y_motor_pulley'
    if under(i, 'Y-Axis-2/') and p[-1] == 'GT2 Pulley and Bearing - ID4 - 20 Teeth-1': return 'y_idler_pulley'
    if under(i, 'Y-Axis-2/'): return 'y_axis_assembly'
    if under(i, 'Toolhead Carriage-1/'):
        if p[-1] in ('Toolhead Mount-1', 'HGH15CA - Usable-1'): return 'z1_mount'
        # Z2: the printed vacuum-stepper mount (older Pack and Gos), or the sheet-metal slide plate and vac head mount
        if p[-1] in ('Toolhead Mount - Hollow Shaft Vacuum Stepper-2', 'Toolhead Carriage - Sheet Metal - Z-Axis-1',
                     'Toolhead Mount - Vac Head-1', 'HGH15CA - Usable-2', 'NEMA11 Hollow Shaft with Nozzle-1'): return 'z2_nozzle'
        if p[-1] == 'GT2 Pulley for Threaded Rod-1': return 'z_pulley'   # Z belt pulley (same size as Y's)
        return 'toolhead_carriage'
    return 'base_link'
for i in I: i['link'] = link_of(i)
# the 17T gear on the N20 shaft drives; its mate rides with the tensioner wheel (vorspanner_rad)
_gears = [i for i in I if 'Spur gear' in i['path'][-1]]
_shaft = next(i for i in I if i['link'] == 'feeder_spool_drive')['tri'].reshape(-1, 3).mean(0)
for g in _gears:
    g['link'] = 'feeder_spool_drive' if g is min(_gears, key=lambda g: np.linalg.norm(g['tri'].reshape(-1, 3).mean(0)[1:] - _shaft[1:])) else 'feeder_spool'

def pts(*names, link=None):
    sel = [i for i in I if (link is None or i['link'] == link) and any(n in '/'.join(i['path']) for n in names)]
    assert sel, names
    return np.vstack([i['tri'].reshape(-1, 3) for i in sel])
def axis_snap(a):
    k = int(np.argmax(abs(a))); v = np.zeros(3); v[k] = 1.0; return v   # rails are axis-aligned to <0.3 deg
def extent(P, a): t = P @ a; return t.min(), t.max()

# ---- base frame: centre of the machine footprint, on its lowest point, Z up --
allP = np.vstack([i['tri'].reshape(-1, 3) for i in I])
lo, hi = allP.min(0), allP.max(0)
BASE = np.array([(lo[0]+hi[0])/2, (lo[1]+hi[1])/2, lo[2]])

# ---- joints measured from geometry ------------------------------------------
LEAD = 0.008  # m per rev, X lead screws
GT2_R = 20 * 0.002 / (2 * math.pi)   # m, pitch radius of the 20T GT2 pulleys on Y and Z (40 mm per rev)
rod_l = pts('X-Axis-2/Threaded Rod'); rod_r = pts('X-Axis-1/Threaded Rod')
ax_x = axis_snap(long_axis(rod_l)[0])                       # gantry travel direction (world)
slider = pts('Existing Y-Axis Slider', link='y_axis_assembly')
s_lo, s_hi = extent(slider, ax_x); r_lo, r_hi = extent(rod_l, ax_x)
# gantry slider travels between the rod ends (nut stays on the threaded length)
nut = pts('Brass Motion Coupling', link='y_axis_assembly'); n_lo, n_hi = extent(nut, ax_x)
gantry_lim = (r_lo - n_lo, r_hi - n_hi)

rail_y = pts('Linear Rail-1/HGR15 600mm'); ax_y = axis_snap(long_axis(rail_y)[0])
blocks_y = pts('Linear Rail-1/HGH15CA', link='toolhead_carriage')
ry_lo, ry_hi = extent(rail_y, ax_y); by_lo, by_hi = extent(blocks_y, ax_y)
carriage_lim = (ry_lo - by_lo, ry_hi - by_hi)

def z_joint(rail, block):
    R = pts(rail); B = pts(block, link=None)
    a = axis_snap(long_axis(R)[0]); a = a if a[2] > 0 else -a
    rl, rh = extent(R, a); bl, bh = extent(B, a)
    return a, (rl - bl, rh - bh), B.mean(0)
ax_z1, z1_lim, z1_c = z_joint('Toolhead Carriage-1/HGR15 70mm-1', 'Toolhead Carriage-1/HGH15CA - Usable-1')
ax_z2, z2_lim, z2_c = z_joint('Toolhead Carriage-1/HGR15 70mm-2', 'Toolhead Carriage-1/HGH15CA - Usable-2')

# feeder: all pivots are normal to the feeder plate; the tape runs along the plate's long axis
FEED_PITCH = 0.004                                          # 8 mm tape, 4 mm sprocket pitch per feed
plate = pts('assembly_feeder_8mm.step-1/base.step')
ax_fp = axis_snap(np.linalg.svd(plate - plate.mean(0), full_matrices=False)[2][2])   # plate normal
tape = pts('tape_stripe', link='feeder_tape')
ax_tape = axis_snap(long_axis(tape)[0])
ax_tape = ax_tape if (tape.mean(0) - plate.mean(0)) @ ax_tape > 0 else -ax_tape   # tape exits at the pick end
# Servo (0816 firmware config.h): the horn turns about its own local Z (normal to the flat horn), the piston
# rod sits in a hole 6.5 mm from the servo axis, 90 deg = fully advanced (horn along the tape, as in the CAD),
# 15 deg = retracted. The rod/lever/pin therefore follows the hole along the tape: r * (cos(q) - 1), q = A - 90 deg.
ROD_HOLE_R = 0.0065
arm_i = next(i for i in I if i['link'] == 'feeder_servo_arm')
Ta = arm_i['T']; Lp = (arm_i['tri'].reshape(-1, 3) - Ta[:3, 3]) @ Ta[:3, :3]   # horn points in its own frame
ext = np.ptp(Lp, 0); k_n, k_w, k_l = np.argsort(ext)          # thin = horn normal, then width, then length
# hub = the widest stretch along the horn's length (round hub around the spline); the tip is the far end
bins = np.linspace(Lp[:, k_l].min(), Lp[:, k_l].max(), 25); mids = (bins[:-1] + bins[1:]) / 2
width = np.array([np.ptp(Lp[(Lp[:, k_l] >= a0) & (Lp[:, k_l] < a1), k_w]) if ((Lp[:, k_l] >= a0) & (Lp[:, k_l] < a1)).any() else 0
                  for a0, a1 in zip(bins[:-1], bins[1:])])
hub = np.zeros(3); hub[k_n] = Lp[:, k_n].mean(); hub[k_w] = (Lp[:, k_w].min() + Lp[:, k_w].max()) / 2
hub[k_l] = mids[width >= 0.95 * width.max()].mean()
tip_l = Lp[:, k_l].max() if abs(Lp[:, k_l].max() - hub[k_l]) > abs(Lp[:, k_l].min() - hub[k_l]) else Lp[:, k_l].min()
servo_c = Ta[:3, :3] @ hub + Ta[:3, 3]
ax_servo = axis_snap(Ta[:3, k_n]); ax_servo = ax_servo if ax_servo @ [0, 0, 1] >= 0 else -ax_servo   # horn local Z
horn_dir = Ta[:3, k_l] * np.sign(tip_l - hub[k_l])
horn_tip = servo_c + ROD_HOLE_R * horn_dir                  # piston rod hole
SERVO_LIM = (math.radians(0 - 90), math.radians(180 - 90))  # joint 0 = servo 90 deg (CAD pose, fully advanced)
# Piston rod: rear hole on the horn hole, front hole pinned to the sprocket-pin lever, which slides along the
# tape. Holes sit symmetric about the rod's centre, so the front hole mirrors the horn hole through it.
rod = pts('lever_servo_advancer', link='feeder_rod'); a_rod = long_axis(rod)[0]; rod_c = rod.mean(0)
rod_front = horn_tip + 2 * ((rod_c - horn_tip) @ a_rod) * a_rod
ROD_LEN = np.linalg.norm(rod_front - horn_tip)
# slider-crank: farthest the pin lever can be pulled back over the servo's 0-180 deg range
_q = np.linspace(*SERVO_LIM, 721)
_h = np.array([[ROD_HOLE_R * math.cos(q), ROD_HOLE_R * math.sin(q)] for q in _q])   # hole (along, lateral) vs CAD
_lat0 = (rod_front - servo_c) @ np.cross(ax_servo, ax_tape)
_s = _h[:, 0] + np.sqrt(ROD_LEN**2 - (_lat0 - _h[:, 1])**2) - (ROD_HOLE_R + ROD_LEN)
ADV_LIM = (float(_s.min()) - 0.0005, 0.0)
spool_c = {k: np.vstack([i['tri'].reshape(-1, 3) for i in I if i['link'] == k and 'Spur gear' in i['path'][-1]]).mean(0)
           for k in ('feeder_spool_drive', 'feeder_spool')}

# tension lever: pivots on its round boss (best circle through the lever's vertices); positive angle tips its
# nub onto the microswitch (taut cover tape), negative lets the spring pull it off (slack -> motor runs)
lev = np.unique(pts('lever_coverswitch', link='feeder_tension_lever').round(6), axis=0)
e1, e2 = ax_tape, np.cross(ax_fp, ax_tape)                  # feeder-plane coordinates
uv = np.c_[lev @ e1, lev @ e2]
best = (0, None)
for cu in np.arange(uv[:, 0].min(), uv[:, 0].max(), 0.00025):
    near = uv[np.abs(uv[:, 0] - cu) < 0.007]
    for cv in np.arange(uv[:, 1].min(), uv[:, 1].max(), 0.00025):
        r = np.hypot(near[:, 0] - cu, near[:, 1] - cv)
        for r0 in np.arange(0.0015, 0.0055, 0.00025):
            n = np.count_nonzero(np.abs(r - r0) < 0.0001)
            if n > best[0]: best = (n, (cu, cv, r0))
cu, cv, boss_r = best[1]
lever_c = e1 * cu + e2 * cv + ax_fp * (lev @ ax_fp).mean()
switch = pts('Micro Switch Button'); nub = lev[np.argmin(np.linalg.norm(lev - switch.mean(0), axis=1))]
ax_lever = ax_fp if np.cross(ax_fp, nub - lever_c) @ (switch.mean(0) - nub) > 0 else -ax_fp
LEVER_LIM = (-0.20, 0.05)                                   # rad: slack release .. switch over-travel
# N20 winds clockwise looking from the gear side toward the motor: +angle about the gear -> motor direction
n20 = pts('gm12-n20_Predeterminado')
ax_spool = ax_fp if (n20.mean(0) - spool_c['feeder_spool_drive']) @ ax_fp > 0 else -ax_fp

# ---- travel limits from collisions (endstop switches, carriage faces, frame) -------
# Each axis sweeps its moving parts against the fixed parts around them; pairs that always slide together are
# skipped. The feeder is left out of the gantry sweep: the nozzles hang below its top at rest and are raised
# before travelling over it. The toolhead's Y-rail blocks pass up through the carriage plate (faces flush with
# its top) and ride with it.
def parts(*links, skip=()): return [('/'.join(i['path']), i['tri']) for i in I
                                    if i['link'] in links and not any(s in '/'.join(i['path']) for s in skip)]
SLIDE = [('HGH15CA', 'HGR15'), ('Brass Motion Coupling', 'Threaded Rod'), ('Y-Axis Slider', '2040 Extrusion')]
LIMIT_FROM = {}
for name, mov, sta, ax, reach in [
        ('gantry (X)', ('y_axis_assembly', 'y_motor_pulley', 'y_idler_pulley', 'toolhead_carriage', 'z_pulley',
                        'z1_mount', 'z2_nozzle'),
         parts('base_link', skip=('assembly_feeder', 'Part1^')), ax_x, 0.5),
        ('carriage (Y)', ('toolhead_carriage', 'z_pulley', 'z1_mount', 'z2_nozzle'),
         parts('y_axis_assembly', 'y_motor_pulley', 'y_idler_pulley'), ax_y, 0.5),
        ('Z1', ('z1_mount',), parts('toolhead_carriage', 'z_pulley'), ax_z1, 0.15),
        ('Z2', ('z2_nozzle',), parts('toolhead_carriage', 'z_pulley'), ax_z2, 0.15)]:
    LIMIT_FROM[name] = sweep(parts(*mov), sta, ax, reach, SLIDE)
gantry_lim = tuple(v for v, _ in LIMIT_FROM['gantry (X)'])
carriage_lim = tuple(v for v, _ in LIMIT_FROM['carriage (Y)'])
# Z1 and Z2 move opposite (one drive): Z1's range keeps both blocks on their 70 mm rails (rail-end stops from
# z_joint above) and both slides clear of the carriage
_z1, _z2 = [tuple(v for v, _ in LIMIT_FROM[k]) for k in ('Z1', 'Z2')]
z1_lim = (max(_z1[0], -_z2[1], z1_lim[0], -z2_lim[1]), min(_z1[1], -_z2[0], z1_lim[1], -z2_lim[0]))
z2_lim = (-z1_lim[1], -z1_lim[0])

# ---- printed bed and board clamps (not in the Pack and Go) -------------------
# Meshes rebuilt by gcode_mesh.py from the owner's print file (EN3_Printed Clamps and Bed.gcode), in print
# coordinates (mm). The bed was printed upside down: corner stop (z 0-5), 200 x 220 mm plate with bolt holes and two
# clamp slots (z 5-10), ribs (z 10-23). In use it is flipped onto the rails: the plate's 20 mm long edges rest on the
# two rails, bolt holes over their slots, and the 180 mm rib block drops between them (220 - 2 x 20). The clamps
# lie on the plate, bolted through the slots, flat edge toward the corner stop. Assumed (not given): where the bed
# sits along the rails (centred on the nozzle's reach), which way round (corner stop toward +X and +Y of the base
# frame), and the clamps' positions in their slots (mid-slot).
PRINTED = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'printed')
BOARD_TOP = None                                           # textured top face of the test board, if any
if os.path.exists(os.path.join(PRINTED, 'Printed Bed.stl')):
    _bed = trimesh.load(os.path.join(PRINTED, 'Printed Bed.stl')).triangles      # print coordinates, mm
    _clamp = trimesh.load(os.path.join(PRINTED, 'Printed Clamp.stl')).triangles
    CLAMP_HOLE = np.array([12.17, 117.65])                     # clamp bolt hole centre (print coordinates)
    CLAMP_FLAT = _clamp[:, :, 0].max() - CLAMP_HOLE[0]         # hole centre to the clamp's flat (pushing) edge
    SLOT_X, SLOT_Y = 177.95, 171.55                            # slot along print X (at this y), slot along print Y (at this x)
    STOP = np.array([206.5, 202.9])                            # corner stop's inner corner (print X/Y)
    PLATE_TOP = 5.0                                            # print Z of the plate face that is on top in use
    # (hole position, quarter turns); mid-slot unless a test board is on the bed (below)
    CLAMPS = [((111.55, SLOT_X), 0), ((SLOT_Y, 105.45), 1)]
    PLATE_C = np.array([131.5, 117.9, 10.0])                   # plate centre in print X/Y, its in-use underside in Z
    FLIP = np.array([[0, 1, 0], [1, 0, 0], [0, 0, -1]])        # 180 deg about (1,1,0): print Y across the rails, up -> down
    _noz = pts('NEMA11 Hollow Shaft with Nozzle'); _nc = (_noz.min(0) + _noz.max(0)) / 2
    BED_AT = np.array([(_gap[0] + _gap[1]) / 2,                                  # centred between the rails
                       (_nc + ax_x * (gantry_lim[0] + gantry_lim[1]) / 2)[1],     # centred on the nozzle's X reach
                       _ztop])                                                    # plate on the rail tops
    def _place(p): return ((p.reshape(-1, 3) - PLATE_C) @ FLIP.T / 1000 + BED_AT).reshape(p.shape)   # print mm -> world m
    def _clamp_at(c, turns):
        a = turns * math.pi / 2; R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
        t = _clamp.reshape(-1, 3).copy(); t[:, :2] = (t[:, :2] - CLAMP_HOLE) @ R.T + c   # same Z as the corner stop
        return t.reshape(-1, 3, 3)
    # Test board (kicad_board.py renders its top side): face up on the plate, its origin corner (KiCad place origin,
    # bottom left) in the corner stop, the clamps slid along their slots onto its two far edges.
    BOARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'board', 'pnp_test_board')
    if os.path.exists(BOARD + '.json'):
        bm = json.load(open(BOARD + '.json')); bw, bh, bt = bm['width'], bm['height'], bm['thickness']
        # KiCad x runs from the stop along -print Y, KiCad up (-y) along -print X; the board's top faces print -Z
        lo = np.array([STOP[0] - bh, STOP[1] - bw, PLATE_TOP - bt]); hi = np.array([*STOP, PLATE_TOP])
        box = trimesh.creation.box(bounds=[lo, hi])
        I.append(dict(path=('Printed Bed (added)', 'PnP Test Board-1'), file='PnP Test Board.SLDPRT', T=np.eye(4),
                      tri=_place(box.triangles), link='base_link'))
        top = np.array([[STOP[0] - bh, STOP[1], lo[2]], [STOP[0] - bh, STOP[1] - bw, lo[2]],   # KiCad TL, TR,
                        [STOP[0], STOP[1] - bw, lo[2]], [STOP[0], STOP[1], lo[2]]])            # BR, BL
        V = _place(top[[0, 1, 2, 0, 2, 3]]).reshape(-1, 3) + [0, 0, 2e-5]                      # just above the box
        if np.cross(V[1] - V[0], V[2] - V[0])[2] < 0: V = V[[0, 2, 1, 3, 5, 4]]
        uv = {tuple(np.round(p, 9)): q for p, q in zip(_place(top).reshape(-1, 3) + [0, 0, 2e-5],
                                                       [(0, 1), (1, 1), (1, 0), (0, 0)])}
        BOARD_TOP = trimesh.Trimesh(vertices=V, faces=np.arange(6).reshape(2, 3), process=False,
                                    visual=trimesh.visual.TextureVisuals(
                                        uv=np.array([uv[tuple(np.round(p, 9))] for p in V]), image=Image.open(BOARD + '.png')))
        o = bm['origin']                                      # KiCad place origin -> print X/Y -> world
        BOARD_ORIGIN = _place(np.array([STOP[0] - (bh - o[1]), STOP[1] - o[0], lo[2]]))
        hole_a, hole_b = STOP[0] - bh - CLAMP_FLAT, STOP[1] - bw - CLAMP_FLAT
        if not (48.9 + 2.75 <= hole_a <= 174.2 - 2.75 and 40.3 + 2.75 <= hole_b <= 170.6 - 2.75):
            print('warning: the test board is too big or small for the clamp slots; clamps left mid-slot')
        else:
            CLAMPS = [((hole_a, SLOT_X), 0), ((SLOT_Y, hole_b), 1)]
        print(f'test board {bw:.0f} x {bh:.0f} x {bt} mm in the corner stop; its place origin is at '
              f'{np.round(BOARD_ORIGIN * 1000, 2)} mm (world), top face at {(V[:, 2].max()) * 1000:.2f} mm')
    I.append(dict(path=('Printed Bed (added)', 'Printed Bed-1'), file='Printed Bed.SLDPRT', T=np.eye(4),
                  tri=_place(_bed), link='base_link'))
    for n, (c, turns) in enumerate(CLAMPS, 1):
        I.append(dict(path=('Printed Bed (added)', f'Printed Clamp-{n}'), file='Printed Clamp.SLDPRT', T=np.eye(4),
                      tri=_place(_clamp_at(c, turns)), link='base_link'))
    _plate_top = _ztop + 0.005
    print(f'printed bed on the rails at {np.round(BED_AT * 1000, 1)} mm (world); the nozzle tip reaches the plate '
          f'after {(_noz[:, 2].min() - _plate_top) * 1000:.1f} mm of Z2 travel (Z2 range {-z2_lim[0] * 1000:.1f} mm)')

# belt pulleys turn about their motor shafts; centres from the pulley meshes
ax_motor = axis_snap(np.ptp(pts('Toolhead Carriage-1/NEMA 17 w Connector'), 0))   # shaft sticks out: longest extent
def bore_centre(v, axis):
    """Point on a pulley's rotation axis: least-squares circle through its bore, in the plane normal to `axis`.
    (The vertex mean is pulled ~1.5 mm off-axis by the set-screw hub, so the pulley would wobble about the shaft.)"""
    a = np.asarray(axis, float) / np.linalg.norm(axis)
    u = np.cross(a, [1, 0, 0] if abs(a[0]) < 0.9 else [0, 1, 0]); u /= np.linalg.norm(u)
    w = np.cross(a, u)
    c0 = (v.min(0) + v.max(0)) / 2
    p = np.c_[(v - c0) @ u, (v - c0) @ w]
    q = p[np.linalg.norm(p, axis=1) < 0.4 * np.linalg.norm(p, axis=1).max()]      # bore wall (5 mm on a 16 mm pulley)
    sol = np.linalg.lstsq(np.c_[2 * q, np.ones(len(q))], (q ** 2).sum(1), rcond=None)[0]
    return c0 + sol[0] * u + sol[1] * w + (((v - c0) @ a).mean()) * a


pulley_c = {k: bore_centre(np.vstack([i['tri'].reshape(-1, 3) for i in I if i['link'] == k]), ax_motor)
            for k in ('y_motor_pulley', 'y_idler_pulley', 'z_pulley')}

# link frames (world positions, axes world-aligned)
FRAME = {
    'base_link': BASE,
    'leadscrew_l': rod_l.mean(0), 'leadscrew_r': rod_r.mean(0),
    'y_axis_assembly': slider.mean(0),
    'toolhead_carriage': blocks_y.mean(0),
    'z1_mount': z1_c, 'z2_nozzle': z2_c,
    'feeder_servo_arm': servo_c, 'feeder_rod': horn_tip, 'feeder_advancer': rod_front, 'feeder_tape': tape.mean(0),
    'feeder_spool_drive': spool_c['feeder_spool_drive'], 'feeder_spool': spool_c['feeder_spool'],
    'feeder_tension_lever': lever_c, **pulley_c,
}
PARENT = {'leadscrew_l': 'base_link', 'leadscrew_r': 'base_link', 'y_axis_assembly': 'base_link',
          'toolhead_carriage': 'y_axis_assembly', 'z1_mount': 'toolhead_carriage', 'z2_nozzle': 'toolhead_carriage',
          'feeder_servo_arm': 'base_link', 'feeder_rod': 'feeder_servo_arm', 'feeder_advancer': 'base_link', 'feeder_tape': 'base_link',
          'feeder_spool_drive': 'base_link', 'feeder_spool': 'base_link', 'feeder_tension_lever': 'base_link',
          'y_motor_pulley': 'y_axis_assembly', 'y_idler_pulley': 'y_axis_assembly', 'z_pulley': 'toolhead_carriage'}

# ---- materials / density (rough: display meshes, no SolidWorks material data) ----
def feeder(i): return i['path'][0].startswith('assembly_feeder')
SHEET = ('sheet metal', 'z-axis mount', 'vac head', 'toolhead carriage - base')   # sheet-metal toolhead parts
def look(i):
    n = i['path'][-1].lower()
    if 'printed clamp' in n: return (0.49, 0.34, 0.76, 1), 1240 * 0.4      # board clamps: own colour
    if 'test board' in n: return (0.12, 0.35, 0.19, 1), 1850                 # FR4 under green solder mask
    if any(k in n for k in SHEET) or (under(i, 'Toolhead Carriage-1/') and n.startswith('base.step')):
        return (0.70, 0.73, 0.77, 1), 2700                       # assumed aluminium sheet
    if any(k in n for k in ('extrusion', 'hgr15', 'bracket')): return (0.75, 0.77, 0.80, 1), 2700
    if any(k in n for k in ('hgh15', 'threaded rod -', 'screw', 'nut', 'bearing', 'spacer', 'coupling-', 'pulley')): return (0.55, 0.57, 0.60, 1), 7850
    if 'nema' in n: return (0.18, 0.18, 0.20, 1), 3500
    if 'brass' in n: return (0.80, 0.62, 0.25, 1), 8500
    if 'endstop-' in n or 'switch' in n: return (0.85, 0.15, 0.15, 1), 1200
    if feeder(i): return (0.35, 0.55, 0.85, 1), 1240 * 0.4      # imported feeder STEP parts
    return (0.95, 0.55, 0.15, 1), 1240 * 0.4                        # printed parts, ~40% infill

# ---- part types (one entry per source part file; the viewer recolors by type) ----
def part_type(i):
    n = re.sub(r'(?i)(\.step)?\.sldprt$', '', i['file'])
    # imported STEP bodies are all named after their STEP file ("base"): outside the feeder, qualify by subassembly
    if i['file'].lower().endswith('.step.sldprt') and not feeder(i): n = f"{i['path'][0].rsplit('-', 1)[0]} - {n}"
    return n
TYPES = sorted({part_type(i) for i in I})
for i in I: i['type'] = TYPES.index(part_type(i))

# ---- export -----------------------------------------------------------------
links = {}
for i in I: links.setdefault(i['link'], []).append(i)
inertial = {}
for name, items in links.items():
    o = FRAME[name]; scene = trimesh.Scene(); m_tot = 0; com = np.zeros(3); Iacc = np.zeros((3, 3)); parts = []
    for i in items:
        tri = i['tri'] - o
        mesh = trimesh.Trimesh(vertices=tri.reshape(-1, 3), faces=np.arange(len(tri)*3).reshape(-1, 3), process=True)
        rgba, rho = look(i)
        mesh.visual = trimesh.visual.ColorVisuals(mesh, face_colors=(np.array(rgba)*255).astype(np.uint8))
        # node name "pt_<type index>#<instance>" survives three.js name sanitizing
        scene.add_geometry(mesh, geom_name='/'.join(i['path']), node_name=f"pt_{i['type']}#{len(scene.graph.nodes)}")
        v = abs(mesh.volume)
        if v > 0:
            m = v * rho; c = mesh.center_mass if mesh.is_volume else mesh.centroid
            Ic = mesh.moment_inertia * (rho if mesh.volume > 0 else -rho) if mesh.is_volume else np.zeros((3, 3))
            parts.append((m, c, Ic))
    for m, c, Ic in parts: m_tot += m; com += m * c
    com /= max(m_tot, 1e-9)
    for m, c, Ic in parts:        # parallel-axis to link COM
        d = c - com; Iacc += Ic + m * (np.dot(d, d) * np.eye(3) - np.outer(d, d))
    inertial[name] = (m_tot, com, Iacc)
    if name == 'base_link' and BOARD_TOP is not None:      # board artwork; not a "pt_" node, so the viewer keeps its texture
        tm = BOARD_TOP.copy(); tm.apply_translation(-o)
        scene.add_geometry(tm, geom_name='PnP Test Board/top', node_name='board_top')
    scene.export(os.path.join(OUT, 'meshes', f'{name}.glb'))
    print(f'{name:18} {len(items):3} parts  {sum(len(i["tri"]) for i in items):7} tris  mass {m_tot:.3f} kg')
# viewer color groups, checked in order; first keyword match wins
GROUPS = [
    ('Extrusions',               '#bfc4cc', ('extrusion',)),
    ('Leadscrews',               '#d4b04a', ('threaded rod - cosmetic', 'brass motion coupling')),
    ('Pulleys',                  '#4fb0c6', ('gt2 pulley',)),
    ('Motors',                   '#2e2e33', ('nema 17 w', 'nema11', 'gm12-n20', 'g12-n20')),
    ('Linear sliding hardware',  '#6a7a8c', ('hgr15', 'hgh15')),
    ('Bolts, nuts & OTS hardware', '#8c9199', ('screw', 'nut', 'spacer', 'corner bracket', 'flex coupling',
                                             'threaded rod bearing', 'endstop-', 'micro switch')),
    ('Sheet metal',              '#a9b3bf', SHEET),
    ('Board clamps',             '#7e57c2', ('printed clamp',)),
    ('Test board',               '#1e5a30', ('test board',)),
]
first = {}
for i in I: first.setdefault(i['type'], i)
def group(k):
    n = TYPES[k].lower()
    if n == 'endstop': n = 'endstop-'          # the switch itself, not "Endstop Mount"
    for g, col, keys in GROUPS:
        if any(key in n for key in keys): return g, col
    if feeder(first[k]): return 'Feeder', '#598cd9'
    return 'Printed / custom parts', '#f28c26'
json.dump([{'name': t, 'group': group(k)[0], 'color': group(k)[1], 'count': sum(i['type'] == k for i in I)}
           for k, t in enumerate(TYPES)], open(os.path.join(OUT, 'part_types.json'), 'w'), indent=1)

# ---- URDF -------------------------------------------------------------------
f6 = lambda v: ' '.join(f'{x:.6f}' for x in v)
def rel(c): return FRAME[c] - FRAME[PARENT[c]]
X = []
X.append('<?xml version="1.0" encoding="utf-8"?>')
X.append('<!-- Generated from the SolidWorks Pack and Go "Pick and Place - Final Configuration" by build_urdf.py. -->')
X.append('<robot name="pick_and_place_final">')
X.append('  <link name="world" />')
X.append('  <joint name="world_to_base" type="fixed">\n    <parent link="world" />\n    <child link="base_link" />\n    <origin xyz="0 0 0" rpy="0 0 0" />\n  </joint>')
for name in ['base_link', 'leadscrew_l', 'leadscrew_r', 'y_axis_assembly', 'toolhead_carriage', 'z1_mount', 'z2_nozzle',
             'feeder_servo_arm', 'feeder_rod', 'feeder_advancer', 'feeder_tape', 'feeder_spool_drive', 'feeder_spool',
             'feeder_tension_lever', 'y_motor_pulley', 'y_idler_pulley', 'z_pulley']:
    m, c, In = inertial[name]
    X.append(f'''  <link name="{name}">
    <inertial>
      <origin xyz="{f6(c)}" rpy="0 0 0" />
      <mass value="{max(m, 1e-4):.6f}" />
      <inertia ixx="{In[0,0]:.6e}" ixy="{In[0,1]:.6e}" ixz="{In[0,2]:.6e}" iyy="{In[1,1]:.6e}" iyz="{In[1,2]:.6e}" izz="{In[2,2]:.6e}" />
    </inertial>
    <visual>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="meshes/{name}.glb" />
      </geometry>
    </visual>
  </link>''')
def joint(name, typ, child, axis, lim=None, mimic=None):
    s = f'''  <joint name="{name}" type="{typ}">
    <parent link="{PARENT[child]}" />
    <child link="{child}" />
    <origin xyz="{f6(rel(child))}" rpy="0 0 0" />
    <axis xyz="{f6(axis)}" />'''
    if lim: s += f'\n    <limit lower="{lim[0]:.6f}" upper="{lim[1]:.6f}" effort="10" velocity="1" />'
    if mimic: s += f'\n    <mimic joint="{mimic[0]}" multiplier="{mimic[1]:.8f}" offset="0" />'
    return s + '\n  </joint>'
rad_per_m = 2 * math.pi / LEAD
X.append(joint('leadscrew_l_joint', 'revolute', 'leadscrew_l', ax_x, (gantry_lim[0]*rad_per_m, gantry_lim[1]*rad_per_m)))
X.append(joint('leadscrew_r_joint', 'revolute', 'leadscrew_r', ax_x, (-gantry_lim[1]*rad_per_m, -gantry_lim[0]*rad_per_m), ('leadscrew_l_joint', -1.0)))
X.append(joint('y_axis_assembly_joint', 'prismatic', 'y_axis_assembly', ax_x, gantry_lim, ('leadscrew_l_joint', 1/rad_per_m)))
X.append(joint('toolhead_carriage_joint', 'prismatic', 'toolhead_carriage', ax_y, carriage_lim))
X.append(joint('z1_joint', 'prismatic', 'z1_mount', ax_z1, z1_lim))
# Z1 and Z2 are reciprocal (one drive): Z2 moves opposite to Z1
X.append(joint('z2_joint', 'prismatic', 'z2_nozzle', ax_z2, z2_lim, ('z1_joint', -1.0)))
# feeder: servo joint = firmware angle - 90 deg. Slider-crank: the rod pivots on the horn hole
# (feeder_rod_joint) and its front hole (feeder_rod_front marker) is pinned to the sprocket-pin lever, which
# slides along the tape (feeder_advancer_joint). URDF can't close that loop, so the viewer solves the rod angle
# and lever position. The pin pushes the tape on the advance stroke (15 -> 90 deg). The cover-tape gears
# counter-rotate 1:1 (17T/17T) and are driven, like the tension lever, by the viewer's switch logic.
X.append(joint('feeder_servo_joint', 'revolute', 'feeder_servo_arm', ax_servo, SERVO_LIM))
X.append(joint('feeder_rod_joint', 'revolute', 'feeder_rod', ax_servo, (-math.pi, math.pi)))   # relative to the horn
X.append(f'''  <link name="feeder_rod_front" />
  <joint name="feeder_rod_front_fixed" type="fixed">
    <parent link="feeder_rod" />
    <child link="feeder_rod_front" />
    <origin xyz="{f6(rod_front - horn_tip)}" rpy="0 0 0" />
  </joint>''')
X.append(joint('feeder_advancer_joint', 'prismatic', 'feeder_advancer', ax_tape, ADV_LIM))
X.append(joint('feeder_tape_joint', 'prismatic', 'feeder_tape', ax_tape, (0, FEED_PITCH)))
X.append(joint('feeder_spool_drive_joint', 'continuous', 'feeder_spool_drive', ax_spool))
X.append(joint('feeder_spool_joint', 'continuous', 'feeder_spool', ax_spool, None, ('feeder_spool_drive_joint', -1.0)))
X.append(joint('feeder_tension_lever_joint', 'revolute', 'feeder_tension_lever', ax_lever, LEVER_LIM))
# belt pulleys (20T GT2, 40 mm per rev). Z: Z1 hangs on the pulley's -X side and Z2 on its +X side, so +rotation
# about +Y lifts Z1. Y: motor and idler turn together; sign assumes the carriage clamps the belt's upper run.
X.append(joint('z_pulley_joint', 'continuous', 'z_pulley', ax_motor, None, ('z1_joint', 1 / GT2_R)))
X.append(joint('y_motor_pulley_joint', 'continuous', 'y_motor_pulley', ax_motor, None, ('toolhead_carriage_joint', 1 / GT2_R)))
X.append(joint('y_idler_pulley_joint', 'continuous', 'y_idler_pulley', ax_motor, None, ('toolhead_carriage_joint', 1 / GT2_R)))
X.append('</robot>\n')
open(os.path.join(OUT, 'PickAndPlace.urdf'), 'w').write('\n'.join(X))
print('gantry (X) travel', np.round(gantry_lim, 4), 'axis', ax_x)
print('carriage (Y) travel', np.round(carriage_lim, 4), 'axis', ax_y)
print('Z1 travel', np.round(z1_lim, 4), 'Z2 travel', np.round(z2_lim, 4))
print('feeder: tape axis', ax_tape, 'servo axis', ax_servo, 'pivot', servo_c.round(4), 'horn dir', horn_dir.round(3), f'rod {ROD_LEN*1000:.1f} mm, front hole lateral {_lat0*1000:.2f} mm, lever travel {ADV_LIM[0]*1000:.2f}..0 mm')
print('tension lever: pivot', lever_c.round(4), f'boss r {boss_r*1000:.2f} mm ({best[0]} verts)', 'axis', ax_lever, 'nub', nub.round(4))
print('feeder links:', {k: [i['path'][-1] for i in I if i['link'] == k] for k in PARENT if k.startswith('feeder')})
for k, ((lo, plo), (hi, phi)) in LIMIT_FROM.items():
    print(f'{k:13} {lo*1000:8.2f} mm  ({" vs ".join(plo) if plo else "no contact within reach"})')
    print(f'{"":13} {hi*1000:8.2f} mm  ({" vs ".join(phi) if phi else "no contact within reach"})')
