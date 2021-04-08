import matplotlib.pyplot as plt
from mpl_toolkits.axisartist.parasite_axes import HostAxes, ParasiteAxes

from measurements import LatencyMeasurement

# path of measurement files
measurement_path = "/home/tim/Bachelorarbeit/Messungen/latency/"
file = "latency_2021-03-28T17-46-56_100b_over300s_every130ms_30kbps_0_43_V_ref.csv"

# for reliability
bin_size_s = 5

# read measurement
runtime_us = 0
payload_size_bytes = 0
interval_us = 0
l = LatencyMeasurement()
measurements_list = l.read_measurement_from_file(measurement_path + file)
assert measurements_list != None, "measurement failed"

runtime_us = l.get_runtime_us()
payload_size_bytes = l.get_payload_size()
interval_us = l.get_interval_us()

x_udp_pkt_time_s, y_udp_pkt_latency_ms = l.get_udp_latency_axis()
y_reliability_per_bin_udp = l.get_reliability_udp_per_time(bin_size_s=bin_size_s)
x_bin_time_reliability_udp_s = [i*bin_size_s for i in range(len(y_reliability_per_bin_udp))]

y_reliability_per_bin_link = l.get_reliability_link_per_time(bin_size_s=bin_size_s)
x_bin_time_reliability_link_s = [i*bin_size_s for i in range(len(y_reliability_per_bin_link))]

# plot
fig = plt.figure()
#                           [left, bottom, width, height]
latency_axis = HostAxes(fig,[0.15, 0.1, 0.65, 0.8])
reliability_axis = ParasiteAxes(latency_axis, sharex=latency_axis)
latency_axis.parasites.append(reliability_axis)

latency_axis.axis["right"].set_visible(False)
reliability_axis.axis["right"].set_visible(True)
reliability_axis.axis["right"].major_ticklabels.set_visible(True)
reliability_axis.axis["right"].label.set_visible(True)

fig.add_axes(latency_axis)

plt_latency, = latency_axis.plot(x_udp_pkt_time_s, y_udp_pkt_latency_ms, label="Latency UDP", ls=None, marker=".")
plt_reliability, = reliability_axis.plot(x_bin_time_reliability_udp_s, y_reliability_per_bin_udp, label="Reliability UDP")
reliability_axis.plot(x_bin_time_reliability_link_s, y_reliability_per_bin_link, color=plt_reliability.get_color(), label="Reliability Link Layer", ls="--")

latency_axis.set_xlabel("Package Send Time [in s]")
latency_axis.set_ylabel("Latency [in ms]")
reliability_axis.set_ylabel(f"Reliability in time intervals of {bin_size_s}s [0..1]")

reliability_axis.set_ylim(0,1.05)    # leave some space in case of 100% reliability

latency_axis.legend()

latency_axis.axis["left"].label.set_color(plt_latency.get_color())
reliability_axis.axis["right"].label.set_color(plt_reliability.get_color())

latency_axis.grid(color=plt_latency.get_color())

plt.title("VLC Latency and Reliability\nPackages with size of {size_pkt} byte every {interval} ms".format(
    size_pkt=payload_size_bytes,
    interval=int(interval_us/1000)
))

plt.show()
