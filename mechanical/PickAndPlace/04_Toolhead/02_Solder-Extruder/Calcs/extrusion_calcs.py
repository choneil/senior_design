# extrusion_calcs.py
# Syringe extruder: stepper -> 19T/32T gear pair -> 0.5 mm lead screw -> plunger
# 3 mL luer lock syringe, 9.5 mm bore

import math

step_size = 1.8                       # deg/full-step
microstep = [1, 1/2, 1/4, 1/8, 1/16]  # A4982
lead = 0.5                            # screw lead (mm/rev), single-start: lead == pitch
gear_ratio = 19 / 32                  # screw revs per motor rev (reduction)
bore_dia = 9.5                        # syringe bore (mm)

steps_per_rev = 360 / step_size                   # 200
area = math.pi * (bore_dia / 2) ** 2              # plunger area (mm^2)
travel_per_motor_rev = lead * gear_ratio          # mm plunger travel / motor rev

print(f"Plunger area:            {area:.2f} mm^2")
print(f"Travel per motor rev:    {travel_per_motor_rev*1000:.1f} um")
print(f"Volume per motor rev:    {area*travel_per_motor_rev:.3f} mm^3 ({area*travel_per_motor_rev:.3f} uL)")
print()

for i in microstep:
        move = travel_per_motor_rev * i / steps_per_rev    # mm per (micro)step
        vol = area * move                                  # mm^3 = uL per (micro)step
        print(f"1/{round(1/i):<2} step: {move*1e6:8.1f} nm plunger travel, "
                                f"{vol*1000:8.2f} nL per step")

        # Flow rate helper: volumetric rate at a given step frequency
def flow_rate(steps_per_sec, ustep=1/16):
        """Returns uL/s at given microstep pulse rate."""
        return area * travel_per_motor_rev * ustep / steps_per_rev * steps_per_sec

        print()
        print(f"Example: 500 pps at 1/16 -> {flow_rate(500):.3f} uL/s")
