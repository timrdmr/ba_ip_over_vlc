#!/usr/bin/env python3

import matplotlib.pyplot as plt
import math
import os

from measurements import LatencyMeasurement

# path of measurements
measurement_path = "/home/tim/Bachelorarbeit/Messungen/latency_interval_10kbps_crc/"

files = os.listdir(measurement_path)
files = sorted(files)

if "measurement.txt" in files:
    files.remove("measurement.txt")

# files = [
#     "latency_2021-02-19T10-25-23_100b_over300s_every500ms.csv",
#     "latency_2021-02-19T10-18-09_100b_over300s_every135ms.csv",
#     "latency_2021-02-19T09-34-38_100b_over300s_every130ms.csv",
#     "latency_2021-02-19T10-33-40_100b_over300s_every100ms.csv",
#     "latency_2021-02-19T10-40-36_100b_over300s_every50ms.csv",
#     # "latency_2021-02-14T18-47-31_100b_over300s_every25ms.csv",
#     "latency_2021-02-19T10-47-00_100b_over300s_every0ms.csv",
# ]
bin_size_s = 5

# plot
fig, axis = plt.subplots()
plt.xlabel("time [in s]")
plt.ylabel("Packet Delivery Rate [0..1]")
payload_size_bytes = 0
for file_name in files:
    l = LatencyMeasurement()
    result = l.read_measurement_from_file(measurement_path + file_name)
    assert result != None, "parsing error"

    interval_us = l.get_interval_us()
    assert (payload_size_bytes == 0 or payload_size_bytes == l.get_payload_size()), "measurements with different payload sizes"
    payload_size_bytes = l.get_payload_size()

    y_reliability_per_bin_udp = l.get_reliability_udp_per_time(bin_size_s=bin_size_s)

    axis.plot(
        [i*bin_size_s for i in range(len(y_reliability_per_bin_udp))],
        y_reliability_per_bin_udp, 
        label="UDP, send interval of " + str(round(interval_us / 1000)) + "ms"
    )

# plt.title(f"Transport Layer Packet Delivery Rate (UDP {payload_size_bytes} byte payload) with binsize of {bin_size_s} s and 0.5cm distance")
# legend doku https://matplotlib.org/api/_as_gen/matplotlib.axes.Axes.legend.html#matplotlib-axes-axes-legend
axis.legend(loc=7)   # best is 0, 7 is upper right corner
# axis.legend()
# place outside of plot
# axis.legend(bbox_to_anchor=(1,1), loc="upper left")
axis.grid()

plt.show()
