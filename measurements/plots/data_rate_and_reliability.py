#!/usr/bin/env python3

import matplotlib.pyplot as plt
import math
import os
import numpy as np

from measurements import LatencyMeasurement


# path to store measurements
measurement_path = "/home/tim/Bachelorarbeit/Messungen/datarate_and_reliability_more_runs/"

files = os.listdir(measurement_path)
files = sorted(files)

if "measurement.txt" in files:
    files.remove("measurement.txt")

print(files)

x_datarate = []
y_reliability_link = []
y_reliability_udp = []

payload_size_bytes = 0
interval_us = 0
distance_cm = 0
for file_name in files:
    l = LatencyMeasurement()
    result = l.read_measurement_from_file(measurement_path + file_name)
    assert result != None, "parsing error"

    assert (payload_size_bytes == 0 or payload_size_bytes == l.get_payload_size()), "measurements with different payload sizes"
    assert (distance_cm == 0 or distance_cm == l.get_distance_cm()), "measurements with different distances"

    payload_size_bytes = l.get_payload_size()
    interval_us = l.get_interval_us()
    distance_cm = l.get_distance_cm()

    y_reliability_udp.append(l.get_reliability_udp())
    y_reliability_link.append(l.get_reliability_link())

    datarate = int(file_name.split("_")[5][0:-3])

    x_datarate.append(datarate/1000)

# plot
# fig, axis = plt.subplots()
plt.xlabel("Datarate [in kbit/s]")
plt.ylabel("Packet Delivery Rate [0..1]")

plt.plot(
    x_datarate,
    y_reliability_link,
    label="Link",
    marker='.'
)

plt.plot(
    x_datarate,
    y_reliability_udp,
    label="UDP",
    marker='.'
)

plt.yticks(np.arange(0, 1.2, 0.1))

#plt.title(f"UDP Packet Delivery Rate for different datarates\nwith {payload_size_bytes} bytes UDP payload")
# legend doku https://matplotlib.org/api/_as_gen/matplotlib.axes.Axes.legend.html#matplotlib-axes-axes-legend
plt.legend(loc=0)   # best is 0, 7 is upper right corner
# axis.legend()
# place outside of plot
# axis.legend(bbox_to_anchor=(1,1), loc="upper left")
plt.grid()

plt.show()
