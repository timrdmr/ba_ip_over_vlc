#!/usr/bin/env python3

import subprocess
import time
import os
from threading import Thread, Lock

flash_failed = False
status_lock = Lock()

def build_source():
    cmd = [
        "make", "all", "-j", "2"
    ]

    print("Start compiling...")
    flash_dir = "/home/tim/Bachelorarbeit/Code/measurements"
    p = subprocess.Popen(cmd, cwd=flash_dir, stdout=open(os.devnull, "w"))
    p.wait()

    assert p.returncode == 0, "compile error"
    print("Compiled successfully")


# returns return code of make flash 
def flash_node(number):
    device = "r"
    if (number == 0):
        device = "s"

    flash_dir = "/home/tim/Bachelorarbeit/Code/measurements"
    cmd = [
        "make", "flash", "-j", "2"
        "PORT=\"/dev/ttyACM" + str(number) + "\"",
        "SERIAL=$" + device,
    ]

    print(f"Try to flash device {device} with number {number}")
    for _ in range(0,6):
        p = subprocess.Popen(cmd, cwd=flash_dir, stdout=open(os.devnull, "w"))
        p.wait()

        if  p.returncode != 0:
            print(f"WARNING cant flash device {device} with number {number} - try again...")
            time.sleep(10)
        else:
            print(f"Successfully flashed device {device} with number {number}")
            return

    with status_lock:
        global flash_failed
        flash_failed = True 

def flash_all_nodes():

    s = Thread(target=flash_node, args=(0,))
    r = Thread(target=flash_node, args=(1,))

    s.start()
    r.start()

    s.join()
    r.join()

    assert flash_failed == False, "flash failed"

    print("All flashed!")

if __name__ == "__main__":
    build_source()
    flash_all_nodes()
