# Pick and Place Digital Twin
Web-based digital twin using URDF and Three.js, built from the SolidWorks "Pick and Place - Final Configuration" assembly. Live-mirroring of the RAMBo/Marlin setup over serial. Live mirroring only supports linear movements.

- `URDF/` – the viewer (`index.html`), the model (`PickAndPlace.urdf`, `meshes/`, `part_types.json`) and the serial bridge (`serial_bridge.py`)
- `sw2urdf/` – rebuilds the model from a SolidWorks Pack and Go, without SolidWorks (see `sw2urdf/README.md`)
- `RAMBo/` – 3D viewer of the RAMBo v1.2 controller board with pin and net lookup (see `RAMBo/README.md`)

# View
https://choneil.github.io/senior_design/digital_twin/URDF/

# Run (no hardware)
## while in the digital_twin directory:

cd URDF
python -m http.server 8000

open http://localhost:8000

The board viewer is at http://localhost:8000/RAMBo/index.html when serving the `digital_twin` folder.

# Run (with hardware)
## while in the digital_twin directory:

pip install -r requirements.txt

cd URDF

python serial_bridge.py --port PORT

# Model
| Axis | Joint | Drive | Travel (from endstop collisions) |
|---|---|---|---|
| X | `leadscrew_l_joint` (gantry follows) | twin lead screws, 8 mm/rev | -133.4 .. +194.0 mm |
| Y | `toolhead_carriage_joint` | 20T GT2 belt, 40 mm/rev | -98.9 .. +179.0 mm |
| Z | `z1_joint` (Z2 moves opposite) | 20T GT2 belt, 40 mm/rev | 0 .. 66.8 mm |

The 0816 feeder (servo slider-crank, cover-tape winder and tension lever) is animated in the viewer: the Feed button, or `M600` / `M601` / `M603 A<deg>` in the G-code box (simulated only, never sent to the RAMBo).

Viewer options: `?urdf=<path>` loads another URDF, `?debug` exposes `robot`, `camera` and `controls` in the browser console.
