"""
Extending on demo-03, implements an event callback we can use to process the
incoming data.

"""

import sys
import time
import struct
import array

from ant.core import driver
from ant.core import node
from ant.core import event
from ant.core import message
from ant.core.constants import *
import traceback

from config import *

import Pyro4
import atexit

NETKEY = '\xB9\xA5\x21\xFB\xBD\x72\xC3\x45'

#channel = None


def exit():
    channel.close()
    channel.unassign()


# A run-the-mill event listener
class HRMListener(event.EventCallback):
    def process(self, msg):
        if isinstance(msg, message.ChannelBroadcastDataMessage):
            print 'Heart Rate:', ord(msg.payload[-1])

# Initialize
#stick = driver.USB2Driver(SERIAL, log=LOG)
#antnode = node.Node(stick)
#antnode.start()

#with Pyro4.core.Proxy("PYRONAME:pyant.server") as antnode:
antnode = Pyro4.core.Proxy("PYRONAME:pyant.server")
# Setup channel
key = node.NetworkKey('N:ANT+', NETKEY)
antnode.setNetworkKey(0, key)
print 1
channel = antnode.getFreeChannel()
print 2
channel.name = 'C:HRM'
channel.assign('N:ANT+', CHANNEL_TYPE_TWOWAY_TRANSMIT)
channel.setID(0x78,0x1234, 1)
channel.setSearchTimeout(50)
channel.setPeriod(8070)
channel.setFrequency(57)

msg = message.ChannelLibConfigMessage()
driver = antnode.getDriver()
driver.write(msg.encode())

msg = message.ChannelEnableExtendedMessage(enable=True)
driver = antnode.getDriver()
driver.write(msg.encode())  

print 3
channel.open()
print 4
atexit.register(exit)





# Setup callback
# Note: We could also register an event listener for non-channel events by
# calling registerEventListener() on antnode rather than channel.
#channel.registerCallback(HRMListener())

# Wait
#print "Listening for HR monitor events (120 seconds)..."
#time.sleep(120)

hr = 50
hr_change = 2
hr_seq = 0

# length = data +1
def get_pack_args(data,sync = MESSAGE_TX_SYNC):
    args = []
    channel = 0
    msg_id = MESSAGE_CHANNEL_BROADCAST_DATA
    length = 4 + len(data) + 1
    args.append('B'*(length))
    args.append(sync)
    # data + chksum
    args.append(len(data) +1)
    args.append(msg_id)
    args.append(channel)
    args.extend(data)

    args = append_checksum(args)

    return args

def append_checksum(args):
    checksum = 0
    for i,arg in enumerate(args[1:],start =1):
        checksum = ((checksum ^ arg))  % 0xFF
    args.append(checksum)
    print args
    return args
                

timestamp = 1234
packed = struct.pack('<H', timestamp)
timestamp_bytes = struct.unpack('BB',packed)

device_number = 4567
packed = struct.pack('<H', device_number)
number = struct.unpack('BB',packed)

device_type = 18
transmission_type = 28

rssi_type = 71
rssi_value = 167
rssi_threshold = 179


buffer_data = [2,3,4,5,6,7,8,9,0xE0,number[0],number[1],device_type,transmission_type,rssi_type,rssi_value,rssi_threshold,timestamp_bytes[0],timestamp_bytes[1]]
buffer_ = struct.pack(*get_pack_args(buffer_data))

buffer_ = struct.pack(*get_pack_args(buffer_data))
msg = message.Message()
msg.decode(buffer_)

try:
    while True:
        msg = message.ChannelBroadcastDataMessage()
        msg.setChannelNumber(channel.getNumber())
        msg.setType(MESSAGE_CHANNEL_EXTENDED_BROADCAST_DATA)
        
        payload = msg.getPayload()
        hr_seq = hr_seq + 1;
        if (hr_seq >= 256):
            hr_seq = 0    
        hr = hr + hr_change
        if hr > 200 or hr < 40:
            hr_change = -hr_change
        #print type(payload)
        #print ord(payload[0])
        #bytes = bytearray(payload)
        #bytes[-1] = chr(hr)
        #bytes[-2] = chr(hr_seq)
        #bytes[0] = chr(channel.number)
        #print chr(channel.number)
        #test = struct.unpack('BBBBBBBB',payload)
        #test[-1] = chr(hr)
        #test[-2] = chr(hr_seq)
        #test[0] = chr(channel.number)
        pack = struct.pack('B' * 8,1,2,3,4,5,6,hr_seq,hr)
        payload = pack
        msg.setRawData(payload)
        print len(msg.getPayload())
        #print 'Heart Rate:', ord(msg.payload[-1])
        driver = antnode.getDriver()
        driver.write(msg.encode()) 
        time.sleep(0.1)
except Exception, e:
    print e
    tb = traceback.format_exc()
    print tb
    #pass

# Shutdown
#channel.close()
#channel.unassign()
#antnode.stop()
