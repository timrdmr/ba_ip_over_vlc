#!/usr/bin/env python3

import matplotlib.pyplot as plt
import math
import os

from measurements import LatencyMeasurement

# path to store measurements
measurement_path = "/home/tim/Bachelorarbeit/Messungen/disturbing_light/"
files_and_light_condition = {
    "Open\n Window":"latency_2021-03-31T15-04-18_100b_over120s_every100ms_30kbps_0_43_V_ref_open_window.csv",
    "Closed\n Window":"latency_2021-03-31T15-15-34_100b_over120s_every100ms_30kbps_0_43_V_ref_closed_window.csv",
    "Half Covered\n Window":"latency_2021-03-31T15-21-27_100b_over120s_every100ms_30kbps_0_43_V_ref_half_covered_window.csv",
    "Darkness":"latency_2021-03-31T15-27-17_100b_over120s_every100ms_30kbps_0_43_V_ref_darkness.csv",
    "No Sunlight,\n LED Ceiling Light":"latency_2021-03-31T15-30-47_100b_over120s_every100ms_30kbps_0_43_V_ref_no_sunlight_led_deckenlampe.csv"
}

x_light_condition = []
y_reliability_udp = []
y_reliability_link = []
payload_size_bytes = 0
interval_us = 0
distance_cm = 0
for elem in files_and_light_condition:
    l = LatencyMeasurement()
    result = l.read_measurement_from_file(measurement_path + files_and_light_condition[elem])
    assert result != None, "parsing error"

    assert (payload_size_bytes == 0 or payload_size_bytes == l.get_payload_size()), "measurements with different payload sizes"
    assert (interval_us == 0 or interval_us == l.get_interval_us()), "measurements with different interval"
    assert (distance_cm == 0 or distance_cm == l.get_distance_cm()), "measurements with different distance"
    payload_size_bytes = l.get_payload_size()
    interval_us = l.get_interval_us()
    distance_cm = l.get_distance_cm()

    y_reliability_udp.append(l.get_reliability_udp())
    y_reliability_link.append(l.get_reliability_link())

    x_light_condition.append(elem)

print(x_light_condition)
print(y_reliability_link)
print(y_reliability_udp)

# plot
plt.xlabel("Light Condition")
plt.ylabel("Packet Delivery Rate [0..1]")

print("x_light_condition: " + str(x_light_condition))
print("y_reliability_udp " + str(y_reliability_udp))
print("y_reliability_link " + str(y_reliability_link))

plt.bar(
    x_light_condition,
    y_reliability_link, 
    label="Link Layer",
)

# plt.bar(
#     x_light_condition,
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
