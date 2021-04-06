#!/usr/bin/env python3

from flash_nodes import build_source, flash_all_nodes
from code_parameters import overwrite_datarate
from measurements import LatencyMeasurement, LatencyMeasurementData
import time
import math

min_data_rate = 18000
steps = 1000
max_data_rate = 40000

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

    # avoid buffering overhead, udp latency = interval
    expected_ping_ms = ((payload_size_bytes + 61) * 8 / data_rate * 1000)
    interval_us = math.floor(expected_ping_ms* 1000)
    # interval_us = 0
    total_run_time_us = 30 * 1000000

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
        subfolder="datarate_and_throughput_latency_equals_interval",
        file_name_note=str(data_rate) + "bps_" + ref_voltage + "_V_ref"
    )

print("Measurement finished!")
