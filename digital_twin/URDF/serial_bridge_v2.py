#!/usr/bin/env python3
"""
Serial -> WebSocket bridge for the Pick & Place digital twin (Assem1.urdf).

Reads Marlin position reports from the RAMBo v1.2 over serial, converts each
axis from millimeters to the corresponding URDF *master joint* value, and
broadcasts the joint state as JSON to any connected browser viewers.

RAMBo v1.2 drive mapping (Assem1.urdf master joints):
    X : motor X (+ ext motor wired opposite) -> leadscrews, 2mm lead.
        Sent as leadscrew_l_joint radians; leadscrew_r mimics x-1 in the URDF.
    Y : motor Y on a 24T GT2 belt -> toolhead_carriage_joint (prismatic, meters).
    Z : motor Z -> z1 leadscrew, 2mm lead -> z1 joint radians.
    E : motor E -> 19T stepper gear -> e1_stepper_gear_19_joint radians.
        The 32T nut and plunger translation follow via URDF mimics.

The bridge sends MASTER joint values; the URDF mimics produce the visible
linear travel. Bridge factors and URDF mimic multipliers compose to unity
(e.g. 3.1416 rad/mm * 0.00031831 m/rad = 0.001 m/mm), so 1 real mm -> 1 twin mm.

The viewer (index.html) connects to ws://localhost:8765 and applies the values.

Install deps:
    pip install pyserial websockets
Run:
    python serial_bridge.py --port /dev/tty.usbmodem*      # macOS
    python serial_bridge.py --port COM3                    # Windows
    python serial_bridge.py --port /dev/ttyACM0            # Linux
"""

import argparse
import asyncio
import json
import math
import re
import sys

import serial               # pyserial
import serial.tools.list_ports
import websockets           # websockets

# ----------------------------------------------------------------------------
# Kinematics: Marlin mm -> URDF master joint value.
#   Screws (X, Z): 2mm lead -> rad_per_mm = 2*pi / lead_mm = 3.141593
#   Belt   (Y):    prismatic joint in METERS -> 0.001 m per mm
#   E:             Marlin E mm assumed == plunger travel mm.
#                  plunger travels (19/32)*0.5mm per stepper rev,
#                  so stepper rad_per_mm = 2*pi / ((19/32)*0.5) = 21.1644
# These MUST stay consistent with the mimic multipliers baked into Assem1.urdf.
# ----------------------------------------------------------------------------
SCREW_LEAD_MM = 2.0
SCREW_RAD_PER_MM = 2 * math.pi / SCREW_LEAD_MM            # 3.141593 rad/mm

PLUNGER_MM_PER_STEPPER_REV = (19.0 / 32.0) * 0.5
E_RAD_PER_MM = 2 * math.pi / PLUNGER_MM_PER_STEPPER_REV   # 21.1644 rad/mm

# Marlin axis letter -> (URDF master joint, factor per mm, invert?)
# For prismatic joints the factor is METERS per mm (0.001); key name kept as
# "rad_per_mm" for uniformity with the revolute axes.
AXIS_MAP = {
    "X": {"joint": "leadscrew_l_joint",                  "rad_per_mm": SCREW_RAD_PER_MM, "invert": False},
    "Y": {"joint": "toolhead_carriage_joint",            "rad_per_mm": 0.001,            "invert": False},
    "Z": {"joint": "z1_threaded_rod_and_coupling_joint", "rad_per_mm": SCREW_RAD_PER_MM, "invert": False},
    "E": {"joint": "e1_stepper_gear_19_joint",           "rad_per_mm": E_RAD_PER_MM,     "invert": False},
}

# Marlin position line, e.g.:  X:12.00 Y:30.00 Z:5.00 E:0.00 Count X:960 ...
POS_RE = re.compile(r"([XYZE]):(-?\d+\.?\d*)")

# ----------------------------------------------------------------------------

clients = set()
latest_state = {}          # joint name -> value (last known, sent to new clients)
ser = None                 # shared serial handle, set once opened
serial_lock = None         # asyncio.Lock created in main()

# G-code we refuse to forward blindly. Empty = allow all (M112 e-stop passes).
BLOCKED_PREFIXES = ()


def mm_to_joint(axis, mm):
    cfg = AXIS_MAP[axis]
    val = mm * cfg["rad_per_mm"]
    if cfg["invert"]:
        val = -val
    return cfg["joint"], val


def parse_position(line):
    """Return {joint: value} for any axis letters found, else {}."""
    if "X:" not in line and "Y:" not in line:
        return {}
    head = line.split("Count")[0]        # ignore stepper-count echo after 'Count'
    out = {}
    for axis, val in POS_RE.findall(head):
        if axis in AXIS_MAP:
            joint, v = mm_to_joint(axis, float(val))
            out[joint] = v
    return out


async def send_gcode(line, loop):
    """Write a single G-code line to the serial port (thread executor)."""
    global ser
    if ser is None:
        return False, "serial not open"
    line = line.strip()
    if not line:
        return False, "empty"
    up = line.upper()
    if any(up.startswith(p) for p in BLOCKED_PREFIXES):
        return False, f"blocked: {line}"
    payload = (line + "\n").encode()
    async with serial_lock:
        await loop.run_in_executor(None, ser.write, payload)
    print(f"[bridge] > {line}")
    return True, line


async def ws_handler(websocket):
    clients.add(websocket)
    loop = asyncio.get_running_loop()
    try:
        if latest_state:
            await websocket.send(json.dumps({"joints": latest_state}))
        async for raw in websocket:
            # inbound JSON: {"gcode": "G1 X10 F1000"} or {"gcode": ["G92 X0", "M211 S0"]}
            try:
                data = json.loads(raw)
            except Exception:
                continue
            cmds = data.get("gcode")
            if cmds is None:
                continue
            if isinstance(cmds, str):
                cmds = [cmds]
            for c in cmds:
                ok, info = await send_gcode(c, loop)
                await websocket.send(json.dumps({"ack": {"ok": ok, "cmd": info}}))
    finally:
        clients.discard(websocket)


async def broadcast(state):
    if not clients:
        return
    msg = json.dumps({"joints": state})
    dead = []
    for ws in clients:
        try:
            await ws.send(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.discard(ws)


async def serial_reader(port, baud, use_autoreport, poll_hz, loop):
    """Blocking serial read in a thread executor; parse and broadcast."""
    global ser
    try:
        ser = serial.Serial(port, baud, timeout=0)
    except Exception as e:
        print(f"[bridge] ERROR opening {port}: {e}", file=sys.stderr)
        return

    print(f"[bridge] opened {port} @ {baud}")
    # give the board time to finish its bootloader reset, then request reports
    await asyncio.sleep(2.0)
    if use_autoreport:
        ser.write(b"M154 S0.1\n")        # auto-report position every 0.1s
        print("[bridge] requested M154 auto-report")

    buf = b""
    last_poll = 0.0
    while True:
        if not use_autoreport:
            now = loop.time()
            if now - last_poll >= 1.0 / poll_hz:
                async with serial_lock:
                    ser.write(b"M114\n")
                last_poll = now

        data = await loop.run_in_executor(None, ser.read, 4096)
        if data:
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                text = line.decode(errors="ignore").strip()
                print(f"[RX] {text}")
                joints = parse_position(text)
                if joints:
                    latest_state.update(joints)
                    await broadcast(latest_state)
        else:
            await asyncio.sleep(0.005)   # avoid busy spin


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", help="serial port (e.g. COM3, /dev/ttyACM0, /dev/tty.usbmodemXXXX)")
    ap.add_argument("--baud", type=int, default=250000)
    ap.add_argument("--ws-port", type=int, default=8765)
    ap.add_argument("--poll", action="store_true",
                    help="use M114 polling instead of M154 auto-report")
    ap.add_argument("--poll-hz", type=float, default=10.0)
    ap.add_argument("--list", action="store_true", help="list serial ports and exit")
    args = ap.parse_args()

    if args.list:
        for p in serial.tools.list_ports.comports():
            print(f"  {p.device}  {p.description}")
        return
    if not args.port:
        ap.error("--port is required (use --list to see ports)")

    global serial_lock
    loop = asyncio.get_running_loop()
    serial_lock = asyncio.Lock()
    ws_server = await websockets.serve(ws_handler, "0.0.0.0", args.ws_port)
    print(f"[bridge] WebSocket on ws://localhost:{args.ws_port}")

    await serial_reader(args.port, args.baud, not args.poll, args.poll_hz, loop)
    ws_server.close()
    await ws_server.wait_closed()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[bridge] stopped")
