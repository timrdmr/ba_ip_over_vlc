from serial import Serial
from threading import Thread, Lock
from time import time
from datetime import datetime
import math

port_sender = "/dev/ttyACM0"
port_receiver = "/dev/ttyACM1"

# path to store measurements
measurement_path = "/home/tim/Bachelorarbeit/Messungen/"

# measurement data of one packet
# -1 marks missing value
class LatencyMeasurementData:
    def __init__(self, pkt_number, udp_send_time_s = -1, udp_latency_ms = -1, link_send_time_s = -1, link_latency_ms = -1):
        self.pkt_number = pkt_number

        # transport layer (UDP)
        self.udp_send_time_s = udp_send_time_s      # relative time of the udp send command
        self.udp_latency_ms = udp_latency_ms        # time from udp send to udp receive

        # link layer
        self.link_send_time_s = link_send_time_s    # relative time of link layer start of send 
        self.link_latency_ms = link_latency_ms      # time from link layer send to link layer receive

    # check if package was received at transport layer 
    def package_received_udp(self):
        return self.udp_latency_ms != -1

    # check if package was received at transport layer 
    def package_received_link_layer(self):
        return self.link_latency_ms != -1

    def is_valid(self):
        if self.pkt_number == None or self.pkt_number < 0:
            print("Measurement data not valid: undefined package number")
            return False

        if self.udp_latency_ms != -1:   # udp package received
            if self.udp_send_time_s == -1:
                print("Measurement data not valid: udp package received but not send")
                return False
            if self.link_send_time_s == -1:
                print("Measurement data not valid: udp package received but not send at link layer")
                return False
            if self.link_latency_ms == -1:
                print("Measurement data not valid: udp package received but no link layer latency")
                return False

        if self.link_latency_ms != -1:   # link layer data received
            if self.udp_send_time_s == -1:
                print("Measurement data not valid: link layer package received but no udp package send")
                return False
            if self.link_send_time_s == -1:
                print("Measurement data not valid: link layer package received but not at link layer")
                return False

        if self.link_latency_ms != -1:   # link layer data send
            if self.udp_send_time_s == -1:
                print("Measurement data not valid: link layer package send but no udp package send")
                return False

        if self.link_send_time_s != -1 and self.link_send_time_s < self.udp_send_time_s:
            print(f"Measurement data not valid: link layer send time < udp send time ({self.link_send_time_s} < {self.udp_send_time_s})")
            return False

        if self.udp_latency_ms != -1 and self.link_latency_ms > self.udp_latency_ms:
            print(f"Measurement data not valid: link layer latency > udp latency ({self.link_latency_ms} > {self.udp_latency_ms})")
            return False

        return True

    # format: pkt_number;udp_send_time_s;link_send_time_s;link_latency_ms;udp_latency_ms
    def csv_line(self):
        return (str(self.pkt_number) + ";"
             + str(self.udp_send_time_s) + ";" + str(self.link_send_time_s) + ";"
             + str(self.link_latency_ms) + ";" + str(self.udp_latency_ms) + "\n")


# serial output markers: <marker> int
#   <marker>
#       su: send udp (before sock_udp_send)
#       sl: send link layer (link layer send method called and payload concatinated)
#       rl: receive link layer (link layer recv method finished)
#       ru: receive udp
#       fu: finish udp send command (all iterations done)
#       rr: receiver ready (setup complete, send can be started)
#       du: drop udp, payload does not match
# NOTE: output serial data takes ~0.5ms on board
class LatencyMeasurement():

    # interval is the delay between each call of send
    # if the payload is not random, the udp payload is dropped if it is not received correctly
    def __init__(self, runtime_us=10*1000000, payload_size_bytes=100, interval_us=1000000, distance_cm=None, random_payload=True):
        self.__runtime_us = runtime_us
        self.__payload_size_bytes = payload_size_bytes
        self.__interval_us = interval_us
        self.__distance_cm = distance_cm
        self.__random_payload = random_payload

        # make sure that server runs before client starts
        self.__init_finished_lock = Lock()
        self.__init_finished_lock.acquire()    # block client

        # number and timestamp of package, needed during measurement
        self.__send_packages_udp_timestamps = {}
        self.__received_packages_udp_timestamps = {}

        self.__send_packages_link_timestamps = {}
        self.__received_packages_link_timestamps = {}

        self.__all_packages_send = False    # used to stop checking for new packages
        self.__receive_timeout = False

        # result of measurement
        self.__result = []

    def get_runtime_us(self):
        return self.__runtime_us

    # payload size in bytes
    def get_payload_size(self):
        return self.__payload_size_bytes

    # interval in us
    def get_interval_us(self):
        return self.__interval_us

    def get_distance_cm(self):
        return self.__distance_cm

    # returns -1 if no packages received, ignore lost packages
    def get_average_udp_latency(self):
        x_udp_pkt_time_s, y_udp_pkt_latency_ms = self.get_udp_latency_axis()
        if len(y_udp_pkt_latency_ms) != 0:
            return sum(y_udp_pkt_latency_ms) / len(x_udp_pkt_time_s)
        return -1

    # returns -1 if no packages received, ignore lost packages
    def get_average_link_latency(self):
        x_link_pkt_time_s, y_link_pkt_latency_ms = self.get_link_latency_axis()
        if len(y_link_pkt_latency_ms) != 0:
            return sum(y_link_pkt_latency_ms) / len(x_link_pkt_time_s)
        return -1

    def get_reliability_udp(self):
        number_send = 0
        number_received = 0
        for m in self.__result:
            if m.udp_send_time_s != -1:
                number_send += 1

                if m.udp_latency_ms != -1:
                    number_received += 1

        assert number_send >= number_send

        return number_received/number_send

    def get_reliability_link(self):
        number_send = 0
        number_received = 0
        for m in self.__result:
            if m.link_send_time_s != -1:
                number_send += 1

                if m.link_latency_ms != -1:
                    number_received += 1

        assert number_send >= number_send

        return number_received/number_send

    # Overhead in bytes compared to the UDP payload size
    # returns bit/s
    def get_average_throughput_link(self, overhead=48):

        runtime_s = self.__runtime_us / 1000000

        payload_send_bits = (self.__payload_size_bytes + overhead) * 8
        number_link_received = 0

        for m in self.__result:
            if m.link_latency_ms > 0:
                number_link_received += 1

        bits_received = number_link_received * payload_send_bits

        return bits_received / runtime_s

    # Overhead in bytes compared to the UDP payload size
    # returns bit/s
    def get_average_throughput_udp(self, overhead=0):
        runtime_s = self.__runtime_us / 1000000

        payload_send_bits = (self.__payload_size_bytes + overhead) * 8
        number_udp_received = 0

        for m in self.__result:
            if m.udp_latency_ms > 0:
                number_udp_received += 1

        bits_received = number_udp_received * payload_send_bits

        return bits_received / runtime_s


    # get reliability per time unit to create a bin plot etc.
    # returns list of reliability per bin, index is the number of bin
    def get_reliability_udp_per_time(self, bin_size_s=5):

        # index is bin number
        measurements_per_bin = []
        for m in self.__result:
            current_bin = math.floor(m.udp_send_time_s/bin_size_s)
            if (len(measurements_per_bin) - 1) < current_bin:
                measurements_per_bin.append(0)
            measurements_per_bin[current_bin] += 1

        reliability_per_bin = []
        for m in self.__result:
            current_bin = math.floor(m.udp_send_time_s/bin_size_s)
            if (len(reliability_per_bin) - 1) < current_bin:
                reliability_per_bin.append(0)

            # check if package received
            if m.udp_latency_ms != -1:
                reliability_per_bin[current_bin] += 1/measurements_per_bin[current_bin]

        return reliability_per_bin

    # get reliability per time unit to create a bin plot etc.
    # returns list of reliability per bin, index is the number of bin
    def get_reliability_link_per_time(self, bin_size_s=5):

        # index is bin number
        measurements_per_bin = []
        for m in self.__result:
            if m.link_send_time_s != -1:
                current_bin = math.floor(m.link_send_time_s/bin_size_s)
                if (len(measurements_per_bin) - 1) < current_bin:
                    measurements_per_bin.append(0)
                measurements_per_bin[current_bin] += 1

        reliability_per_bin = []
        for m in self.__result:
            if m.link_send_time_s != -1:
                current_bin = math.floor(m.link_send_time_s/bin_size_s)
                if (len(reliability_per_bin) - 1) < current_bin:
                    reliability_per_bin.append(0)

                # check if package received
                if m.link_latency_ms != -1:
                    reliability_per_bin[current_bin] += 1/measurements_per_bin[current_bin]

        return reliability_per_bin

    # get x and y axis of udp latency for plotting, ignore lost packages
    # limit: only return data with a smaller link_send_time_s than limit (-1 no limit)
    # -> (x: time in s, y: latency udp in ms)
    def get_udp_latency_axis(self, limit=-1) -> (list, list):
        x_udp_pkt_time_s = []
        y_udp_pkt_latency_ms = []

        for m in self.__result:

            # time limit
            if limit != -1 and m.link_send_time_s > limit:
                return x_udp_pkt_time_s, y_udp_pkt_latency_ms

            if m.udp_latency_ms != -1:
                x_udp_pkt_time_s.append(m.udp_send_time_s)
                y_udp_pkt_latency_ms.append(m.udp_latency_ms)

        return x_udp_pkt_time_s, y_udp_pkt_latency_ms

    # get x and y axis of link latency for plotting, ignore lost packages
    # limit: only return data with a smaller link_send_time_s than limit (-1 no limit)
    # -> (x: time in s, y: latency link in ms)
    def get_link_latency_axis(self, limit=-1) -> (list, list):
        x_link_pkt_time_s = []
        y_link_pkt_latency_ms = []

        for m in self.__result:

            # time limit
            if limit != -1 and m.link_send_time_s > limit:
                return x_link_pkt_time_s, y_link_pkt_latency_ms

            if m.link_latency_ms != -1:
                x_link_pkt_time_s.append(m.link_send_time_s)
                y_link_pkt_latency_ms.append(m.link_latency_ms)

        return x_link_pkt_time_s, y_link_pkt_latency_ms

    def __send_thread_function(self):

        timeout_serial = (self.__interval_us/1000000)*40
        # avoid immediate timeout
        if timeout_serial < 1:
            timeout_serial = 1
        with Serial(port=port_sender, baudrate=115200, timeout=timeout_serial) as s:

            cmd = "udp_latency_client {iter} {bytes} {interv} {random}".format(
                iter=self.__runtime_us,
                bytes=self.__payload_size_bytes,
                interv=self.__interval_us,
                random=str(int(self.__random_payload))
            )
            self.__init_finished_lock.acquire()
            s.write((cmd + '\n').encode('UTF-8'))
            s.flush()

            print("Send: " + cmd + " to " + port_sender)

            while not self.__receive_timeout:
                line = s.readline()
                # check serial timeout
                if (len(line) == 0):
                    print("[ERROR] Sender timed out!")
                    break

                receive_time = time()
                # remove \n
                line = line.decode('UTF-8')[:-1]

                # remove RIOT shell command char '>' after command finishes
                if len(line) >= 2:
                    if line[0] == '>' and line[1] == ' ':
                        line = line[2:]

                print("[" + port_sender + "] " + str(receive_time) + " - " + line)

                # parse line and get package number
                words = line.split(' ')
                if len(words) < 2:
                    print("[WARNING] Cannot parse, too few words")
                    continue

                package_number = None
                try:
                    package_number = int(words[1])
                except ValueError:
                    print("[WARNING] Cannot parse package number")
                    continue

                # udp send
                if words[0] == "su":
                    if package_number in self.__send_packages_udp_timestamps:
                        print("[ERROR] UDP package already send")
                        break
                    self.__send_packages_udp_timestamps[package_number] = receive_time
                # link layer send
                elif words[0] == "sl":
                    if package_number in self.__send_packages_link_timestamps:
                        print("[ERROR] Link layer package already send")
                        # break
                    self.__send_packages_link_timestamps[package_number] = receive_time
                else:
                    print("[WARNING] Cannot parse package number")
                    continue


    def __receive_thread_function(self):
        timeout = self.__interval_us * 40   # miss at most 20 Packages
        # avoid immediate timeout
        if timeout < 5000000:
            timeout = 5000000   # 1 second
        with Serial(port=port_receiver, baudrate=115200, timeout=timeout/1000000) as s:

            cmd = "udp_latency_server " + str(timeout) + " " + str(self.__payload_size_bytes) + " " + str(int(self.__random_payload))
            s.write((cmd + '\n').encode('UTF-8'))
            s.flush()
            print("Send: " + cmd + " to " + port_receiver)

            print("Waiting for response")

            # NOTE: one loop takes ~80us after serial read 
            while True:
                line = s.readline()
                # check serial timeout
                if (len(line) == 0):
                    print("[INFO] serial timeout")
                    self.__receive_timeout = True
                    break

                receive_time = time()
                # remove \n
                line = line.decode('UTF-8')[:-1]
                print("[" + port_receiver + "] " + str(receive_time) + " - " + line)

                # receiver setup ready and send can start
                if line == "rr":
                    self.__init_finished_lock.release()
                    continue

                if line == "Timeout":
                    self.__receive_timeout = True
                    break

                # parse line and get package number
                words = line.split(' ')
                if len(words) < 2:
                    print("[WARNING] Cannot parse, too few words")
                    continue

                package_number = None
                try:
                    package_number = int(words[1])
                except ValueError:
                    print("[WARNING] Cannot parse package number")
                    continue
                
                # udp received
                if words[0] == "ru":
                    if package_number in self.__received_packages_udp_timestamps:
                        print("[WARNING] UDP package already received")
                        continue
                    self.__received_packages_udp_timestamps[package_number] = receive_time
                # link layer received
                elif words[0] == "rl":
                    if package_number in self.__received_packages_link_timestamps:
                        print("[WARNING] Link layer package already received")
                        # may occur if printf was interrupted
                        continue
                    self.__received_packages_link_timestamps[package_number] = receive_time
                else:
                    print("[WARNING] Cannot parse package number")
                    continue

    # run measurement, blocks until finished
    # return None if measurement failed
    def run(self):
        receive_thread = Thread(target=self.__receive_thread_function)
        receive_thread.start()

        send_thread = Thread(target=self.__send_thread_function)
        send_thread.start()

        # wait until measurement finished
        receive_thread.join()
        send_thread.join()

        # calculate result
        for i in range(max(self.__send_packages_udp_timestamps.keys()) + 1):
            # if i not in self.__send_packages_udp_timestamps:
            #     print(f"Measurement failed: UDP package {i} not send")
            #     return None

            if 0 not in self.__send_packages_udp_timestamps:
                print(f"Measurement failed: UDP package 0 not send - needed for relative time calculation")
                return None
            
            lmd = LatencyMeasurementData(i)
            # take first udp send timestamp as start time
            if i  in self.__send_packages_udp_timestamps:
                lmd.udp_send_time_s = self.__send_packages_udp_timestamps[i] - self.__send_packages_udp_timestamps[0]

            if i in self.__received_packages_udp_timestamps and i in self.__send_packages_udp_timestamps:
                lmd.udp_latency_ms = (self.__received_packages_udp_timestamps[i] - self.__send_packages_udp_timestamps[i]) * 1000

            # take first udp send timestamp as start time
            if i in self.__send_packages_link_timestamps:
                lmd.link_send_time_s = self.__send_packages_link_timestamps[i] - self.__send_packages_udp_timestamps[0]

            if i in self.__received_packages_link_timestamps and i in self.__send_packages_link_timestamps:
                lmd.link_latency_ms = (self.__received_packages_link_timestamps[i] - self.__send_packages_link_timestamps[i]) * 1000

            if not lmd.is_valid():
                print(f"[WARNING] Package {i} not valid")
                # it may be that the measurement is incorrect e.g. a serial output was interrupted and not send
                # return None
            self.__result.append(lmd)

        return self.__result

    # generate a csv file
    def write_measurement_to_file(self, subfolder="latency", file_name_note=""):
        file_name_note_seperator = ""
        if file_name_note != "":
            file_name_note_seperator = "_"

        filename = (measurement_path + subfolder + "/latency_" + datetime.now().strftime("%Y-%m-%dT%H-%M-%S") + "_" 
            + str(self.__payload_size_bytes)  + "b_over" 
            + str(int(self.__runtime_us/1000000)) + "s_every" 
            + str(int(self.__interval_us / 1000)) + "ms"
            + file_name_note_seperator + file_name_note
            + ".csv")

        with open(filename, 'w') as file:
            # write meta data header
            file.write("Runtime in us;" + str(self.__runtime_us) + "\n")
            file.write("Payload size in byte;" + str(self.__payload_size_bytes) + "\n")
            file.write("Interval in us;" + str(int(self.__interval_us)) + "\n")
            if (self.__distance_cm):
                file.write("Distance in cm;" + str(float(self.__distance_cm)) + "\n")
            file.write("\n")

            # write measurement table
            file.write("pkt number;rel. UDP pkt send time [s];rel. link pkt send time [s];Latency UDP [ms];Latency link [ms]\n")
            for m in self.__result:
                file.write(m.csv_line())

        print("Saved measurement in file: " + filename)

    # read csv file, returns lists of LatencyMeasurementData
    def read_measurement_from_file(self, filename) -> list:
        with open(filename, 'r') as file:
            runtime = 0
            payload_size_bytes = 0
            interval_us = 0
            try:
                # read meta data header
                runtime = int(file.readline().split(';')[-1])
                payload_size_bytes = int(file.readline().split(';')[-1])
                interval_us = int(file.readline().split(';')[-1])
                # distance line may not exists, if not exists skips new line with read
                distance_cm = None
                distance_line = file.readline()
                if (distance_line != "\n"):
                    distance_cm = float(distance_line.split(';')[-1])
                    file.readline()  # skip new line

                file.readline()     # skip row description

                result = []

                for line in file:
                    m = LatencyMeasurementData(0)
                    content = line.split(';')
                    m.pkt_number = int(content[0])
                    m.udp_send_time_s = float(content[1])
                    m.link_send_time_s = float(content[2])
                    m.link_latency_ms = float(content[3])
                    m.udp_latency_ms = float(content[4])

                    if not m.is_valid():
                        print(f"[WARNING] Package {m.pkt_number} not valid")
                        # it may be that the measurement is incorrect e.g. a serial output was interrupted and not send
                        # return None

                    result.append(m)

            except Exception as e:
                print("[ERROR] cannot parse file " + filename)
                print(e)
                
                return None

            # if parsing successful save
            self.__runtime_us = runtime
            self.__payload_size_bytes = payload_size_bytes
            self.__interval_us = interval_us
            self.__result = result
            if (distance_cm):
                self.__distance_cm = distance_cm

        return self.__result

if __name__ == "__main__":
    m = LatencyMeasurementData(43, udp_send_time_s=12, link_send_time_s=13, link_latency_ms=13, udp_latency_ms=10)
    print(m.is_valid())
    print(m.csv_line())
