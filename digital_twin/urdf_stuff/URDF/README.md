# Digital Twin Tools

Routine URDF edits without burning Claude usage. Run from the `URDF/` folder.

## Setup (once)
    pip install numpy scipy pygltflib

## Common operations
    # nudge a part (moves joint + its mesh together), mm in world frame
    python tools/twin.py shift-joint E_Nut_32T_Joint --world 0,-4.02,0

    # set travel limits (m for prismatic, rad for revolute)
    python tools/twin.py set-limit Z_Mount_Prismatic 0 0.029

    # wrong spin/travel direction
    python tools/twin.py flip-axis E_Plunger_Joint
    python tools/twin.py set-mimic Z_Screw_Joint -3141.592654

    # measure a mesh (axis line, world-mapped)
    python tools/twin.py fit-axis meshes/Extruder/Threaded_Rod_and_Coupling.glb

    # count pulley/gear teeth (verify a part is what you think)
    python tools/twin.py teeth meshes/motor_pulley_x.glb

    # add a new fixed part exported in the ORIGINAL session frame
    python tools/twin.py place-part meshes/Extruder/NEMA.glb Z_Motor Toolhead_Carriage

    # add a part exported in a DIFFERENT session (carriage parked elsewhere):
    # include that session's carriage export + the old STL as the anchor
    python tools/twin.py place-part meshes/Extruder/NEMA.glb Z_Motor Toolhead_Carriage \
        --anchor meshes/toolhead_carriage_session.glb --stl meshes/Toolhead_Carriage.STL

    # health check: masters, mimic chains, missing meshes
    python tools/twin.py validate

Every edit writes a `.urdf.bak` backup first.

## Conventions baked in
- glbs export in assembly-global coords; glTF Y-up -> model Z-up via +90deg X.
- Model rest pose = the original export session. New sessions are anchored by
  registering the carriage glb against Toolhead_Carriage.STL (link coords).
- Kinematics: X motor 26T GT2 (52mm/rev) -> Y assembly; Y motor 24T GT2
  (48mm/rev) -> toolhead; E: 19T->32T gears, 0.5mm pitch (0.297mm plunger/rev);
  Z: 2mm/rev screw, +Z input = stage down.
