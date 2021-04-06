
import subprocess

riot_dir = "/home/tim/riot/RIOT"

def overwrite_datarate(new_data_rate):
    # sed -i 's/DATARATE_BITS_PER_SECOND 5000/DATARATE_BITS_PER_SECOND 10000/' vlc_netif.c

    cmd = ["sed", "-i", f"s/#define DATARATE_BITS_PER_SECOND.*/#define DATARATE_BITS_PER_SECOND {new_data_rate}/", "vlc_netif.c"]
    print(cmd)
    p = subprocess.Popen(cmd, cwd=riot_dir + "/sys/vlc_netif")
    p.wait()

    return p.returncode

def overwrite_tolerance(new_tolerance):

    cmd = ["sed", "-i", f"s/#define VLC_RECEIVER_TOLERANCE.*/#define VLC_RECEIVER_TOLERANCE {new_tolerance}/", "vlc_netif.c"]
    print(cmd)
    p = subprocess.Popen(cmd, cwd=riot_dir + "/sys/vlc_netif")
    p.wait()

    return p.returncode
