#!/usr/bin/env python3

from flash_nodes import build_source, flash_all_nodes
from code_parameters import overwrite_tolerance, overwrite_datarate
from measurements import LatencyMeasurement, LatencyMeasurementData
import time

datarate = 30000

min_tolerance = 0
steps = 5
max_tolerance = 50

number_packages_per_run = 500

overwrite_datarate(datarate)

for tolerance in range(min_tolerance, max_tolerance + steps, steps):
    print("-------------")
    print(f"Run tolerance measurement with tolerance value of {tolerance}")
    print(f"The datarate was set to {datarate}")
    print("-------------")

    overwrite_tolerance(tolerance)

    build_source()
    flash_all_nodes()

    # wait until RIOT is initialized
    time.sleep(3)

    ref_voltage = "0_43"
    payload_size_bytes = 100
    distance = 0.5    #cm

    # avoid buffering effects
    expected_ping_ms = ((payload_size_bytes + 61) * 8 / datarate * 1000) + 25
    interval_us = round(expected_ping_ms* 1000)
    total_run_time_us = number_packages_per_run * interval_us

    print(expected_ping_ms)
    print(interval_us)
    print(total_run_time_us)

    l = LatencyMeasurement(
        runtime_us=total_run_time_us,
        payload_size_bytes=payload_size_bytes,
        interval_us=interval_us,
        distance_cm=distance,
        random_payload=True
    )

    measurements_list = l.run()
    assert measurements_list != None, "measurement failed"

    l.write_measurement_to_file(
        subfolder="receiver_tolerance_crc",
        file_name_note="rtol" + str(tolerance) + "_" + ref_voltage + "_V_ref_" + str(datarate) + "kbps"
    )

print("Measurement finished!")
