#!/usr/bin/env python3

from flash_nodes import build_source, flash_all_nodes
from code_parameters import overwrite_datarate
from measurements import LatencyMeasurement, LatencyMeasurementData
import time
import math

min_data_rate = 30000
steps = 1000
max_data_rate = 35000

number_packages_per_run = 1000

for data_rate in range(min_data_rate, max_data_rate + steps, steps):
    print("-------------")
    print(f"Run data rate test with data rate of {data_rate} bits/s")
    print("-------------")

    overwrite_datarate(data_rate)

    build_source()
    flash_all_nodes()

    # wait until RIOT is initialized
    time.sleep(3)

    ref_voltage = "0_43"
    payload_size_bytes = 100
    distance = 0.5    #cm

    # avoid buffering effects
    expected_ping_ms = ((payload_size_bytes + 62.5) * 8 / data_rate * 1000) + 30
    interval_us = math.ceil(expected_ping_ms* 1000)
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
        subfolder="datarate_and_reliability_more_runs",
        file_name_note=str(data_rate) + "bps_" + ref_voltage + "_V_ref"
    )

print("Measurement finished!")
