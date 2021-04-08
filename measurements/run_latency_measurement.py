import matplotlib.pyplot as plt

from measurements import LatencyMeasurement, LatencyMeasurementData

total_run_time_s = 120
payload_size_bytes = 100
interval_us = 100 * 1000
distance = 0.5    #cm

l = LatencyMeasurement(runtime_us=total_run_time_s*1000000, payload_size_bytes=payload_size_bytes, interval_us=interval_us, distance_cm=distance, random_payload=True)
measurements_list = l.run()
assert measurements_list != None, "measurement failed"
datarate = "30"  #kbit/s
l.write_measurement_to_file(subfolder="disturbing_light", file_name_note=datarate + "kbps_0_43_V_ref")

x_udp_pkt_time_s, y_udp_pkt_latency_ms = l.get_udp_latency_axis()
x_link_pkt_time_s, y_link_pkt_latency_ms = l.get_link_latency_axis()

# plot
plt.title("VLC Latency Measurement \nPackages with size of {size_pkt} byte every {interval} ms".format(
    size_pkt=payload_size_bytes,
    interval=int(interval_us/1000)
))
plt.xlabel("time in s")
plt.ylabel("latency in ms")
plt.plot(x_udp_pkt_time_s, y_udp_pkt_latency_ms, label="UDP")
plt.plot(x_link_pkt_time_s, y_link_pkt_latency_ms, label="Link Layer", marker='.')
plt.legend()
# average_latency_udp = l.get_average_udp_latency()
# if average_latency_udp > 0:
#     plt.plot(x_udp_pkt_time_s, [average_latency_udp for _ in range(len(x_udp_pkt_time_s))])
# average_latency_link = l.get_average_link_latency()
# if average_latency_link > 0:
#     plt.plot(x_link_pkt_time_s, [average_latency_link for _ in range(len(x_link_pkt_time_s))])

print("Reliability UDP: " + str(l.get_reliability_udp()))
print("Reliability link layer: " + str(l.get_reliability_link()))

plt.show()
