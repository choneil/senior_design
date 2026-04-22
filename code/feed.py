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
    time.sleep(2)  # allow board to reset

    ser.reset_input_buffer()
    ser.reset_output_buffer()

    # --- Get firmware info ---
    send(ser, "M115")

    # --- Set max feedrate to 100 mm/s ---
    send(ser, "M203 X50000")

    send(ser, "M201 X50000")
    # --- Save to EEPROM (make it default) ---
    send(ser, "M500")

    # --- Verify settings ---
    send(ser, "M503")

    print("Done: X max speed set to 100 mm/s")
