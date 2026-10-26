# Thresholds follow Ruuvi Station's rule: a coin cell's voltage sags in the cold,
# so the cutoff drops with temperature to avoid false warnings outdoors in winter.
LOW_MV_ABOVE_FREEZING = 2500
LOW_MV_BELOW_FREEZING = 2300
LOW_MV_BELOW_MINUS_20 = 2000


def is_battery_low(battery_mv, temperature_c):
    if battery_mv is None:
        return False
    if temperature_c is None or temperature_c >= 0:
        threshold = LOW_MV_ABOVE_FREEZING
    elif temperature_c >= -20:
        threshold = LOW_MV_BELOW_FREEZING
    else:
        threshold = LOW_MV_BELOW_MINUS_20
    return battery_mv < threshold
