import matplotlib.pyplot as plt

from measurements import LatencyMeasurement

# path to store measurements
measurement_path = "/home/tim/Bachelorarbeit/Messungen/latency/"

runtime_us = 0
payload_size_bytes = 0
interval_us = 0
l = LatencyMeasurement()
measurements_list = l.read_measurement_from_file(measurement_path + "latency_2021-03-30T09-58-03_100b_over300s_every200ms_30kbps_0_43_V_ref.csv")
assert measurements_list != None, "measurement failed"
print("Distance: " + str(l.get_distance_cm()))

runtime_us = l.get_runtime_us()
payload_size_bytes = l.get_payload_size()
interval_us = l.get_interval_us()

limit = 150     # -1 for no limit
x_udp_pkt_time_s, y_udp_pkt_latency_ms = l.get_udp_latency_axis(limit=limit)
x_link_pkt_time_s, y_link_pkt_latency_ms = l.get_link_latency_axis(limit=limit)

# plot
# plt.title("VLC Latency Measurement \nPackages with size of {size_pkt} byte every {interval} ms".format(
#     size_pkt=payload_size_bytes,
#     interval=int(interval_us/1000)
# ))
plt.xlabel("time in s")
plt.ylabel("latency in ms")
plt.plot(x_udp_pkt_time_s, y_udp_pkt_latency_ms, label="UDP")
plt.plot(x_link_pkt_time_s, y_link_pkt_latency_ms, label="Link Layer")
plt.grid()
plt.legend()
# average_latency_udp = l.get_average_udp_latency()
# if average_latency_udp > 0:
#     plt.plot(x_udp_pkt_time_s, [average_latency_udp for _ in range(len(x_udp_pkt_time_s))])
# average_latency_link = l.get_average_link_latency()
# if average_latency_link > 0:
#     plt.plot(x_link_pkt_time_s, [average_latency_link for _ in range(len(x_link_pkt_time_s))])

print("Reliability UDP: " + str(l.get_reliability_udp()))
print("Reliability link layer: " + str(l.get_reliability_link()))
print("Average UDP latency: " + str(l.get_average_udp_latency()))
print("Average link latency: " + str(l.get_average_link_latency()))

plt.show()
