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
antnode = Pyro4.core.Proxy("PYRONAME:pyant.server2")
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


msg_list = []
counter = 0

for i in range(0,3):
    msg = message.ChannelBurstDataMessage()
    data = msg.getRawData()
    unpacked_data = struct.unpack('B'*8,data)
    new_data = list()
    for i,item in enumerate(unpacked_data):
        new_data.append(counter)
        counter += 1
    args = ['B'*8]
    args.extend(new_data)
    new_packed = struct.pack(*args)
    msg.setRawData(new_packed)
    msg_list.append(msg)

    
try:
    while True:
        msg = message.ChannelBurstDataMessage()
        channel.sendBurst(msg_list)
        
        #print first
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

        time.sleep(5)
except Exception, e:
    print e
    tb = traceback.format_exc()
    print tb
    #pass

# Shutdown
#channel.close()
#channel.unassign()
#antnode.stop()
