#!/usr/bin/env python3

import matplotlib.pyplot as plt
import math
import os
import numpy as np

from measurements import LatencyMeasurement


# path to store measurements
measurement_path = "/home/tim/Bachelorarbeit/Messungen/datarate_and_reliability_0_43V_better_reliability/"

files = os.listdir(measurement_path)
files = sorted(files)

if "measurement.txt" in files:
    files.remove("measurement.txt")

print(files)

x_datarate = []
y_throughput_link = []
y_throughput_udp = []

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

    y_throughput_udp.append(l.get_average_throughput_udp()/1000)
    y_throughput_link.append(l.get_average_throughput_link()/1000)

    datarate = int(file_name.split("_")[5][0:-3])

    x_datarate.append(datarate/1000)

def expected_transmission_time(data_rate_bitps, payload_size_bytes, overhead_bytes=62.5):
    return (payload_size_bytes + overhead_bytes) * 8 / data_rate_bitps

def expected_throughput_udp(delay_ms, data_rate_bitps, payload_size_bytes_udp):
    expected_transmission_delay = expected_transmission_time(data_rate_bitps, payload_size_bytes_udp)
    expected_time_per_packet_s = (delay_ms / 1000) + expected_transmission_delay
    num_udp_packages_per_s = 1 / expected_time_per_packet_s

    throughput_bitps = num_udp_packages_per_s * payload_size_bytes_udp * 8

    return throughput_bitps

def expected_throughput_link(delay_ms, data_rate_bitps, payload_size_bytes):
    expected_transmission_delay = expected_transmission_time(data_rate_bitps, payload_size_bytes, overhead_bytes=14.5)
    expected_time_per_packet_s = (delay_ms / 1000) + expected_transmission_delay
    num_packages_per_s = 1 / expected_time_per_packet_s

    throughput_bitps = num_packages_per_s * payload_size_bytes * 8

    return throughput_bitps

y_udp_throughput_calc = [expected_throughput_udp(25, data_rate*1000, payload_size_bytes) / 1000 for data_rate in x_datarate]
y_link_throughput_calc = [expected_throughput_link(25, data_rate*1000, payload_size_bytes + 48) / 1000 for data_rate in x_datarate]

# plot
# fig, axis = plt.subplots()
plt.xlabel("Datarate [in kbit/s]")
plt.ylabel("Throughput [in kbit/s]")

plt.plot(
    x_datarate,
    y_throughput_link,
    label="Link",
    marker='.',
    color='C0'
)

plt.plot(
    x_datarate,
    y_link_throughput_calc,
    label="Expected Link",
    marker='',
    ls='dotted',
    color='C0'
)

plt.plot(
    x_datarate,
    y_throughput_udp,
    label="UDP",
    marker='.',
    color='C1'
)

plt.plot(
    x_datarate,
    y_udp_throughput_calc,
    label="Expected UDP",
    marker='',
    ls='dotted',
    color='C1'
)

#plt.title(f"UDP Packet Delivery Rate for different datarates\nwith {payload_size_bytes} bytes UDP payload")
# legend doku https://matplotlib.org/api/_as_gen/matplotlib.axes.Axes.legend.html#matplotlib-axes-axes-legend
plt.legend(loc=0)   # best is 0, 7 is upper right corner
# axis.legend()
# place outside of plot
# axis.legend(bbox_to_anchor=(1,1), loc="upper left")
plt.grid()

plt.show()

