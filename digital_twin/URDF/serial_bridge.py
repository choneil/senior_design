#!/usr/bin/env python3
"""
Serial -> WebSocket bridge for the Pick & Place digital twin.

Reads Marlin position reports from the RAMBo over serial, converts each axis
from millimeters to the corresponding URDF *master joint* angle (radians), and
broadcasts the joint state as JSON to any connected browser viewers.

The viewer (index.html) connects to ws://localhost:8765 and applies the values.

Install deps (into whatever Python you run this with):
    pip install pyserial websockets

Run:
    python serial_bridge.py --port COM3            # Windows
    python serial_bridge.py --port /dev/ttyACM0    # Linux
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
# Kinematics: mm of axis travel -> radians of the master pulley joint.
# These MUST match the leads baked into the URDF mimics.
#   X motor pulley drives the Y-assembly: 40 mm / rev  (GT2 20T)
#   Y motor pulley drives the toolhead:   60 mm / rev  (GT2 30T)
# rad_per_mm = 2*pi / lead_mm
# ----------------------------------------------------------------------------
X_LEAD_MM = 52.0
Y_LEAD_MM = 48.0

# Marlin axis letter -> (URDF master joint name, rad per mm, invert?)
# 'invert' flips sign if the twin moves opposite the real machine (fix visually).
AXIS_MAP = {
    "X": {"joint": "X_Motor_Pulley_Revolute", "rad_per_mm": 2 * math.pi / X_LEAD_MM, "invert": False},
    "Y": {"joint": "Y_Motor_Pulley_Revolute", "rad_per_mm": 2 * math.pi / Y_LEAD_MM, "invert": False},
    # "Z": {...}  # add when you model a Z master
}

# Marlin position line, e.g.:  X:12.00 Y:30.00 Z:5.00 E:0.00 Count X:960 ...
POS_RE = re.compile(r"([XYZE]):(-?\d+\.?\d*)")

# ----------------------------------------------------------------------------

clients = set()
latest_state = {}          # joint name -> radians (last known, sent to new clients)
ser = None                 # shared serial handle, set once opened
serial_lock = None         # asyncio.Lock created in main()

# G-code we refuse to forward blindly. M112 (emergency stop) is allowed through;
# everything else passes. This is a light guard, not a safety system.
BLOCKED_PREFIXES = ()      # e.g. ('M303',) to block PID autotune; empty = allow all


def mm_to_joint(axis, mm):
    cfg = AXIS_MAP[axis]
    val = mm * cfg["rad_per_mm"]
    if cfg["invert"]:
        val = -val
    return cfg["joint"], val


def parse_position(line):
    """Return {joint: radians} for any axis letters found, else {}."""
    if "X:" not in line and "Y:" not in line:
        return {}
    head = line.split("Count")[0]        # ignore stepper-count echo after 'Count'
    out = {}
    for axis, val in POS_RE.findall(head):
        if axis in AXIS_MAP:
            joint, rad = mm_to_joint(axis, float(val))
            out[joint] = rad
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
            # inbound messages are JSON: {"gcode": "G1 X10 F1000"} or {"gcode": ["G92 X0 Y0", "M211 S0"]}
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
        # optional polling fallback
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
    ap.add_argument("--port", help="serial port (e.g. COM3 or /dev/ttyACM0)")
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
