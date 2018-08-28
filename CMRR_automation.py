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
import acq400_hapi
from prettytable import PrettyTable


def analyse(data, args):
    max_index = np.argmax((data[-1][2:]))
    max_db = data[1][2:][max_index]
    freq = data[0][2:][max_index]
    print("Peak detected at: ", max_db, "dB at frequency: ", freq, "Hz")
    global tabulated_data
    tabulated_data.append((max_db, freq))
    print("\n\n")
    return None


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
    epics.caput("acq2106_105:MODE:CONTINUOUS", 0) # disable streaming before configuring uut.
    epics.caput("{}:AI:WF:PS:SMOO".format(uut), args.smoo)
    epics.caput("acq2106_105:MODE:CONTINUOUS", 1)


def run_test(args):

    raw_input("Test configured for system: {} with {} modules. If this is correct press enter. Else ctrl-c and start again".format(args.uut[0], args.modules))

    configure_uut(args.uut[0], args)

    global tabulated_data
    channels = list(range(1, 17))
    for mode in ["Standard configuration", "CMR configuration"]:
        for module in range(1, args.modules*2+1, 2):
            print("Carrier in use: ", args.uut[0])
            for chan in channels:
                chan = "{:02d}".format(chan)
                raw_input("Please connect channel {} on site {} in {} and then press enter to continue: ".format(chan, module, mode)) # {:02d}.format() pads chan to two digits for epics.

                data = retrieve_data(args.uut[0], module, chan, args)

                if args.plot_data == 1:
                    plot_data(data)
                if args.save_data == 1:
                    store_data(data, args.uut[0], module, chan, args)

                analyse(data, args)

    sys_info_table = get_system_info(args)
    results_table = get_results_table(args)
    final_table = sys_info_table + "\n\n" + results_table

    # t = PrettyTable(['CH', 'standard mode dB', 'standard mode Hz', 'CMR mode dB', 'CMR mode Hz', "Calculated CMRR (Results)"])
    # ch = 0
    # while ch < 16*args.modules:
    #     t.add_row([ch+1, tabulated_data[ch][0], tabulated_data[ch][1], tabulated_data[ch+16*args.modules][0], \
    #                tabulated_data[ch+16*args.modules][1], tabulated_data[ch][0] - \
    #                tabulated_data[ch+16*args.modules][0]])
    #     ch+=1

    print(final_table)
    results_file = open("{}/{}".format("/home/dt100/CMR/{}".format(args.uut[0]), "results"), "wb")
    results_file.write(final_table)
    results_file.close()

    copy_data(args)


def get_results_table(args):
    global tabulated_data
    t = PrettyTable(['CH', 'standard mode dB', 'standard mode Hz', 'CMR mode dB', 'CMR mode Hz', "Calculated CMRR (Results)"])
    ch = 0
    while ch < 16 * args.modules:
        t.add_row([ch + 1, tabulated_data[ch][0], tabulated_data[ch][1], tabulated_data[ch + 16 * args.modules][0], \
                   tabulated_data[ch + 16 * args.modules][1], tabulated_data[ch][0] - \
                   tabulated_data[ch + 16 * args.modules][0]])
        ch += 1


def get_system_info(args):
    info = []
    info.append(epics.caget("{}:0:SERIAL".format(args.uut[0])))
    info.append(epics.caget("{}:SYS:VERSION:SW".format(args.uut[0])))
    info.append(epics.caget("{}:SYS:VERSION:FPGA".format(args.uut[0])))
    info.append(epics.caget("{}:SYS:Z:TEMP".format(args.uut[0])))

    for site in [0,1,3,5]:
        info.append(epics.caget("{}:SYS:{}:TEMP".format(args.uut[0], site)))

    table = PrettyTable(["Serial Number", "Software Version", "FPGA Personality", "Zync Temp", "Site 0 Temp", "Site 3 Temp", "Site 5 Temp"])
    table.add_row(info)
    return str(table)


def copy_data(args):
    choice = raw_input("Data collection finished. Would you like to store this data in the final data directory? y/n: ")
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
    parser.add_argument('--smoo', default=0.75, type=float, help="Smoothing factor")
    parser.add_argument('uut', nargs='+', help="uut")
    run_test(parser.parse_args())


if __name__ == '__main__':
    tabulated_data = []
    run_main()
