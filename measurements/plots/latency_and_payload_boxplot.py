#!/usr/bin/env python3

import matplotlib.pyplot as plt
import math
import os
import numpy as np

from measurements import LatencyMeasurement

link_payload_overhead = 13 + 1.5
data_rate = 30000

# path to store measurements
measurement_path = "/Users/tim/iCloudDrive/UNI/6. Semester/Bachelorarbeit/Messungen/latency_and_payload_long_term/"

files = os.listdir(measurement_path)
files = sorted(files)
# files = files[1:]
if "measurement.txt" in files:
    files.remove("measurement.txt")

print(files)


if "measurement.txt" in files:
    files.remove("measurement.txt")

print(files)

x_payload_udp = []
y_reliability_link_average = []
y_reliability_link = []
y_reliability_udp = []

distance_cm = 0
for file_name in files:
    l = LatencyMeasurement()
    result = l.read_measurement_from_file(measurement_path + file_name)
    assert result != None, "parsing error"

    assert (distance_cm == 0 or distance_cm == l.get_distance_cm()), "measurements with different distances"

    payload_size_bytes_udp = l.get_payload_size()
    interval_us = l.get_interval_us()
    distance_cm = l.get_distance_cm()

    y_reliability_link_average.append(l.get_average_link_latency())
    y_reliability_link.append(l.get_link_latency_axis()[1])
    y_reliability_udp.append(l.get_udp_latency_axis()[1])

    x_payload_udp.append(payload_size_bytes_udp)

# plot
# fig, axis = plt.subplots()
plt.ylabel("UDP Layer Payload Size [in byte]")
plt.xlabel("Latency [in ms]")

# box plot
bplot_link = plt.boxplot(
    y_reliability_link,
    positions=x_payload_udp,
    showfliers=False,   # Ausreißer
    vert=False,
    widths=2
)

bplot_udp = plt.boxplot(
    y_reliability_udp,
    positions=x_payload_udp,
    showfliers=False,
    vert=False,
    widths=2,
    boxprops=dict(color="blue"),
    capprops=dict(color="blue"),
    whiskerprops=dict(color="blue"),
    flierprops=dict(color="blue"),
)


# only show max and min flieres
# source: https://stackoverflow.com/questions/28521828/matplotlib-boxplot-show-only-max-and-min-fliers
fliers_link = bplot_link['fliers']
for f in fliers_link:
    data = f.get_data()
    f.set_data([data[0][0],data[0][-1]],[data[1][0],data[1][-1]])
fliers_udp = bplot_udp['fliers']
for f in fliers_udp:
    data = f.get_data()
    f.set_data([data[0][0],data[0][-1]],[data[1][0],data[1][-1]])

# bplot_udp['props'] = dict(color="blue")

#plt.title(f"UDP Packet Delivery Rate for different datarates\nwith {payload_size_bytes} bytes UDP payload")
# legend doku https://matplotlib.org/api/_as_gen/matplotlib.axes.Axes.legend.html#matplotlib-axes-axes-legend
# plt.legend(loc=0)   # best is 0, 7 is upper right corner
# axis.legend()
# place outside of plot
# axis.legend(bbox_to_anchor=(1,1), loc="upper left")
plt.grid()

plt.show()
