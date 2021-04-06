import matplotlib.pyplot as plt
import math
import numpy as np

max_time = 150

incoming_signal_width = 27.36
rise_time = 9.44
fall_time = 19.8

## incoming signal ##

x_incoming = []
y_incoming = []
edge = 0
for i in np.arange(0, max_time, incoming_signal_width):
    # add two elements for each data point
    x_incoming.append(i)
    x_incoming.append(i + incoming_signal_width)
    y_incoming.append(edge)
    y_incoming.append(edge)

    if (edge == 0):
        edge = 1
    else:
        edge = 0

print(x_incoming)
print(y_incoming)

## interrupt signal ##
x_interrupt = [0] * (len(x_incoming))
y_interrupt = y_incoming[:]
edge = 0
for i in range(1, len(x_incoming) - 1, 2):
    if (edge == 0):
        x_interrupt[i] = x_incoming[i] + rise_time
        x_interrupt[i+1] = x_incoming[i] + rise_time
        edge = 1

    else:
        x_interrupt[i] = x_incoming[i+1] + fall_time
        x_interrupt[i+1] = x_incoming[i+1] + fall_time
        edge = 0

x_interrupt = x_interrupt[:-1]
y_interrupt = y_interrupt[:-1]
print((x_interrupt))
print((y_interrupt))

y_interrupt = list(map(lambda x: x + 0.01, y_interrupt))

## plot ##

fig = plt.figure()
axis = fig.add_subplot(1,1,1)

plt.xlabel("Time [in $\mu s$]")
plt.ylabel("Digital Signal")

plt.plot(
    x_interrupt,
    y_interrupt,
    label="Interrupt Signal",
)

plt.plot(
    x_incoming,
    y_incoming,
    label="Incoming Signal",
    #ls='--'
)

plt.yticks([0,1], labels=["Low", "High"])
axis.set_xticks(range(0, max_time, 5), minor=True)
axis.set_xticks(range(0, max_time, 20), minor=False)

plt.title("Calculation of the receiver response to an incoming signal")
# legend doku https://matplotlib.org/api/_as_gen/matplotlib.axes.Axes.legend.html#matplotlib-axes-axes-legend
plt.legend(loc=7)   # best is 0, 7 is upper right corner
# axis.legend()
# place outside of plot
# axis.legend(bbox_to_anchor=(1,1), loc="upper left")

axis.grid(which='minor', alpha=5)
axis.grid(which='major', alpha=50)

plt.show()
