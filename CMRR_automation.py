#!/usr/bin/env python

"""
A python script to automate the collection of data during a CMRR test for acq482.
"""

from __future__ import print_function
import acq400_hapi
import epics
import matplotlib.pyplot as plt
import numpy as np
import argparse
import os
from prettytable import PrettyTable

def analyse(data):
    max_index = np.argmax(data[1])
    max_db = data[1][max_index]
    freq = data[0][max_index]
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


def run_test(args):
    #uut = acq400_hapi.Acq400(args.uut[0])
    #uut.MODE.CONTINUOUS
    raw_input("This test has been configured for system: {}, with {} modules. If this is correct please press enter. Else ctrl-c and start again".format(args.uut[0], args.modules))
    global tabulated_data
    channels = list(range(1, 17))
    for mode in ["Normal configuration", "Shorted configuration"]:
        for module in range(1, args.modules+1):
            print("Carrier in use: ", args.uut[0])
            for chan in channels:
                chan = "{:02d}".format(chan)
                raw_input("Please connect channel {} on module {} in {} and then press enter to continue: ".format(chan, module, mode)) # {:02d}.format() pads chan to two digits for epics.

                data = retrieve_data(args.uut[0], module, chan, args)
                if args.plot_data == 1:
                    plot_data(data)
                if args.save_data == 1:
                    store_data(data, args.uut[0], module, chan, args)
                analyse(data)

    t = PrettyTable(['CH', 'normal dB', 'normal Hz', 'shorted dB', 'shorted Hz', "CMRR"])
    ch = 0
    while ch < 16*args.modules:
        # print("channel: ", ch, tabulated_data[ch][0], "dB ", tabulated_data[ch][1], "Hz ", tabulated_data[ch+16*args.modules][0], "dB", tabulated_data[ch+16*args.modules][1], "Hz")
        t.add_row([ch+1, tabulated_data[ch][0], tabulated_data[ch][1], tabulated_data[ch+16*args.modules][0], tabulated_data[ch+16*args.modules][1], tabulated_data[ch][0] - tabulated_data[ch+16*args.modules][0]])
        ch+=1
    print(t)
    results_file = open("{}/{}".format("/home/dt100/CMR/{}".format(args.uut[0]), "results"), "wb")
    results_file.write(str(t))
    results_file.close()

def retrieve_data(carrier, module, channel, args):
    if int(channel) > 8:
        module += 1
        channel = int(channel) - 8
        channel = "{:02d}".format(int(channel))
    ydata = epics.caget("{}:{}:AI:WF:PS:{}.VALA".format(carrier, module, channel)) # data in dB
    xdata = epics.caget("{}:{}:AI:WF:PS:{}.VALB".format(carrier, module, channel)) # data in Hz
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

    parser.add_argument('uut', nargs='+', help="uut")
    run_test(parser.parse_args())


if __name__ == '__main__':
    tabulated_data = []
    run_main()
