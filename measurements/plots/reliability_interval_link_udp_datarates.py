#!/usr/bin/env python3
import matplotlib.pyplot as plt

import os
from measurements import LatencyMeasurement

measurement_base_path = "/home/tim/Bachelorarbeit/Messungen/latency_interval_"

datarate = 30 #kbit/s

measurement_path = measurement_base_path + str(datarate) + "kbps_crc/"
files = os.listdir(measurement_path)
files = sorted(files)

if "measurement.txt" in files:
    files.remove("measurement.txt")

x_interval = []
y_reliability_udp = []
y_reliability_link = []

payload_size_bytes = 0
distance_cm = 0
for file_name in files:
    l = LatencyMeasurement()
    result = l.read_measurement_from_file(measurement_path + file_name)
    assert result != None, "parsing error"

    assert (payload_size_bytes == 0 or payload_size_bytes == l.get_payload_size()), "measurements with different payload sizes"
    assert (distance_cm == 0 or distance_cm == l.get_distance_cm()), "measurements with different distances"

    x_interval.append(l.get_interval_us()/1000)

    y_reliability_udp.append(l.get_reliability_udp())
    y_reliability_link.append(l.get_reliability_link())

# plot

plt.xlabel("Interval [in ms]")
plt.ylabel("Packet Delivery Rate [0..1]")

plt.plot(
    x_interval,
    y_reliability_link,
    label=str(datarate) + " kbit/s Link Layer",
    marker='.'
)

plt.plot(
    x_interval,
    y_reliability_udp,
    label=str(datarate) + " kbit/s UDP Layer",
    marker='.'
)

plt.title("Data rate of " + str(datarate) + " kbit/s")
plt.legend()
plt.grid()
plt.show()
