#!/usr/bin/env python3

import matplotlib.pyplot as plt
import math
import os
import numpy as np

from measurements import LatencyMeasurement

link_payload_overhead = 13 + 1.5
data_rate = 30000

# path to store measurements
measurement_path = "/Users/tim/iCloudDrive/UNI/6. Semester/Bachelorarbeit/Messungen/latency_and_payload/"

files = os.listdir(measurement_path)
files = sorted(files)

if "measurement.txt" in files:
    files.remove("measurement.txt")

print(files)

x_payload_link = []
y_reliability_link_average = []
y_reliability_link_min = []
y_reliability_link = []

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
    y = l.get_link_latency_axis()[1]
    y_reliability_link.append(y)
    y_reliability_link_min.append(min(y))

    x_payload_link.append(payload_size_bytes_udp + 8 + 40)

# expected transmission delay
def expected_transmission_delay(link_payload_size_bytes, data_rate_bitps):
    return ((link_payload_size_bytes + link_payload_overhead) / (data_rate_bitps / 8)) * 1000

y_expected_delay = [expected_transmission_delay(x, data_rate) for x in x_payload_link]

# plot
# fig, axis = plt.subplots()
plt.xlabel("UDP Layer Payload Size [in byte]")
plt.ylabel("Time [in ms]")

plt.plot(
    x_payload_link,
    y_reliability_link_min,
    label="Measured Minimum Link Layer Latency",
    marker='.',
    ls=''
)

plt.plot(
    x_payload_link,
    y_reliability_link_average,
    label="Measured Average Link Layer Latency",
    marker=''
)

plt.plot(
    x_payload_link,
    y_expected_delay,
    label="Expected Transmission Delay",
    marker=''
)

# box plot
# figure = plt.figure()
# axes = figure.add_axes([0,0,1,1])
# bplot = plt.boxplot(y_reliability_link, positions=x_payload_link, showfliers=True, widths=5)
# axes.boxplot()

# plt.xticks(ticks=range(0, 1100, 100))

# only show max and min flieres
# source: https://stackoverflow.com/questions/28521828/matplotlib-boxplot-show-only-max-and-min-fliers
# fliers = bplot['fliers']
# for f in fliers:
#     data = f.get_data()
#     if data[0] != []:
#         f.set_data([data[0][0],data[0][-1]],[data[1][0],data[1][-1]])


#plt.title(f"UDP Packet Delivery Rate for different datarates\nwith {payload_size_bytes} bytes UDP payload")
# legend doku https://matplotlib.org/api/_as_gen/matplotlib.axes.Axes.legend.html#matplotlib-axes-axes-legend
plt.legend(loc=0)   # best is 0, 7 is upper right corner
# axis.legend()
# place outside of plot
# axis.legend(bbox_to_anchor=(1,1), loc="upper left")
plt.grid()

plt.show()
