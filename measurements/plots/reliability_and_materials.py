#!/usr/bin/env python3

import matplotlib.pyplot as plt
import math
import os

from measurements import LatencyMeasurement

# path to store measurements
measurement_path = "/home/tim/Bachelorarbeit/Messungen/reliability_and_materials/"
files_and_material = {
    "no material":"latency_2021-03-22T21-05-18_100b_over120s_every150ms_10kbps_0_layer_plexiglas.csv",
    "2 mm plexiglas":"latency_2021-03-22T21-08-55_100b_over120s_every150ms_10kbps_1_layer_plexiglas.csv",
    "4 mm plexiglas":"latency_2021-03-22T21-12-33_100b_over120s_every150ms_10kbps_2_layer_plexiglas.csv",
    "6 mm plexiglas":"latency_2021-03-22T21-17-22_100b_over120s_every150ms_10kbps_3_layer_plexiglas.csv",
    "8 mm plexiglas":"latency_2021-03-22T21-19-13_100b_over120s_every150ms_10kbps_4_layer_plexiglas.csv",
    "paper":"latency_2021-03-22T21-26-06_100b_over120s_every150ms_10kbps_paper.csv" 
}

x_material = []
y_reliability_udp = []
y_reliability_link = []
payload_size_bytes = 0
interval_us = 0
distance_cm = 0
for elem in files_and_material:
    l = LatencyMeasurement()
    result = l.read_measurement_from_file(measurement_path + files_and_material[elem])
    assert result != None, "parsing error"

    assert (payload_size_bytes == 0 or payload_size_bytes == l.get_payload_size()), "measurements with different payload sizes"
    assert (interval_us == 0 or interval_us == l.get_interval_us()), "measurements with different interval"
    assert (distance_cm == 0 or distance_cm == l.get_distance_cm()), "measurements with different distance"
    payload_size_bytes = l.get_payload_size()
    interval_us = l.get_interval_us()
    distance_cm = l.get_distance_cm()

    y_reliability_udp.append(l.get_reliability_udp())
    y_reliability_link.append(l.get_reliability_link())

    x_material.append(elem)

print(x_material)
print(y_reliability_link)
print(y_reliability_udp)

# plot
plt.xlabel("Material")
plt.ylabel("Packet Delivery Rate [0..1]")

print("x_material: " + str(x_material))
print("y_reliability_udp " + str(y_reliability_udp))
print("y_reliability_link " + str(y_reliability_link))

plt.bar(
    x_material,
    y_reliability_link, 
    label="Link Layer",
)

# plt.bar(
#     x_material,
#     y_reliability_udp, 
#     label="UDP",
# )

# plt.title(f"Packet Delivery Rate for different materials exactly between the line of sight\nat {distance_cm} cm distance, interval of {interval_us / 1000} ms and {payload_size_bytes} bytes payload")
# legend doku https://matplotlib.org/api/_as_gen/matplotlib.axes.Axes.legend.html#matplotlib-axes-axes-legend
plt.legend(loc=0)   # best is 0, 7 is upper right corner
# axis.legend()
# place outside of plot
# axis.legend(bbox_to_anchor=(1,1), loc="upper left")

plt.show()
