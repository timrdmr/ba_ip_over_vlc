import matplotlib.pyplot as plt
import math
import os

from measurements import LatencyMeasurement

comperator_ref_voltage = 0.2

# path to store measurements
measurement_base_path = "/home/tim/Bachelorarbeit/Messungen/"

# 15 degree

measurement_path_15degree = measurement_base_path + f"distance_{comperator_ref_voltage}V_15degree/"
files_15degree = os.listdir(measurement_path_15degree)
files_15degree = sorted(files_15degree)

if "measurement.txt" in files_15degree:
    files_15degree.remove("measurement.txt")

print(files_15degree)

x_distance_15degree = []
y_reliability_udp_15_degree = []
payload_size_bytes = 0
interval_us = 0
distance_cm = 0
for file_name in files_15degree:
    l = LatencyMeasurement()
    result = l.read_measurement_from_file(measurement_path_15degree + file_name)
    assert result != None, "parsing error"

    assert (payload_size_bytes == 0 or payload_size_bytes == l.get_payload_size()), "measurements with different payload sizes"
    assert (interval_us == 0 or interval_us == l.get_interval_us()), "measurements with different interval"
    payload_size_bytes = l.get_payload_size()
    interval_us = l.get_interval_us()
    distance_cm = l.get_distance_cm()

    y_reliability_udp_15_degree.append(l.get_reliability_udp())

    x_distance_15degree.append(l.get_distance_cm())

# 120 degree

measurement_path_120degree = measurement_base_path + f"distance_{comperator_ref_voltage}V_120degree/"
files_120degree = os.listdir(measurement_path_120degree)
files_120degree = sorted(files_120degree)

if "measurement.txt" in files_120degree:
    files_120degree.remove("measurement.txt")

x_distance_120degree = []
y_reliability_udp_120_degree = []
for file_name in files_120degree:
    l = LatencyMeasurement()
    result = l.read_measurement_from_file(measurement_path_120degree + file_name)
    assert result != None, "parsing error"

    assert (payload_size_bytes == 0 or payload_size_bytes == l.get_payload_size()), "measurements with different payload sizes"
    assert (interval_us == 0 or interval_us == l.get_interval_us()), "measurements with different interval"
    payload_size_bytes = l.get_payload_size()
    interval_us = l.get_interval_us()
    distance_cm = l.get_distance_cm()

    y_reliability_udp_120_degree.append(l.get_reliability_udp())

    x_distance_120degree.append(l.get_distance_cm())


# plot
# fig, axis = plt.subplots()
plt.xlabel("Distance [in cm]")
plt.ylabel("Packet Delivery Rate [0..1]")

plt.plot(
    x_distance_15degree,
    y_reliability_udp_15_degree,
    label="15 degree",
    marker='.'
)

plt.plot(
    x_distance_120degree,
    y_reliability_udp_120_degree,
    label="120 degree",
    marker='.'
)

plt.title(f"UDP Packet Delivery Rate for different distances and LED emitting angles\nat an interval of {interval_us / 1000} ms, {payload_size_bytes} bytes payload and {comperator_ref_voltage} V comperator referenz voltage")
# legend doku https://matplotlib.org/api/_as_gen/matplotlib.axes.Axes.legend.html#matplotlib-axes-axes-legend
plt.legend(loc=0)   # best is 0, 7 is upper right corner
# axis.legend()
# place outside of plot
# axis.legend(bbox_to_anchor=(1,1), loc="upper left")
plt.grid()

plt.show()
