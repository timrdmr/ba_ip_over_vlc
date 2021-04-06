import matplotlib.pyplot as plt
import math

from measurements import LatencyMeasurement

# path to store measurements
measurement_path = "/home/tim/Bachelorarbeit/Messungen/latency/"
files = [
    # "latency_2021-02-19T10-25-23_100b_over300s_every500ms.csv",
    # "latency_2021-02-19T10-18-09_100b_over300s_every135ms.csv",
    # "latency_2021-02-19T09-34-38_100b_over300s_every130ms.csv",
    # "latency_2021-02-19T10-33-40_100b_over300s_every100ms.csv",
    # "latency_2021-02-19T10-40-36_100b_over300s_every50ms.csv",
    # "latency_2021-02-19T10-47-00_100b_over300s_every0ms.csv",
    "latency_2021-03-25T09-09-19_100b_over30s_every0ms_30kbps_0_43_V_ref.csv"
]
bin_size_s = 5

# plot
fig, axis = plt.subplots()
plt.xlabel("time [in s]")
plt.ylabel("Packet Delivery Rate [0..1]")
payload_size_bytes = 0
for file_name in files:
    l = LatencyMeasurement()
    result = l.read_measurement_from_file(measurement_path + file_name)
    assert result != None, "parsing error"

    interval_us = l.get_interval_us()
    assert (payload_size_bytes == 0 or payload_size_bytes == l.get_payload_size()), "measurements with different payload sizes"
    payload_size_bytes = l.get_payload_size()

    y_reliability_per_bin_link = l.get_reliability_link_per_time(bin_size_s=bin_size_s)

    axis.plot(
        [i*bin_size_s for i in range(len(y_reliability_per_bin_link))],
        y_reliability_per_bin_link, 
        label="Link Layer, send interval of " + str(round(interval_us / 1000)) + "ms",
    )

plt.title(f"Link Layer Packet Delivery Rate (UDP {payload_size_bytes} byte payload) with binsize of {bin_size_s} s and 0.5cm distance")
# legend doku https://matplotlib.org/api/_as_gen/matplotlib.axes.Axes.legend.html#matplotlib-axes-axes-legend
axis.legend(loc=7)   # best is 0, 7 is upper right corner
# axis.legend()
# place outside of plot
# axis.legend(bbox_to_anchor=(1,1), loc="upper left")
axis.grid()

plt.show()
