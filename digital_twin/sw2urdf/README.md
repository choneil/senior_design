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
- Mates are not decoded, so link grouping and joints are set in `build_urdf.py` (`link_of`, `FEEDER_LINK`).
- Axis limits come from a collision sweep (`limits.py`) of each axis against the endstops; the build prints
  the part pair that sets each limit.
- The toolhead carriage is lifted so its plate rests on the Y-rail blocks (the CAD overlaps them by ~4.2 mm).
- Masses are estimates from mesh volume and guessed densities. Toolbox screws are not in the Pack and Go and are skipped.
