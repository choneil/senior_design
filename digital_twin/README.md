# Pick and Place Digital Twin
Web-based digital twin using URDF and Three.js. Live-mirroring of the rambo/marlin setup over serial. Live mirroring only supports linear movements.

## View
https://choneil.github.io/senior_design/digital_twin/URDF/

## Run (no hardware)
# while in the digital_twin directory:

cd URDF
python -m http.server 800

open http://localhost:8000 

## Run (with hardware)
# while in the digital_twin directory:

pip install -r requirements.txt

cd URDF

python serial_bridge.py --port PORT
