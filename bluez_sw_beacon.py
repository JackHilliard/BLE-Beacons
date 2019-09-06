"""
bluey_beacon.py
This program connects to the bluey 1.1 Nordic nRF52 dev board 
made by Electronut Labs. The firmware on Bluey has to be running the 
"bluey beacon" example. 
This code is expected to be run on a Raspverry Pi 3.
It assumes that you have bluez installed - it uses hcidump and hcitool.
The code reads advertisement packets from bluey, parses the 
Temperature, Humidity, and Ambient Light informationb and 
posts that to freeboard.io dashboard via dweet.io.
Electronut Labs
electronut.in
References:
1. Ruuvi Project.
https://github.com/ttu/ruuvitag-sensor/
"""

import re
import sys
import os
import time
import subprocess
from datetime import datetime

# constant
zoneLimit = -90

#decode rssi
def twos_comp(val, bits):
    if ((val & (1 << (bits - 1))) != 0):
        val = val - (1 << bits)
    return val

"""
This class uses hctool and hcidump to parse BLE adv data.
"""
class BLEScanner:

    hcitool = None
    hcidump = None
    
    def start(self):
        print('Start receiving broadcasts')
        DEVNULL = subprocess.DEVNULL if sys.version_info > (3, 0) else open(os.devnull, 'wb')

        subprocess.call('sudo hciconfig hci0 reset', shell = True, stdout = DEVNULL)
        self.hcitool = subprocess.Popen(['sudo', '-n', 'hcitool', 'lescan', '--duplicates'], stdout = DEVNULL)
        self.hcidump = subprocess.Popen(['sudo', '-n', 'hcidump', '--raw'], stdout=subprocess.PIPE)

    def stop(self):
        print('Stop receiving broadcasts')
        subprocess.call(['sudo', 'kill', str(self.hcidump.pid), '-s', 'SIGINT'])
        subprocess.call(['sudo', '-n', 'kill', str(self.hcitool.pid), '-s', "SIGINT"])

    def get_lines(self):
        data = None
        try:
            print("reading hcidump...\n")
            #for line in hcidump.stdout:
            while True:
                line = self.hcidump.stdout.readline()
                line = line.decode()
                if line.startswith('> '):
                    yield data
                    data = line[2:].strip().replace(' ', '')
                elif line.startswith('< '):
                    data = None
                else:
                    if data:
                        data += line.strip().replace(' ', '')
        except KeyboardInterrupt as ex:
            print("kbi")
            return
        except Exception as ex:
            print(ex)
            return


# main() function
def main():
    # use sys.argv if needed
    if len(sys.argv) < 2:
        print('Usage: python bluey-beacon.py MACADDR')
        exit(0)
    print('starting...')

    deviceId = sys.argv[1]
    scanner = BLEScanner()
    scanner.start()

    zoneOne = False
    data = None
    while True:
        try:
            currentTime = time.time()
            if ((round(currentTime) % 10) == 0):
                print(currentTime)
                avgRssi = 0
                countRssi = 0
                while (time.time() <= currentTime + 15):
                    for line in scanner.get_lines():
                        if line:
                            found_mac = line[14:][:12]
                            reversed_mac = ''.join(
                                reversed([found_mac[i:i + 2] for i in range(0, len(found_mac), 2)]))
                            mac = ':'.join(a+b for a,b in zip(reversed_mac[::2], reversed_mac[1::2]))
                            data = line[26:]
                            if mac == deviceId and len(data) == 64:
                                #print(mac, data)
                                if u'2BAD69BB' in data:
                                    rssi = twos_comp(int(data[62:],16), 8)
                                    #average reading
                                    #check if it is within range
                                    avgRssi+=rssi
                                    countRssi+=1
                                    break
                if (countRssi == 0):
                    zoneOne = False
                    print("Beacon", deviceId, "cannot be found")
                else:
                    avgRssi = avgRssi/countRssi
                    #handles beacon leaving or entering zone
                    if ((avgRssi > zoneLimit) and (zoneOne==False)):
                        zoneOne=True
                        print("Beacon", deviceId, "is in range")
                        print("RSSI :", avgRssi)
                    elif ((avgRssi < zoneLimit) and (zoneOne == True)):
                        zoneOne = False
                        print("Beacon", deviceId, "is now out of range")
        except KeyboardInterrupt as ex:
            print("kbi")
            scanner.stop()
            exit(0)

# call main
if __name__ == '__main__':
    main()
