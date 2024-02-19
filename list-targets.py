#!/bin/python3

import os
import pprint
import re

def printboards(boards):
    print("%s\n" % re.sub(r"'|[)]|[(]|^ ", '', pprint.pformat("%s" % boards, width=80)))

os.chdir("boards.d")

allwinner = ""
am625 = ""
qcom = ""
rk33xx = ""
other = ""

for entry in sorted(os.listdir('.')):

    if os.path.islink(entry):
        if 'AllWinner' == os.path.basename(os.path.realpath(entry)):
            allwinner += "%s " % entry
        elif 'am625' == os.path.basename(os.path.realpath(entry)):
            am625 += "%s " % entry
        elif 'qcom' == os.path.basename(os.path.realpath(entry)):
            qcom += "%s " % entry
        elif 'rk33xx' == os.path.basename(os.path.realpath(entry)):
            rk33xx += "%s " % entry
        else:
            if entry != 'none':
                other += "%s " % entry


print("AllWinner Devices:")
printboards(allwinner)

print("TI am625 Devices:")
printboards(am625)

print("QCom Devices:")
printboards(qcom)

print("Rockchips rk33xx series Devices:")
printboards(rk33xx)

print("Other Devices:")
printboards(other)
