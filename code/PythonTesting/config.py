USB_SEARCH_PATHS = [
    "/media/pi/*",
    "/media/*/*",
    "/run/media/*/*",
    "/mnt/usb",
]

# Serial / Rambo
# Pin this to a stable name with a udev rule (e.g. /dev/rambo) so it does not
# collide with the onboard UART or shift on reboot.
SERIAL_PORT = "/dev/ttyACM0"
BAUD_RATE = 115200
SERIAL_TIMEOUT = 2          # seconds per readline()
SERIAL_MAX_TIMEOUTS = 5     # consecutive empty reads before we give up on an 'ok'

# Vacuum control
# Marlin digital pin number wired to the vacuum solenoid / MOSFET.
# VAC ON  -> M42 P<VAC_PIN> S255
# VAC OFF -> M42 P<VAC_PIN> S0
VAC_PIN = 4                 # <-- set to your actual wired pin

# Geometry
FEEDER_X = -10.0
FEEDER_Y = -10.0
ORIGIN_X = 0.0
ORIGIN_Y = 0.0

# Z heights (mm). Pick and place are separate on purpose: pick height is set
# by the feeder/tape surface, place height by board + component thickness.
Z_UP = 10.0                # safe travel height
Z_PICK = 1.0               # height to grab part from feeder
Z_PLACE = 1.5              # height to set part on board

# Feedrates (mm/min)
XY_FEEDRATE = 3000
Z_FEEDRATE = 500
ROTATE_FEEDRATE = 300

REQUIRED_COLUMNS = ["Designator", "X", "Y", "Rotation"]