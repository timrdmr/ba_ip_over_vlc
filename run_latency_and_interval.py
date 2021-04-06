#!/usr/bin/env python3

from flash_nodes import build_source, flash_all_nodes
from code_parameters import overwrite_datarate
from measurements import LatencyMeasurement, LatencyMeasurementData
import time
import math

data_rate = 10000
total_run_time_us = 60 * 1000 * 1000
ref_voltage = "0_43"
payload_size_bytes = 100
distance = 0.5    #cm

min_interval_us = 0 * 1000
steps = 25 * 1000
max_interval_us = 0 * 1000

overwrite_datarate(data_rate)
build_source()

for interval_us in range(min_interval_us, max_interval_us + steps, steps):
    print("-------------")
    print(f"Run data rate test with interval of {interval_us/1000} ms")
    print()
    print("-------------")

    flash_all_nodes()
    time.sleep(3)

    # avoid buffering overhead, udp latency = interval
    expected_ping_ms = ((payload_size_bytes + 61) * 8 / data_rate * 1000)

    print(f"expected_ping_ms: {expected_ping_ms}ms")
    print(f"interval_us: {interval_us}us ({interval_us/1000}ms)")
    print(f"total_run_time_us: {total_run_time_us}us ({total_run_time_us/1000000}s)")

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
        subfolder="latency_interval_10kbps_crc",
        file_name_note=str(data_rate) + "bps_" + ref_voltage + "_V_ref_every" + str(interval_us/1000) + "ms"
    )

print("Measurement finished!")
