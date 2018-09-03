#!/usr/bin/env python

"""
A python script to automate the collection of data during a CMRR test for acq482.
Assumes that carrier has 3 modules.

Example usage:

    python CMRR_automation.py acq2106_105

Example usage for carrier without 2 modules:

    python CMRR_automation.py --modules=2 acq2106_105

Dependencies:
    Requires pyepics, matplotlib, numpy, prettytable.
    All of these are available as dt100 on endor.

Run from:

    /home/dt100/CMR/cmrr

    ie:
    cd /home/dt100/CMR/cmrr
    python CMRR_automation.py acq2106_105

Data is saved one directory up in /home/dt100/CMR/<UUT Name>

"""


from __future__ import print_function
import epics
import matplotlib.pyplot as plt
import numpy as np
import argparse
import os
import shutil
import datetime
import socket
import math
from prettytable import PrettyTable


def analyse(data, args, mode):
    global max_db
    global freq
    total_energy = 0
    max_index = np.argmax((data[1][2:]))

    for index in range(max_index - 5, max_index + 5):
        total_energy += (data[1][index]) ** 2
    total_energy = math.sqrt(total_energy)
    total_energy = 20 * np.log10(total_energy)
    max_db = total_energy
    #max_db = data[1][2:][max_index]
    freq = data[0][2:][max_index]
    print("Peak detected at: ", max_db, "dB at frequency: ", freq, "Hz")

    if mode == "Standard configuration":
        if max_db > -2 or max_db < -6 or freq < 90000 or freq > 110000:
            print("\n\n")
            return False
    if mode == "CMR configuration":
        if max_db > -80 or max_db < -110 or freq < 90000 or freq > 110000:
            print("\n\n")
            return False
    append_data() # do not need to pass parameters as vars are global
    print("\n\n")
    return True


def append_data():
    global tabulated_data
    tabulated_data.append((max_db, freq))


def make_data_dir(directory):
    try:
        os.makedirs(directory)
    except Exception:
        print("Tried to create dir but dir already exists")
        pass


def plot_data(data):
    plt.plot(data[0], data[1])
    plt.show()


def configure_uut(uut, args):
    epics.caput("{}:MODE:CONTINUOUS".format(uut), 0) # disable streaming before configuring uut.
    epics.caput("{}:AI:WF:PS:SMOO".format(uut), args.smoo)
    # epics.caput("{}:MODE:CONTINUOUS".format(uut), 1)


def run_test(args):

    raw_input("Test configured for system: {} with {} modules. "
              "If this is correct press enter. Else ctrl-c and start again".format(args.uut[0], args.modules))
    configure_uut(args.uut[0], args)

    global tabulated_data
    channels = list(range(1, 17))
    for mode in ["Standard configuration", "CMR configuration"]:
        for module in range(1, args.modules*2+1, 2):
            print("Carrier in use: ", args.uut[0])
            for chan in channels:
                successful = False
                chan = "{:02d}".format(chan)
                while not successful:

                    raw_input("Please connect channel {} on site {} in {} "
                              "and then press enter to continue: ".format(chan, module, mode)) # {:02d}.format() pads chan to two digits for epics.

                    if args.local_fft == 1:
                        data = retrieve_non_fft_data(args.uut[0], module, chan, args)
                        data = perform_fft(data, args.uut[0], module)
                    else:
                        data = retrieve_data(args.uut[0], module, chan, args)

                    status = analyse(data, args, mode)
                    if status == False:

                        choice = raw_input("Potential bad values detected. "
                                           "Would you like to repeat the last channel? y/n: ")
                        if choice != "n":
                            continue
                        else:
                            append_data() # do not need to pass parameters as vars are global
                            successful = True
                    else:
                        if args.plot_data == 1:
                            plot_data(data)
                        if args.save_data == 1:
                            store_data(data, args.uut[0], module, chan, args)
                        successful = True


    sys_info_table = get_system_info(args)
    results_table = get_results_table(args)
    final_table = sys_info_table + "\n\n" + results_table

    print(final_table)
    results_file = open("{}/{}".format("/home/dt100/CMR/{}".format(args.uut[0]), "results"), "wb")
    results_file.write(final_table)
    results_file.close()
    copy_data(args)


def get_results_table(args):
    global tabulated_data
    t = PrettyTable(['CH', 'standard mode dB', 'standard mode Hz',
                     'CMR mode dB', 'CMR mode Hz', "Calculated CMRR (Results)"])
    ch = 0
    while ch < 16 * args.modules:
        t.add_row([ch + 1, tabulated_data[ch][0], tabulated_data[ch][1], tabulated_data[ch + 16 * args.modules][0], \
                   tabulated_data[ch + 16 * args.modules][1], tabulated_data[ch][0] - \
                   tabulated_data[ch + 16 * args.modules][0]])
        ch += 1
    return str(t)


def get_system_info(args):
    info = []
    info.append(epics.caget("{}:0:SERIAL".format(args.uut[0])))
    info.append(epics.caget("{}:SYS:VERSION:SW".format(args.uut[0])))
    info.append(epics.caget("{}:SYS:VERSION:FPGA".format(args.uut[0])))
    info.append(epics.caget("{}:SYS:Z:TEMP".format(args.uut[0])))
    info.append(epics.caget("{}:SYS:{}:TEMP".format(args.uut[0], 0)))
    for site in [1,3,5]:
        info.append(epics.caget("{}:{}:SERIAL".format(args.uut[0], site)))
        info.append(epics.caget("{}:SYS:{}:TEMP".format(args.uut[0], site)))

    table = PrettyTable()
    table.add_column("Parameters", ["Serial Num", "SW Version",
                                    "FPGA", "Zync Temp", "Site 0 Temp",
                                    "Site 1 SN", "Site 1 Temp",
                                    "Site 3 SN", "Site 3 Temp",
                                    "Site 5 SN", "Site 5 Temp"])
    table.add_column("Values", info)
    return str(table)


def copy_data(args):
    choice = raw_input("Data collection finished. "
                       "Would you like to store this data in the final data directory? y/n: ")
    if choice == "y":
        source = "/home/dt100/CMR/{}/".format(args.uut[0])
        destination = "/home/dt100/CMR/final_data/{}/{}".format(args.uut[0], "_".join(str(datetime.datetime.now()).split(" ")))
        shutil.copytree(source, destination)
        print("Data has been recorded in {}".format(destination))
    return None


def retrieve_data(carrier, module, channel, args):
    if int(channel) > 8:
        module += 1
        channel = int(channel) - 8
        channel = "{:02d}".format(int(channel))
    print("module: ",module, "channel: ", channel)
    ydata = epics.caget("{}:{}:AI:WF:PS:{}.VALA".format(carrier, module, channel)) # data in dB
    if args.save_freq_data == 1:
        xdata = epics.caget("{}:{}:AI:WF:PS:{}.VALB".format(carrier, module, channel)) # data in Hz
        return [xdata, ydata]
    else:
        xdata = epics.caget("{}:{}:AI:WF:PS:01.VALB".format(carrier, module))  # data in Hz
    return [xdata, ydata]


def retrieve_non_fft_data(carrier, module, channel, args):
    if int(channel) > 8:
         module += 1
         channel = int(channel) - 8
         channel = "{:02d}".format(int(channel))

    data = ""
    skt = socket.socket()
    skt.connect((carrier, int("530" + channel)))
    while len(data) < 200000:
        data += skt.recv(4096)

    data = np.frombuffer(data, dtype=np.int16)
    print("Channel = ", channel)

    xdata = np.linspace(0, 500000, len(data))
    ydata = data
    return [xdata, ydata]


def perform_fft(data, carrier, module):
    data[1] = data[1][6:65535]
    data[1] = data[1] / float(32768)

    ft = abs(np.fft.rfft((data[1]))) # take the fourier transform
    L = len(data[1])/2 #/ (float())
    ft = (ft/L)

    ps = 20 * (np.log10(ft)) # Take 20 * log10 of the absolute value of the data

    freq_axis = np.linspace(0, int(epics.caget("{}:{}:ACQ480:OSR".format(carrier, module)))/2, len(ft))

    peak = max(ps)
    peak_index = np.argmax(ps)
    print("peak = ", peak)
    print("peak index = ", peak_index)

    total_energy = 0
    for index in range(peak_index - 5, peak_index + 5):
        total_energy += (ft[index]) ** 2
    total_energy = math.sqrt(total_energy)
    total_energy = 20 * np.log10(total_energy)
    print("total energy = ", total_energy)

    # plt.plot(freq_axis, ps)
    # plt.show()
    return [freq_axis, ft]


def store_data(data, carrier, module, channel, args):
    dir = "/home/dt100/CMR/{}/module_{}/CH{}".format(carrier, module, channel)
    make_data_dir(dir)
    data_file_x = open("{}/{}".format(dir, "frequency_data"), "wb")
    data_file_y = open("{}/{}".format(dir, "power_data"), "wb")
    data_file_x.write(data[0])
    data_file_y.write(data[1])
    data_file_x.close()
    data_file_y.close()
    return None


def run_main():
    parser = argparse.ArgumentParser(description='Run CMRR test')
    parser.add_argument('--carrier', default=1, type=int, help="Number of carriers involved in the test.")
    parser.add_argument('--modules', default=3, type=int, help="Number of acq482 modules in EACH carrier. Max = 3.")
    parser.add_argument('--save_data', default=1, type=int, help="Whether to store data or not (test run).")
    parser.add_argument('--plot_data', default=0, type=int, help="Whether to plot the data before it gets saved.")
    parser.add_argument('--save_freq_data', default=0, type=int, help="")
    parser.add_argument('--smoo', default=0, type=float, help="Smoothing factor")
    parser.add_argument('--local_fft', default=0, type=float, help="Whether to download standard sample data and "
                                                                   "use it to perform an FFT locally. This is in "
                                                                   "contrast to downloading FFT data from the UUT.")
    parser.add_argument('uut', nargs='+', help="uut")
    run_test(parser.parse_args())


if __name__ == '__main__':
    tabulated_data = []

    run_main()
