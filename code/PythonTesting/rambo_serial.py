import time
import threading
import serial
from config import *


class Rambo:
    def __init__(self):
        self.ser = None
        # One lock guards ALL access to the serial port. Both the worker
        # thread (sending g-code) and the main thread (abort) must hold it
        # before touching self.ser, or the two threads will garble each
        # other's bytes on the wire.
        self.lock = threading.Lock()

    def connect(self):
        self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=SERIAL_TIMEOUT)
        # Marlin resets when the port opens; give it time to boot, then
        # clear any startup banner out of the input buffer.
        time.sleep(2)
        self.ser.reset_input_buffer()

    def is_connected(self):
        return self.ser is not None and self.ser.is_open

    def send(self, line):
        """
        Send one line of g-code and wait for Marlin's 'ok' before returning.
        Translates the pseudo-commands VAC ON / VAC OFF into real Marlin
        commands. Skips comments and blank lines. Raises on error / timeout
        instead of looping forever.
        """
        line = line.strip()
        if line == "" or line.startswith(";"):
            return

        # Map our human-readable vacuum pseudo-commands to real Marlin output.
        # M42 sets a digital pin; configure VAC_PIN in config.py to the pin
        # wired to your vacuum solenoid/MOSFET. S255 = on, S0 = off.
        if line == "VAC ON":
            line = f"M42 P{VAC_PIN} S255"
        elif line == "VAC OFF":
            line = f"M42 P{VAC_PIN} S0"

        with self.lock:
            if not self.is_connected():
                raise RuntimeError("Serial port not connected")

            self.ser.write((line + "\n").encode())

            # Bounded wait for 'ok'. readline() returns "" on timeout because
            # the port has SERIAL_TIMEOUT set, so an unresponsive board can
            # never hang us forever.
            timeouts = 0
            while True:
                resp = self.ser.readline().decode("utf-8", errors="ignore").strip()

                if resp.startswith("ok"):
                    return

                if resp.startswith("error") or resp.startswith("!!"):
                    raise RuntimeError(f"Marlin reported: {resp}")

                if resp == "":
                    # No data within the timeout window.
                    timeouts += 1
                    if timeouts >= SERIAL_MAX_TIMEOUTS:
                        raise TimeoutError(
                            f"No 'ok' from Rambo after {timeouts} timeouts "
                            f"on line: {line}"
                        )
                    continue

                # Anything else (echo:, busy: processing, temperature reports,
                # etc.) is informational — keep waiting for the ok.
                # Reset the timeout counter since the board is clearly alive.
                timeouts = 0

    def emergency_stop(self):
        """
        Abort current motion. Acquires the lock so it can't collide with a
        send() in progress on the worker thread. M410 is Marlin's quickstop
        (halts planned moves). NOTE: a software stop is a convenience, not a
        safety device — wire a real hardware E-stop into the Rambo for true
        emergency shutoff.
        """
        with self.lock:
            if self.is_connected():
                self.ser.write(b"M410\n")
                # Also drop the vacuum so a held part is released on abort.
                self.ser.write(f"M42 P{VAC_PIN} S0\n".encode())

    def close(self):
        with self.lock:
            if self.is_connected():
                self.ser.close()
            self.ser = None