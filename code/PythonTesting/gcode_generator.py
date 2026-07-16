from config import *


def component_to_gcode(c):
    lines = []

    lines.append(f"; {c['designator']}")

    # --- Pick from feeder ---
    lines.append(f"G1 X{FEEDER_X} Y{FEEDER_Y} F{XY_FEEDRATE} ; move to feeder")
    lines.append(f"G1 Z{Z_PICK} F{Z_FEEDRATE} ; lower Z to pick")
    lines.append("VAC ON ; turn vacuum on")
    lines.append(f"G1 Z{Z_UP} F{Z_FEEDRATE} ; raise Z after pick")

    # --- Move to placement location ---
    lines.append(f"G1 X{c['x']} Y{c['y']} F{XY_FEEDRATE} ; move to placement location")

    # --- Rotate component if needed ---
    # NOTE: this drives the E axis as the rotation (theta) axis. The value is
    # in degrees, so STEPS_PER_DEGREE must be calibrated in Marlin (E steps/mm)
    # for this to map correctly. E is absolute here because of G90.
    if c["rotation"] != 0:
        lines.append(f"G1 E{c['rotation']} F{ROTATE_FEEDRATE} ; rotate component")

    # --- Place ---
    lines.append(f"G1 Z{Z_PLACE} F{Z_FEEDRATE} ; lower Z to place")
    lines.append("VAC OFF ; release component")
    lines.append(f"G1 Z{Z_UP} F{Z_FEEDRATE} ; raise Z after place")

    # --- Reset rotation back to zero so the next pick starts square ---
    if c["rotation"] != 0:
        lines.append(f"G1 E0 F{ROTATE_FEEDRATE} ; reset rotation")

    return lines


def build_gcode(components):
    lines = []

    # --- Preamble / calibration ---
    lines.append("G21 ; units = mm")
    lines.append("G90 ; absolute positioning")
    lines.append("G28 ; home all axes -- establishes known origin")
    lines.append(f"G1 Z{Z_UP} F{Z_FEEDRATE} ; raise to safe Z before any XY move")
    lines.append(f"G92 E0 ; zero the rotation axis")

    # --- Per-component placement ---
    for c in components:
        lines += component_to_gcode(c)

    # --- Park ---
    lines.append(f"G1 Z{Z_UP} F{Z_FEEDRATE} ; raise Z")
    lines.append(f"G1 X{ORIGIN_X} Y{ORIGIN_Y} F{XY_FEEDRATE} ; return to origin")

    return lines