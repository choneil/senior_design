# RAMBo v1.2 board viewer

3D view of the pick & place controller board (UltiMachine RAMBo v1.2h), built from the open-source Eagle files.
Click a part (or pick it from the list) to see its pins, nets, Arduino pin numbers and Marlin pin roles.
Connectors the pick & place uses are marked in orange.

## View
Serve the `digital_twin` folder (the viewer loads three.js from `../URDF/libs`):

    cd digital_twin
    python -m http.server 8000

then open http://localhost:8000/RAMBo/index.html

Options: `?part=X8` selects a part on load, `?part=U5&open` also opens its package, `?debug` exposes `scene`,
`camera`, `data` in the console.

ICs with an entry in `internals.json` get an **Open package** button: the moulded body turns into a ghost and
the lead frame, die and bond wires show, with the die drawn as the IC's internal circuit down to transistors.
While a package is open the mouse wheel zooms toward the pointer, so you can zoom into a single block.

## Files
- `index.html` – the viewer
- `cutaway.js` – the package cutaway (lead frame, die, bond wires, die drawing)
- `cells.js` – schematic symbols, and the transistor-level circuits drawn inside the die's function blocks. The
  datasheets show those blocks only as boxes and their designs are not published, so each block gets the standard
  textbook circuit for its job (comparator, bandgap, R-string DAC, flip-flop, SRAM / flash / EEPROM cells, ...).
  Each block is also rendered as its own sharper texture laid over the die.
- `internals.json` – per IC (keyed by part value): package and lead-frame dimensions from the datasheet's package
  drawing, datasheet pin names, and the internal circuit as the datasheet's figures draw it, with transistors where
  the datasheet shows them (A4982 DMOS bridges, LM22675 power switch, AVR pin circuits), and the circuit from
  `cells.js` for each block. Die sizes and floorplans are not published by the manufacturers, so the die is sized
  to fit the paddle and blocks sit next to their pins.
- `board.json`, `top.png`, `bottom.png` – generated board model and textures
- `tools/build_board.py` – regenerates them (needs only Pillow: `pip install pillow`, then `python tools/build_board.py`).
  It downloads its inputs into `tools/.cache/`: the RAMBo 1.2h board, schematic and BOM
  (github.com/ultimachine/RAMBo, CC BY-SA 3.0) and Marlin's `pins_RAMBO.h`.

Copper, pads and silkscreen come straight from the board file. Component bodies are simplified shapes sized
per package, not manufacturer CAD models. Connector functions come from the board silkscreen and
Marlin's pin map; the pick & place usage notes come from `URDF/serial_bridge.py`.
