#!/usr/bin/env python3

import matplotlib.pyplot as plt
import math
import os
import numpy as np

from measurements import LatencyMeasurement

data_rate = 30000

# path to store measurements
measurement_path = "/home/tim/Bachelorarbeit/Messungen/reliability_and_payload/"

files = os.listdir(measurement_path)
files = sorted(files)

if "measurement.txt" in files:
    files.remove("measurement.txt")

print(files)

x_payload_udp = []
y_reliability_udp = []
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

    y_reliability_udp.append(l.get_reliability_udp())
    y_reliability_link.append(l.get_reliability_link())

    x_payload_udp.append(payload_size_bytes_udp)


# plot
# fig, axis = plt.subplots()
plt.xlabel("UDP Payload Size [in byte]")
plt.ylabel("Package Delivery Rate [in ms]")

plt.plot(
    x_payload_udp,
    y_reliability_link,
    label="Link",
    #marker='.',
    #ls=''
)

plt.plot(
    x_payload_udp,
    y_reliability_udp,
    label="UDP",
    #marker='.',
    #ls=''
)

plt.legend(loc=0)   # best is 0, 7 is upper right corner

plt.grid()

plt.show()
