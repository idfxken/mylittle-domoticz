#!/usr/bin/python
#   File : bluedetect.py
#   Author: jmleglise - lalemanw
#   Date: 25-10-2017
#   Version 1.6.1 initial split off

#   Description : Modified version of jmleglises' script to run on switches instead of uservariables (now who doesnt want to see if their kids sneak out at night?)
#   His original script can be found here: https://github.com/jmleglise/mylittle-domoticz/edit/master/Presence%20detection%20%28beacon%29/check_beacon_presence.py

# Script takes care of Bluetooth Adapter. Switch it UP RUNNING.
# When the MACADRESS of a list of beacons are detected, update DOMOTICZ.
#
# References :
# https://www.domoticz.com/wiki/Presence_detection_%28Bluetooth_4.0_Low_energy_Beacon%29
# http://https://www.domoticz.com/forum/viewtopic.php?f=28&t=10640
# https://wiki.tizen.org/wiki/Bluetooth
# https://storage.googleapis.com/google-code-archive-source/v2/code.google.com/pybluez/source-archive.zip  => pybluez\examples\advanced\inquiry-with-rssi.py
#
# Required in Domoticz : A switchlight with known idx value
# Configuration :
# Change your IP and Port here :
# Logically these switches should be protected in domoticz, so add your passcode
URL_DOMOTICZ = 'http://xxxx.xx:port/json.htm?type=command&param=switchlight&idx=PARAM_IDX&switchcmd=PARAM_CMD&passcode=DOMOTICZ_PASSCODE'
DOMOTICZ_USER='xxxx'
DOMOTICZ_PASS='xxxx'
DOMOTICZ_PASSCODE='1111'


# Configure your Beacons in the TAG_DATA table with : [Name,MacAddress,Timeout,0,idx]
# name can be random, best to use something recongizable(no spaces)
# macAddress : case insensitive
# Timeout is in secondes the elapsed time  without a detetion for switching the beacon AWAY. Ie :if your beacon emits every 3 to 8 seondes, a timeout of 15 secondes seems good.
# 0 : used by the script (will keep the time of the last broadcast)
# idx of the switch in Domoticz for this beacon


TAG_DATA = [
            ["Tag_Me","7C:2F:80:CE:F0:D6",30,0,2],
            ["Tag_Wife","fa:1e:1a:e6:b0:b2",30,0,258]
           ]


import logging

# choose between DEBUG (log every information) or warning (change of state) or CRITICAL (only error)
#logLevel=logging.DEBUG
#logLevel=logging.CRITICAL
logLevel=logging.WARNING

logOutFilename='/var/log/bluedetect.log'       # output LOG : File or console (comment this line to console output)
ABSENCE_FREQUENCY=10  # frequency of the test of absence. in seconde. (without detection, switch "Off".

################ Nothing to edit under this line #####################################################################################

import os
import subprocess
import sys
import struct
import bluetooth._bluetooth as bluez
import time
import requests
import signal
import threading


LE_META_EVENT = 0x3e
OGF_LE_CTL=0x08
OCF_LE_SET_SCAN_ENABLE=0x000C
EVT_LE_CONN_COMPLETE=0x01
EVT_LE_ADVERTISING_REPORT=0x02

def print_packet(pkt):
    for c in pkt:
        sys.stdout.write("%02x " % struct.unpack("B",c)[0])

def packed_bdaddr_to_string(bdaddr_packed):
    return ':'.join('%02x'%i for i in struct.unpack("<BBBBBB", bdaddr_packed[::-1]))

def hci_disable_le_scan(sock):
    hci_toggle_le_scan(sock, 0x00)

def hci_toggle_le_scan(sock, enable):
    cmd_pkt = struct.pack("<BB", enable, 0x00)
    bluez.hci_send_cmd(sock, OGF_LE_CTL, OCF_LE_SET_SCAN_ENABLE, cmd_pkt)

def handler(signum = None, frame = None):
    time.sleep(1)  #here check if process is done
    sys.exit(0)

for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
    signal.signal(sig, handler)

def le_handle_connection_complete(pkt):
    status, handle, role, peer_bdaddr_type = struct.unpack("<BHBB", pkt[0:5])
    device_address = packed_bdaddr_to_string(pkt[5:11])
    interval, latency, supervision_timeout, master_clock_accuracy = struct.unpack("<HHHB", pkt[11:])
    #print "le_handle_connection output"
    #print "status: 0x%02x\nhandle: 0x%04x" % (status, handle)
    #print "role: 0x%02x" % role
    #print "device address: ", device_address

def request_thread(idx,cmd, name):
    try:
        url = URL_DOMOTICZ
        url=url.replace('PARAM_IDX',str(idx))
        url=url.replace('PARAM_CMD',str(cmd))
        url=url.replace('PARAM_NAME',str(name))
        url=url.replace('DOMOTICZ_PASSCODE',str(DOMOTICZ_PASSCODE))
        result = requests.get(url,auth=(DOMOTICZ_USER, DOMOTICZ_PASS))
        logging.debug(" %s -> %s" % (threading.current_thread(), result))
    except requests.ConnectionError, e:
        logging.critical(' %s Request Failed %s - %s' % (threading.current_thread(), e, url) )

class CheckAbsenceThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    def run(self):

        time.sleep(ABSENCE_FREQUENCY)
        for tag in TAG_DATA:
            elapsed_time_absence=time.time()-tag[3]
            if elapsed_time_absence>=tag[2] : # sleep execute after the first Home check.
                logging.warning('Tag %s not seen since %i sec => update absence',tag[0],elapsed_time_absence)
                threadReqAway = threading.Thread(target=request_thread,args=(tag[4],"Off",tag[0]))
                threadReqAway.start()

        while True:
            time.sleep(ABSENCE_FREQUENCY)
            for tag in TAG_DATA:
                elapsed_time_absence=time.time()-tag[3]
                if elapsed_time_absence>=tag[2] and elapsed_time_absence<(tag[2]+ABSENCE_FREQUENCY) :  #update when > timeout ant only 1 time , before the next absence check [>15sec <30sec]
                    logging.warning('Tag %s not seen since %i sec => update absence',tag[0],elapsed_time_absence)
                    threadReqAway = threading.Thread(target=request_thread,args=(tag[4],"Off",tag[0]))
                    threadReqAway.start()

FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
if globals().has_key('logOutFilename') :
    logging.basicConfig(format=FORMAT,filename=logOutFilename,level=logLevel)
else:
    logging.basicConfig(format=FORMAT,level=logLevel)

#Reset Bluetooth interface, hci0
os.system("sudo hciconfig hci0 down")
os.system("sudo hciconfig hci0 up")

#Make sure device is up
interface = subprocess.Popen(["sudo hciconfig"], stdout=subprocess.PIPE, shell=True)
(output, err) = interface.communicate()

if "RUNNING" in output: #Check return of hciconfig to make sure it's up
    logging.debug('Ok hci0 interface Up n running !')
else:
    logging.critical('Error : hci0 interface not Running. Do you have a BLE device connected to hci0 ? Check with hciconfig !')
    sys.exit(1)

devId = 0
try:
    sock = bluez.hci_open_dev(devId)
    logging.debug('Connect to bluetooth device %i',devId)
except:
    logging.critical('Unable to connect to bluetooth device...')
    sys.exit(1)

old_filter = sock.getsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, 14)
hci_toggle_le_scan(sock, 0x01)

for tag in TAG_DATA:
    tag[3]=time.time()-tag[2]  # initiate lastseen of every beacon "timeout" sec ago. = Every beacon will be AWAY. And so, beacons here will update

th=CheckAbsenceThread()
th.daemon=True
th.start()

while True:
    old_filter = sock.getsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, 14)
    flt = bluez.hci_filter_new()
    bluez.hci_filter_all_events(flt)
    bluez.hci_filter_set_ptype(flt, bluez.HCI_EVENT_PKT)
    sock.setsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, flt )

    pkt = sock.recv(255)
    ptype, event, plen = struct.unpack("BBB", pkt[:3])

    if event == bluez.EVT_INQUIRY_RESULT_WITH_RSSI:
            i =0
    elif event == bluez.EVT_NUM_COMP_PKTS:
            i =0
    elif event == bluez.EVT_DISCONN_COMPLETE:
            i =0
    elif event == LE_META_EVENT:
            subevent, = struct.unpack("B", pkt[3])
            pkt = pkt[4:]
            if subevent == EVT_LE_CONN_COMPLETE:
                le_handle_connection_complete(pkt)
            elif subevent == EVT_LE_ADVERTISING_REPORT:
                num_reports = struct.unpack("B", pkt[0])[0]
                report_pkt_offset = 0
                for i in range(0, num_reports):
                            #logging.debug('UDID: ', print_packet(pkt[report_pkt_offset -22: report_pkt_offset - 6]))
                            #logging.debug('MAJOR: ', print_packet(pkt[report_pkt_offset -6: report_pkt_offset - 4]))
                            #logging.debug('MINOR: ', print_packet(pkt[report_pkt_offset -4: report_pkt_offset - 2]))
                            #logging.debug('MAC address: ', packed_bdaddr_to_string(pkt[report_pkt_offset + 3:report_pkt_offset + 9]))
                            #logging.debug('Unknown:', struct.unpack("b", pkt[report_pkt_offset -2])) # don't know what this byte is.  It's NOT TXPower ?
                            #logging.debug('RSSI: %s', struct.unpack("b", pkt[report_pkt_offset -1])) #  Signal strenght !
                            macAdressSeen=packed_bdaddr_to_string(pkt[report_pkt_offset + 3:report_pkt_offset + 9])
                            for tag in TAG_DATA:
                                if macAdressSeen.lower() == tag[1].lower():  # MAC ADDRESS
                                    logging.debug('Tag %s Detected %s - RSSI %s - DATA unknown %s', tag[0], macAdressSeen, struct.unpack("b", pkt[report_pkt_offset -1]),struct.unpack("b", pkt[report_pkt_offset -2])) #  Signal strenght + unknown (hope it's battery life).
                                    elapsed_time=time.time()-tag[3]  # lastseen
                                    if elapsed_time>=tag[2] : # Upadate only once : after an absence (>timeout). It's back again
                                        threadReqHome = threading.Thread(target=request_thread,args=(tag[4],"On",tag[0]))  # IDX, RSSI, name
                                        threadReqHome.start()
                                        logging.warning('Tag %s seen after an absence of %i sec : update presence',tag[0],elapsed_time)
                                    tag[3]=time.time()   # update lastseen

    sock.setsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, old_filter )
