step_size = 1.8                      # deg/full-step
microstep = [1, 1/2, 1/4, 1/8, 1/16]
lead = 2                             # Tr8x2 lead (mm/rev)

steps_per_rev = 360 / step_size      # 200
for i in microstep:
    movement = lead * i / steps_per_rev   # mm per (micro)step
    print(f"Movement per step at 1/{round(1/i)} microstepping: "f"{movement*1000:.3f} um")
