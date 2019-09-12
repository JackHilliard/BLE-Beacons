"""
References:
1. Ruuvi Project.
https://github.com/ttu/ruuvitag-sensor/
2.bluey_beacon.py from electronut
"""

import re
import sys
import os
import time
import subprocess
import requests
import arrow
import json

# zone limit and sizes
# -20 to -30 at beacon
# -50 ~1m away
# -65 ~3 metres away
# very dependant on devices nearby and elevation compared to RPi
zoneLimit = -65
rpiZone = "one"

#decode rssi
def twos_comp(val, bits):
    if ((val & (1 << (bits - 1))) != 0):
        val = val - (1 << bits)
    return val

def sendToServer(payload):
    r=requests.post(conf["url"] + '/beacondata',
                    headers={'Content-Type': 'application/json'},
                    json=payload)

    if r.status_code == 200:
        print(r.content)
        
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
            scanner.stop()
            exit(0)
            return
        except Exception as ex:
            print(ex)
            return

class BLEBeacon:
    def __init__(self, macAddr, name)
        self.macAddr = macAddr
        self.name = name
        self.combRssi = 0
        self.countRssi = 0
        self.avgRssi = 0
        self.zone = False

# main() function
def main():
    scanner = BLEScanner()
    scanner.start()
    #beacons = [BLEBeacon("E9:F6:A1:2B:AD:69",u'2BAD69BB'),BLEBeacon("FC:3E:28:A4:8F:4E", u'A48F4EBA')]
    beacons = []
    for x in range(len(conf["beacons"])):
        beacons[x] = BLEBeacon(conf["beacons"][x]["macAddr"],conf["beacons"][x]["name"])
    data = None
    while True:
        try:
            currentTime = time.time()
            if ((round(currentTime) % 10) == 0):
                #print(currentTime)
                for x in range(len(beacons)):
                    beacons[x].combRssi = 0
                while (time.time() <= currentTime + 15):
                    for line in scanner.get_lines():
                        if line:
                            found_mac = line[14:][:12]
                            reversed_mac = ''.join(
                                reversed([found_mac[i:i + 2] for i in range(0, len(found_mac), 2)]))
                            mac = ':'.join(a+b for a,b in zip(reversed_mac[::2], reversed_mac[1::2]))
                            data = line[26:]
                            #cycle through all the known beacons
                            for x in range(len(beacons)):
                                if mac == beacons[x].macAddr and len(data) == 64:
                                    #print(mac, data)
                                    if beacons[x].name in data:
                                        #average reading
                                        beacons[x].combRssi+=twos_comp(int(data[62:],16), 8)
                                        beacons[x].countRssi+=1
                                        break
                                elif(time.time() >= currentTime + 5): #if it goes 5 seconds without finding any data timeout
                                    break
                for x in range(len(beacons)):
                    if (beacons[x].countRssi == 0):
                        if(beacons[x].zone==True):
                            print("Beacon", beacons[x].macAddr, "is now out of range")
                            sendToServer({'beacon': beacons[x].macAddr, 'zone': 'none', 'rssi': 0, 'timestamp': str(arrow.utcnow())})
                        else: print("Beacon", beacons[x].macAddr, "cannot be found")
                        beacons[x].zone = False
                    else:
                        beacons[x].avgRssi = beacons[x].combRssi/beacons[x].countRssi
                        #handles beacon leaving or entering zone
                        if ((beacons[x].avgRssi >= zoneLimit) and (beacons[x].zone == False)):
                            beacons[x].zone=True
                            print("Beacon", beacons[x].macAddr, "is in range")
                            print("RSSI :", beacons[x].rssi)
                            sendToServer({'beacon': beacons[x].macAddr, 'zone': rpiZone, 'rssi': beacons[x].avgRssi, 'timestamp': str(arrow.utcnow())})
                        elif ((beacons[x].avgRssi < zoneLimit) and (beacons[x].zone == True)):
                            beacons[x].zone = False
                            print("Beacon", beacons[x].macAddr, "is now out of range")
                            sendToServer({'beacon': beacons[x].macAddr, 'zone': 'none', 'rssi': 0, 'timestamp': str(arrow.utcnow())})
        except KeyboardInterrupt as ex:
            print("kbi")
            scanner.stop()
            exit(0)

# call main
if __name__ == '__main__':
    main()
