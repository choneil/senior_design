import serial
import time

PORT = "/dev/ttyACM0"
BAUD = 250000

def read_until_ok(ser, timeout=3):
    end = time.time() + timeout
    while time.time() < end:
        line = ser.readline().decode(errors="replace").strip()
        if line:
            print(line)
        if "ok" in line:
            return True
    return False

def send(ser, cmd):
    print(f">>> {cmd}")
    ser.write((cmd + "\n").encode())
    read_until_ok(ser)

with serial.Serial(PORT, BAUD, timeout=1) as ser:
    time.sleep(2)  # allow board reset

    ser.reset_input_buffer()
    ser.reset_output_buffer()

    # --- Setup ---
    send(ser, "M115")     # firmware info
    send(ser, "M17")      # enable motors
    send(ser, "G90")      # absolute positioning
    send(ser, "G92 X0")   # Sets orgin

    # --- FORWARD: 0 → ~254 mm in 25.4 mm steps ---
    for i in range(15):      
        x = (-1) ** i * i * 5.08
        send(ser, f"G1 X{x:.2f} F75000")
        send(ser, "G4 P200")  # shorter pause since it's fast

    # --- Cut motor current ---
    send(ser, "M18")
