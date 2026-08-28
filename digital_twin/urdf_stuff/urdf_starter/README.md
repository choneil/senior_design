# Minimal URDF Viewer

Loads a URDF (with .glb / .stl / .dae meshes) in the browser. No build step,
no internet — three.js and urdf-loader are vendored in `libs/`.

## Layout
    index.html          <- the viewer (edit URDF_PATH at the top)
    libs/               <- vendored three.js + urdf-loader (do not rename)
    robot.urdf          <- your URDF
    meshes/             <- your mesh files, paths as referenced in the URDF

## Run
    python -m http.server 8000
    # open http://localhost:8000

Browsers block file:// module loads, so you must serve it (any static server works).

## Configure (top of index.html)
    URDF_PATH  filename of your URDF (relative to index.html)
    UP_IS_Z    true = URDF is Z-up (typical, rotates -90deg X for three.js)

## Notes
- Mesh paths in the URDF are resolved relative to index.html. If the URDF uses
  `package://name/meshes/...`, rewrite those to plain relative paths
  (e.g. `meshes/...`) or the loader can't find them.
- Non-fixed, non-mimic joints get a slider automatically.
- Collision meshes load but are hidden.
- If nothing renders: open the browser console (F12). A red "URDF load failed"
  or "…fail:" line names the exact file/path problem.
