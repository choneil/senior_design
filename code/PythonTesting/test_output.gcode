G21
G90
; U1
G1 X-10.0 Y-10.0 ; move to feeder
G1 Z1.0 ; lower Z to pick
VAC ON ; turn vacuum on
G1 Z10.0 ; raise Z after pick
G1 X25.0 Y20.0 ; move to placement location
G1 E90.0 ; rotate component
G1 Z1.0 ; lower Z to place
VAC OFF ; release component
G1 Z10.0 ; raise Z after place
G1 X0.0 Y0.0 ; return to origin
; R1
G1 X-10.0 Y-10.0 ; move to feeder
G1 Z1.0 ; lower Z to pick
VAC ON ; turn vacuum on
G1 Z10.0 ; raise Z after pick
G1 X10.0 Y8.0 ; move to placement location
G1 Z1.0 ; lower Z to place
VAC OFF ; release component
G1 Z10.0 ; raise Z after place
G1 X0.0 Y0.0 ; return to origin
; C1
G1 X-10.0 Y-10.0 ; move to feeder
G1 Z1.0 ; lower Z to pick
VAC ON ; turn vacuum on
G1 Z10.0 ; raise Z after pick
G1 X15.5 Y12.2 ; move to placement location
G1 E180.0 ; rotate component
G1 Z1.0 ; lower Z to place
VAC OFF ; release component
G1 Z10.0 ; raise Z after place
G1 X0.0 Y0.0 ; return to origin
