import time
import serial

PORT = "/dev/ttyACM0"
BAUD = 250000

def read_until_ok(ser, timeout=3):
    end = time.time() + timeout
    while time.time() < end:
        line = ser.readline().decode(errors="replace").strip()
        if line:
            print(line)
        if line == "ok" or line.endswith("ok"):
            return True
    return False

with serial.Serial(PORT, BAUD, timeout=1) as ser:
    time.sleep(2)          # board often resets when port opens
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    ser.write(b"M115\n")   # ask firmware for info
    read_until_ok(ser)

    ser.write(b"G90\n")    # absolute positioning
    read_until_ok(ser)

    ser.write(b"M114\n")   # report current position
    read_until_ok(ser)

    send("M17")          # enable motors
    send("G28 X")        # home X axis
    send("G90")          # absolute positioning

    send("G1 X0 F300")
    send("G1 X50 F300")
    send("G1 X100 F300")
    send("G1 X150 F300")
    send("G1 X200 F300")
    send("G1 X250 F300")
