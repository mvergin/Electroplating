from pathlib import Path
import sys
import csv
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm

print(sys.argv)
epdir = Path(sys.argv[1])
for csvf in tqdm(epdir.rglob("*.csv")):
    if csvf.with_suffix(".png").is_file():
        continue
    print(csvf)
    header = None
    timelist = list()
    currentlist = list()
    voltlist = list()
    chargelist = list()
    with open(csvf, newline="\n") as csvfile:
        csvreader = csv.reader(csvfile)
        dec_string = next(csvreader)
        # print(dec_string)
        if not "Electroplating" in dec_string[0]:
            print("here")
            continue
        for row in csvreader:
            if len(row) < 2:
                continue
            # if not row[0].isnumeric():
            #     continue
            if not header:
                header = row
                continue
            timelist.append(row[0])
            currentlist.append(row[1])
            voltlist.append(row[2])
            chargelist.append(row[3])
    timearr = np.asarray(timelist, dtype=float)
    curarr = np.asarray(currentlist, dtype=float)
    chargearr = np.asarray(chargelist, dtype=float)
    plt.plot(timearr, curarr)
    plt.minorticks_on()
    plt.grid(which="major")
    plt.title("Current vs Time")
    plt.xlabel("Time")
    plt.ylabel("Current (mA)")
    plt.savefig(
        csvf.with_suffix(".png"),
        dpi=150,
        facecolor="white",
        bbox_inches="tight",
        pad_inches=0.5,
    )
    plt.clf()
