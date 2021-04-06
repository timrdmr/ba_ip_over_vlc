import matplotlib.pyplot as plt
import math
import os

from measurements import LatencyMeasurement

# path to store measurements
measurement_path = "/home/tim/Bachelorarbeit/Messungen/receiver_tolerance_crc/"
files = os.listdir(measurement_path)
files = sorted(files)

print(files)

x_tolerance = []
y_reliability_udp = []
y_reliability_link = []
payload_size_bytes = 0
interval_us = 0
distance_cm = 0
for file_name in files:
    l = LatencyMeasurement()
    result = l.read_measurement_from_file(measurement_path + file_name)
    assert result != None, "parsing error"

    assert (payload_size_bytes == 0 or payload_size_bytes == l.get_payload_size()), "measurements with different payload sizes"
    assert (interval_us == 0 or interval_us == l.get_interval_us()), "measurements with different interval"
    assert (distance_cm == 0 or distance_cm == l.get_distance_cm()), "measurements with different interval"
    payload_size_bytes = l.get_payload_size()
    interval_us = l.get_interval_us()
    distance_cm = l.get_distance_cm()

    y_reliability_udp.append(l.get_reliability_udp())
    y_reliability_link.append(l.get_reliability_link())

    # file name ends with: _rtol<number>.csv
    x_tolerance.append(int(file_name[-6:-4])/100)

# plot
# fig, axis = plt.subplots()
plt.xlabel("Tolerance [0 .. 1]")
plt.ylabel("Packet Delivery Rate [0..1]")

print("x_tolerance: " + str(x_tolerance))
print("y_reliability_udp " + str(y_reliability_udp))
print("y_reliability_link " + str(y_reliability_link))

plt.plot(
    x_tolerance,
    y_reliability_link, 
    label="Link Layer",
    marker='.'
)

plt.plot(
    x_tolerance,
    y_reliability_udp, 
    label="UDP",
    marker='.'
)

# plt.title(f"Packet Delivery Rate for different receiver tolerance values\nat {distance_cm} cm distance, interval of {interval_us / 1000} ms and {payload_size_bytes} bytes payload")
# legend doku https://matplotlib.org/api/_as_gen/matplotlib.axes.Axes.legend.html#matplotlib-axes-axes-legend
plt.legend(loc=0)   # best is 0, 7 is upper right corner
# axis.legend()
# place outside of plot
# axis.legend(bbox_to_anchor=(1,1), loc="upper left")
plt.grid()

plt.show()
