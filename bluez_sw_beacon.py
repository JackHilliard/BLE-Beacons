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
import numpy as np

# zone limit and sizes
# -20 to -30 at beacon
# -50 ~1m away
# -65 ~3 metres away
# very dependant on devices nearby and elevation compared to RPi
zoneLimit = -65

#URL definition
url = "http://192.168.1.242:3000"

#decode rssi
def twos_comp(val, bits):
    if ((val & (1 << (bits - 1))) != 0):
        val = val - (1 << bits)
    return val

def sendToServer(payload):
    r=requests.post(url + '/beacondata',
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


# main() function
def main():
    # use sys.argv if needed
    #if len(sys.argv) < 2:
    #    print('Usage: python bluey-beacon.py MACADDR')
    #    exit(0)
    #print('starting...')

    #deviceId = sys.argv[1]
    scanner = BLEScanner()
    scanner.start()

    zoneOne = False
    data = None
    while True:
        try:
            currentTime = time.time()
            if ((round(currentTime) % 10) == 0):
                print(currentTime)
                avgRssi = np.zeros((2,len(beacons[0][])))
                while (time.time() <= currentTime + 15):
                    for line in scanner.get_lines():
                        if line:
                            found_mac = line[14:][:12]
                            reversed_mac = ''.join(
                                reversed([found_mac[i:i + 2] for i in range(0, len(found_mac), 2)]))
                            mac = ':'.join(a+b for a,b in zip(reversed_mac[::2], reversed_mac[1::2]))
                            data = line[26:]
                            #cycle through all the known beacons
                            for x in len(beacons[0][]):
                                if mac == beacons[0][x] and len(data) == 64:
                                    #print(mac, data)
                                    if beacons[1][x] in data:
                                        #average reading
                                        #check if it is within range
                                        avgRssi[0][x]+=twos_comp(int(data[62:],16), 8)
                                        avgRssi[1][x]+=1
                                        break
                                elif(time.time() >= currentTime + 5): #if it goes 10 seconds without finding any data break
                                    break;
                for x in len(beacons[0][]):
                    if (avgRssi[0][x] == 0):
                        if(zoneOne==True):
                            print("Beacon", beacons[0][x], "is now out of range")
                            sendToServer({'beacon': beacons[0][x], 'zone': 'none', 'timestamp': str(arrow.utcnow())})
                        zoneOne = False
                        print("Beacon", beacons[0][x], "cannot be found")
                    else:
                        rssi = avgRssi[0][x]/avgRssi[1][x]
                        #handles beacon leaving or entering zone
                        if ((rssi >= zoneLimit) and (zoneOne == False)):
                            zoneOne=True
                            print("Beacon", beacons[0][x], "is in range")
                            print("RSSI :", rssi)
                            sendToServer({'beacon': beacons[0][x], 'zone': 'one', 'timestamp': str(arrow.utcnow())})
                        elif ((rssi < zoneLimit) and (zoneOne == True)):
                            zoneOne = False
                            print("Beacon", beacons[0][x], "is now out of range")
                            sendToServer({'beacon': beacons[0][x], 'zone': 'none', 'timestamp': str(arrow.utcnow())})
        except KeyboardInterrupt as ex:
            print("kbi")
            scanner.stop()
            exit(0)

# call main
if __name__ == '__main__':
    main()
