#!/usr/bin/env python3
"""
twin.py - CLI for routine PnP digital-twin URDF edits. Run from the URDF folder.

  python tools/twin.py shift-joint  E_Nut_32T_Joint --world 0,-4.02,0
      Move a joint (and its mesh, which rides it) by a world-frame mm vector.
      Multiple joints: comma-separate names.

  python tools/twin.py set-limit    Z_Mount_Prismatic 0 0.029
      Set a joint's lower/upper limits (meters or radians).

  python tools/twin.py set-mimic    E_Nut_32T_Joint -0.59375
      Set (or flip the sign of) a mimic multiplier.

  python tools/twin.py flip-axis    E_Plunger_Joint
      Negate a joint's axis vector (direction flips).

  python tools/twin.py fit-axis     meshes/Extruder/Threaded_Rod_and_Coupling.glb
      Report a part's axis line + centers (native + world-mapped).

  python tools/twin.py teeth        meshes/motor_pulley_x.glb
      Count gear/pulley teeth and tooth OD.

  python tools/twin.py place-part   meshes/Extruder/NEMA.glb New_Link Parent_Link \\
        [--anchor meshes/toolhead_carriage.glb --stl meshes/Toolhead_Carriage.STL]
      Add a fixed link+visual for a glb. If the glb's session differs from the
      model rest pose, pass --anchor/--stl: the anchor glb (same session) is
      registered to the STL (link coords) to recover the session transform.

  python tools/twin.py validate
      Recompute link tree, report joint limits, mimic chains, missing meshes.

All edits back up the URDF to <name>.urdf.bak first.
"""
import argparse
import math
import os
import shutil
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twinlib import (RX90, Urdf, T_of, fmt, R_to_rpy, load_glb_points,
                     load_stl_points, fit_vertical_circle, fit_axis_line,
                     count_teeth, register)

URDF_DEFAULT = r"C:\Users\Comuter\urdf_starter\Assem1.urdf"

def cmd_set_mesh_path(args):
    u = open_urdf(args)
    n = 0
    for L in u.root.findall('link'):
        for vis in L.findall('visual'):
            mesh = vis.find('geometry/mesh')
            if mesh is None:
                continue
            f = mesh.get('filename')
            new = f.replace(args.old, args.new)
            if new != f:
                mesh.set('filename', new)
                n += 1
    print(f"rewrote {n} mesh path(s): {args.old!r} -> {args.new!r}")
    u.save()

def open_urdf(args):
    path = args.urdf
    if not os.path.exists(path):
        sys.exit(f"URDF not found: {path} (run from the URDF folder or pass --urdf)")
    shutil.copy(path, path + ".bak")
    return Urdf(path)


def cmd_shift_joint(args):
    u = open_urdf(args)
    D = np.array([float(v) for v in args.world.split(",")]) / 1000.0
    for name in args.joint.split(","):
        J = u.joints.get(name) or sys.exit(f"no joint {name}")
        parent = J.find('parent').get('link')
        Rp = u.world_T(parent)[:3, :3]
        o = J.find('origin')
        xyz = np.array([float(v) for v in o.get('xyz').split()]) + Rp.T @ D
        o.set('xyz', fmt(xyz))
        print(f"{name}: shifted {args.world} mm (world)")
    u.save()


def cmd_set_limit(args):
    u = open_urdf(args)
    J = u.joints.get(args.joint) or sys.exit(f"no joint {args.joint}")
    lim = J.find('limit')
    if lim is None:
        import xml.etree.ElementTree as ET
        lim = ET.SubElement(J, 'limit')
        lim.set('effort', '10'); lim.set('velocity', '1')
    lim.set('lower', str(args.lower)); lim.set('upper', str(args.upper))
    print(f"{args.joint}: limits {args.lower} .. {args.upper}")
    u.save()


def cmd_set_mimic(args):
    u = open_urdf(args)
    J = u.joints.get(args.joint) or sys.exit(f"no joint {args.joint}")
    m = J.find('mimic') or sys.exit(f"{args.joint} has no mimic")
    m.set('multiplier', str(args.multiplier))
    print(f"{args.joint}: mimic multiplier -> {args.multiplier}")
    u.save()


def cmd_flip_axis(args):
    u = open_urdf(args)
    J = u.joints.get(args.joint) or sys.exit(f"no joint {args.joint}")
    ax = np.array([float(v) for v in J.find('axis').get('xyz').split()])
    J.find('axis').set('xyz', fmt(-ax))
    print(f"{args.joint}: axis -> {fmt(-ax)}")
    u.save()

def cmd_set_axis(args):
    u = open_urdf(args)
    J = u.joints.get(args.joint) or sys.exit(f"no joint {args.joint}")
    J.find('axis').set('xyz', args.xyz.replace(",", " "))
    print(f"{args.joint}: axis -> {args.xyz}")
    u.save()

def cmd_fit_axis(args):
    P = load_glb_points(args.glb)
    c, r = fit_vertical_circle(P)
    print(f"vertical circle fit: center native {np.round(c,5)}  r {r*1000:.2f} mm")
    try:
        p, d, n = fit_axis_line(P)
        print(f"slender-section line ({n} sections): point {np.round(p,5)} dir {np.round(d,5)}")
        print(f"  world-mapped: point {np.round(RX90@p,5)} dir {np.round(RX90@d,5)}")
    except RuntimeError as e:
        print(f"line fit: {e}")


def cmd_teeth(args):
    P = load_glb_points(args.glb)
    # try native-y axis first (vertical parts), fall back to PCA odd-one-out
    for ax in ([0, 1, 0], [1, 0, 0], [0, 0, 1]):
        try:
            k, od = count_teeth(P, ax)
            print(f"axis {ax}: {k} teeth, tooth OD {od:.2f} mm "
                  f"(GT2 lead if belt pulley: {k*2} mm/rev)")
        except Exception:
            pass


def cmd_place_part(args):
    u = open_urdf(args)
    P = load_glb_points(args.glb)
    parent = args.parent
    Tp = u.world_T(parent)

    if args.anchor and args.stl:
        anchor = load_glb_points(args.anchor)
        stl = load_stl_points(args.stl)
        R, t, rms, med = register(anchor, stl, trim=0.6)
        print(f"anchor registration: trimmed RMS {rms*1000:.3f} mm, median {med*1000:.3f} mm")
        if rms > 0.0015:
            sys.exit("registration too poor - wrong anchor/session?")
        # anchor registers to Toolhead_Carriage link coords; map to world through it
        T_reg = np.eye(4); T_reg[:3, :3] = R; T_reg[:3, 3] = t
        T_map = u.world_T("Toolhead_Carriage") @ T_reg
    else:
        T_map = np.eye(4); T_map[:3, :3] = RX90   # original-session global frame

    p_native = P.mean(axis=0)
    Tw = np.eye(4); Tw[:3, 3] = (T_map @ np.array([*p_native, 1]))[:3]
    import xml.etree.ElementTree as ET
    l = ET.SubElement(u.root, 'link'); l.set('name', args.link)
    v = ET.SubElement(l, 'visual')
    o = ET.SubElement(v, 'origin')
    Tv = np.linalg.inv(Tw) @ T_map
    o.set('xyz', fmt(Tv[:3, 3])); o.set('rpy', fmt(R_to_rpy(Tv[:3, :3])))
    g = ET.SubElement(v, 'geometry')
    m = ET.SubElement(g, 'mesh'); m.set('filename', args.glb.replace('\\', '/'))
    j = ET.SubElement(u.root, 'joint'); j.set('name', f'{args.link}_Joint'); j.set('type', 'fixed')
    o = ET.SubElement(j, 'origin')
    Tj = np.linalg.inv(Tp) @ Tw
    o.set('xyz', fmt(Tj[:3, 3])); o.set('rpy', fmt(R_to_rpy(Tj[:3, :3])))
    ET.SubElement(j, 'parent').set('link', parent)
    ET.SubElement(j, 'child').set('link', args.link)
    print(f"added fixed link {args.link} under {parent} at world {np.round(Tw[:3,3],4)}")
    u.save()

def cmd_square_joint(args):
    u = open_urdf(args)
    J = u.joints.get(args.joint) or sys.exit(f"no joint {args.joint}")
    o = J.find('origin')
    o.set('rpy', '0 0 0')                       # frame axis-aligned to world
    if args.axis:
        J.find('axis').set('xyz', args.axis.replace(",", " "))
    print(f"{args.joint}: rpy zeroed" + (f", axis -> {args.axis}" if args.axis else ""))
    u.save()

def cmd_set_visual(args):
    u = open_urdf(args)
    L = u.links.get(args.link) or sys.exit(f"no link {args.link}")
    o = L.find('visual').find('origin')
    if args.xyz: o.set('xyz', args.xyz.replace(",", " "))
    if args.rpy is not None: o.set('rpy', args.rpy.replace(",", " "))
    print(f"{args.link}: visual origin xyz={o.get('xyz')} rpy={o.get('rpy')}")
    u.save()

def cmd_validate(args):
    u = Urdf(args.urdf)
    print(f"links: {len(u.links)}  joints: {len(u.joints)}")
    masters, mimics = [], []
    for name, J in u.joints.items():
        m = J.find('mimic')
        if m is not None:
            mimics.append((name, m.get('joint'), m.get('multiplier')))
        elif J.get('type') in ('revolute', 'prismatic', 'continuous'):
            lim = J.find('limit')
            lim_s = f"[{lim.get('lower')}..{lim.get('upper')}]" if lim is not None else "(no limits)"
            masters.append((name, J.get('type'), lim_s))
    print("\nmaster joints (driveable):")
    for n, t, l in masters:
        print(f"  {n:30s} {t:10s} {l}")
    print("\nmimic chains:")
    for n, tgt, mult in mimics:
        ok = "" if tgt in u.joints else "  <-- TARGET MISSING"
        print(f"  {n:30s} <- {tgt} x {mult}{ok}")
    print("\nmesh files:")
    base = os.path.dirname(os.path.abspath(args.urdf))
    missing = 0
    for name, L in u.links.items():
        for vis in L.findall('visual'):
            mesh = vis.find('geometry/mesh')
            if mesh is None:
                continue
            f = mesh.get('filename')
            if not os.path.exists(os.path.join(base, f)):
                print(f"  MISSING: {f}  (link {name})")
                missing += 1
    if not missing:
        print("  all visual meshes present")

def cmd_chain(args):
    # Only read the URDF, no need to create a .bak file for info commands
    u = Urdf(args.urdf)
    tgt = args.link
    if tgt not in u.links:
        sys.exit(f"no link {tgt}")
    
    chain = []
    curr = tgt
    while curr in u._parent_of:
        p, Tj = u._parent_of[curr]
        chain.append((curr, p, Tj))
        curr = p
    chain.append((curr, None, np.eye(4)))
    chain.reverse()
    
    print(f"\nKinematic chain for '{tgt}':")
    for child, parent, Tj in chain:
        if parent is None:
            print(f"  [Root] {child}")
        else:
            Tw = u.world_T(child)
            print(f"  -> {child}")
            print(f"       Local Pos: {np.round(Tj[:3,3], 5)}")
            print(f"       World Pos: {np.round(Tw[:3,3], 5)}")

def cmd_mass(args):
    u = Urdf(args.urdf)
    total_mass = 0.0
    print(f"\n{'Link Name':<30} | {'Mass (kg)':<10} | {'Center of Mass (Local)':<30}")
    print("-" * 75)
    
    for name, link in u.links.items():
        inertial = link.find('inertial')
        if inertial is not None:
            mass_elem = inertial.find('mass')
            origin_elem = inertial.find('origin')
            
            mass = float(mass_elem.get('value')) if mass_elem is not None else 0.0
            total_mass += mass
            
            if origin_elem is not None and origin_elem.get('xyz'):
                com = np.array([float(v) for v in origin_elem.get('xyz').split()])
                com_str = str(np.round(com, 5))
            else:
                com_str = "[0. 0. 0.]"
            
            print(f"{name:<30} | {mass:<10.4f} | {com_str:<30}")
    
    print("-" * 75)
    print(f"{'TOTAL MASS':<30} | {total_mass:<10.4f} |")

def cmd_bbox(args):
    P = load_glb_points(args.glb)
    min_pt = P.min(axis=0)
    max_pt = P.max(axis=0)
    dims = max_pt - min_pt
    center = (max_pt + min_pt) / 2.0
    
    print(f"\nBounding Box for {args.glb}:")
    print(f"  Min    (native): {np.round(min_pt, 5)} m")
    print(f"  Max    (native): {np.round(max_pt, 5)} m")
    print(f"  Center (native): {np.round(center, 5)} m")
    print(f"  Dimensions (mm): {np.round(dims * 1000, 2)}")
    
    # Map to world coordinates (Z-up)
    world_center = RX90 @ center
    world_dims = np.abs(RX90 @ dims)
    print(f"\nMapped for World Z-up:")
    print(f"  Center  (world): {np.round(world_center, 5)} m")
    print(f"  Dimensions (mm): {np.round(world_dims * 1000, 2)}")

def cmd_reparent(args):
    u = open_urdf(args)
    J = u.joints.get(args.joint) or sys.exit(f"no joint {args.joint}")
    new_parent = args.new_parent
    
    if new_parent not in u.links:
        sys.exit(f"no link {new_parent}")
        
    child = J.find('child').get('link')
    
    # Calculate new local transform to keep world position identical
    T_world_child = u.world_T(child)
    T_world_new_parent = u.world_T(new_parent)
    T_new_local = np.linalg.inv(T_world_new_parent) @ T_world_child
    
    # Update parent tag
    J.find('parent').set('link', new_parent)
    
    # Update origin tag
    o = J.find('origin')
    if o is None:
        import xml.etree.ElementTree as ET
        o = ET.SubElement(J, 'origin')
    
    o.set('xyz', fmt(T_new_local[:3, 3]))
    o.set('rpy', fmt(R_to_rpy(T_new_local[:3, :3])))
    
    print(f"{args.joint}: reparented to '{new_parent}'. Local origin recalculated to preserve world space.")
    u.save()

def cmd_glb_visual(args):
    u = open_urdf(args)
    L = u.links.get(args.link) or sys.exit(f"no link {args.link}")
    # world transform of this link's frame
    Tl = u.world_T(args.link)
    # glb is authored in assembly-global (native Y-up). Map to model world:
    # world = RX90 @ native. The visual origin must take native glb pts into the
    # link frame: T_vis = inv(Tl) @ [RX90 | 0]
    T = np.eye(4); T[:3,:3] = RX90
    Tvis = np.linalg.inv(Tl) @ T
    o = L.find('visual').find('origin')
    o.set('xyz', fmt(Tvis[:3,3]))
    o.set('rpy', fmt(R_to_rpy(Tvis[:3,:3])))
    # point the mesh at the glb
    L.find('visual').find('geometry/mesh').set('filename', args.glb.replace('\\','/'))
    print(f"{args.link}: visual origin set for glb {args.glb}")
    u.save()

def cmd_set_origin_world(args):
    u = open_urdf(args)
    J = u.joints.get(args.joint) or sys.exit(f"no joint {args.joint}")
    parent = J.find('parent').get('link')
    Tp = u.world_T(parent)                      # parent frame world transform
    w = np.array([float(v) for v in args.xyz.replace(",", " ").split()] + [1.0])
    p_parent = (np.linalg.inv(Tp) @ w)[:3]      # world point -> parent frame
    o = J.find('origin')
    o.set('xyz', fmt(p_parent))
    print(f"{args.joint}: world {args.xyz} -> parent({parent}) frame {fmt(p_parent)}")
    u.save()

def cmd_set_axis_world(args):
    u = open_urdf(args)
    J = u.joints.get(args.joint) or sys.exit(f"no joint {args.joint}")
    child = J.find('child').get('link')
    Rframe = u.world_T(child)[:3, :3]          # child/joint frame world rotation
    w = np.array([float(v) for v in args.xyz.replace(",", " ").split()])
    w = w / np.linalg.norm(w)
    a = Rframe.T @ w                            # world axis -> joint frame
    a = a / np.linalg.norm(a)
    # snap tiny components to zero for clean right-angle output
    a = np.where(np.abs(a) < 1e-6, 0.0, a)
    J.find('axis').set('xyz', fmt(a))
    print(f"{args.joint}: world axis {args.xyz} -> joint-frame {fmt(a)}")
    u.save()

def cmd_add_mimic(args):
    u = open_urdf(args)
    J = u.joints.get(args.joint) or sys.exit(f"no joint {args.joint}")
    
    if args.target not in u.joints:
        sys.exit(f"target joint {args.target} does not exist")
        
    m = J.find('mimic')
    if m is None:
        import xml.etree.ElementTree as ET
        m = ET.SubElement(J, 'mimic')
        
    m.set('joint', args.target)
    m.set('multiplier', str(args.multiplier))
    
    print(f"{args.joint}: now mimics '{args.target}' (multiplier: {args.multiplier})")
    u.save()

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--urdf", default=URDF_DEFAULT)
    sub = ap.add_subparsers(dest="cmd", required=True)

    # --- New Information Commands ---
    s = sub.add_parser("chain", help="Trace the kinematic chain and world transforms to a specific link")
    s.add_argument("link")
    s.set_defaults(fn=cmd_chain)

    s = sub.add_parser("set-origin-world"); s.add_argument("joint")
    s.add_argument("xyz", help='world-frame point, e.g. "0.724 -1.183 1.03"')
    s.set_defaults(fn=cmd_set_origin_world)

    s = sub.add_parser("set-axis-world"); s.add_argument("joint")
    s.add_argument("xyz", help='world-frame axis, e.g. "0 0 1"')
    s.set_defaults(fn=cmd_set_axis_world)

    s = sub.add_parser("mass", help="Extract and summarize mass and inertial properties from the URDF")
    s.set_defaults(fn=cmd_mass)

    s = sub.add_parser("bbox", help="Calculate the bounding box dimensions of a glb mesh")
    s.add_argument("glb")
    s.set_defaults(fn=cmd_bbox)

    s = sub.add_parser("square-joint"); s.add_argument("joint")
    s.add_argument("--axis", help='clean world axis, e.g. "0 0 1"')
    s.set_defaults(fn=cmd_square_joint)

    s = sub.add_parser("glb-visual"); s.add_argument("link"); s.add_argument("glb")
    s.set_defaults(fn=cmd_glb_visual)

    s = sub.add_parser("shift-joint"); s.add_argument("joint")
    s.add_argument("--world", required=True, help="dx,dy,dz in mm, world frame")
    s.set_defaults(fn=cmd_shift_joint)

    s = sub.add_parser("set-visual"); s.add_argument("link")
    s.add_argument("--xyz"); s.add_argument("--rpy")
    s.set_defaults(fn=cmd_set_visual)

    s = sub.add_parser("set-limit"); s.add_argument("joint")
    s.add_argument("lower", type=float); s.add_argument("upper", type=float)
    s.set_defaults(fn=cmd_set_limit)

    s = sub.add_parser("set-mimic"); s.add_argument("joint")
    s.add_argument("multiplier", type=float); s.set_defaults(fn=cmd_set_mimic)

    s = sub.add_parser("flip-axis"); s.add_argument("joint"); s.set_defaults(fn=cmd_flip_axis)

    s = sub.add_parser("fit-axis"); s.add_argument("glb"); s.set_defaults(fn=cmd_fit_axis)

    s = sub.add_parser("teeth"); s.add_argument("glb"); s.set_defaults(fn=cmd_teeth)

    s = sub.add_parser("place-part")
    s.add_argument("glb"); s.add_argument("link"); s.add_argument("parent")
    s.add_argument("--anchor"); s.add_argument("--stl")
    s.set_defaults(fn=cmd_place_part)

    s = sub.add_parser("validate"); s.set_defaults(fn=cmd_validate)

    s = sub.add_parser("set-axis"); s.add_argument("joint")
    s.add_argument("xyz", help='e.g. "0 0 1" or 0,0,1')
    s.set_defaults(fn=cmd_set_axis)

    s = sub.add_parser("set-mesh-path")
    s.add_argument("old"); s.add_argument("new")
    s.set_defaults(fn=cmd_set_mesh_path)

    # --- Object Relationship Commands ---
    s = sub.add_parser("reparent", help="Change a joint's parent link and recalculate origin to preserve world position")
    s.add_argument("joint")
    s.add_argument("new_parent")
    s.set_defaults(fn=cmd_reparent)

    s = sub.add_parser("add-mimic", help="Create or update a mimic relationship between two joints")
    s.add_argument("joint", help="The joint that will follow the target")
    s.add_argument("target", help="The joint to mimic")
    s.add_argument("multiplier", type=float)
    s.set_defaults(fn=cmd_add_mimic)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
