# sw2urdf

Rebuilds `../URDF/PickAndPlace.urdf`, its GLB meshes and `part_types.json` straight from the SolidWorks
Pack and Go of "Pick and Place - Final Configuration", without SolidWorks. It reads part placements from
the assembly's embedded component tree and meshes from SolidWorks' cached display tessellation.

```
python3 -m venv venv && venv/bin/pip install -r requirements.txt
venv/bin/python build_urdf.py "<unzipped Pack and Go>/.../Pick and Place.SLDASM" ../URDF
```

The other parts are found relative to the `.SLDASM`, so keep the Pack and Go's folder layout.

View it: from `../URDF`, run `python3 -m http.server 8000` and open `http://localhost:8000`.

What the build does beyond the CAD:
- Parts that aren't in the Pack and Go are added from the owner's description: four 150 mm 4040 feet under the ends
  of the foundation 4040s (against the corner brackets) and two 600 mm 2040 rails under the foundation in the 220 mm
  gap between them, on edge against the feet.
- The printed bed and board clamps come from `printed/*.stl`, rebuilt from their Cura print file with
  `gcode_mesh.py "<file>.gcode" printed` (the second clamp copy is dropped). The bed is flipped from its print
  orientation onto the rails; its position along the rails and which way round it sits are assumptions noted in
  `build_urdf.py`. The clamps have their own colour group.
- The test board comes from `board/pnp_test_board.{png,json}`, rendered from its KiCad file with
  `kicad_board.py "<board>.kicad_pcb" board` (mask, tracks, pads, silkscreen, holes). It lies face up on the bed with
  its place origin (bottom left) in the corner stop, and the clamps are slid along their slots onto its far edges.
  The artwork is a textured node outside the part-type colouring, so the viewer keeps it.
- Mates are not decoded, so link grouping and joints are set in `build_urdf.py` (`link_of`, `FEEDER_LINK`).
- Axis limits come from a collision sweep (`limits.py`) of each axis against the endstops; the build prints
  the part pair that sets each limit.
- The toolhead carriage is lifted so its plate rests on the Y-rail blocks (the CAD overlaps them by ~4.2 mm).
- Masses are estimates from mesh volume and guessed densities. Toolbox screws are not in the Pack and Go; one that
  has no cached tessellation in the assembly borrows the mesh of another instance of the same size (configuration),
  and is skipped if there is none. Mirrored parts without a display list are handled the same way.
