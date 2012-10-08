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

NETKEY = '\xB9\xA5\x21\xFB\xBD\x72\xC3\x45'

# A run-the-mill event listener
class HRMListener(event.EventCallback):
    def process(self, msg):
        if isinstance(msg, message.ChannelBroadcastDataMessage):
            print 'Heart Rate:', ord(msg.payload[-1])

# Initialize
stick = driver.USB2Driver(SERIAL, log=LOG)
antnode = node.Node(stick)
antnode.start()

# Setup channel
key = node.NetworkKey('N:ANT+', NETKEY)
antnode.setNetworkKey(0, key)
channel = antnode.getFreeChannel()
channel.name = 'C:HRM'
channel.assign('N:ANT+', CHANNEL_TYPE_TWOWAY_TRANSMIT)
channel.setID(0x78,0x1234, 1)
channel.setSearchTimeout(50)
channel.setPeriod(8070)
channel.setFrequency(57)
channel.open()

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

msg = message.ChannelLibConfigMessage(enable=False)
driver = antnode.getDriver()
driver.write(msg.encode())

msg = message.ChannelEnableExtendedMessage(enable=False)
driver = antnode.getDriver()
driver.write(msg.encode())  

try:
    while True:
        msg = message.ChannelBroadcastDataMessage()
        payload = msg.getPayload()
        hr_seq = hr_seq + 1;
        if (hr_seq >= 256):
            hr_seq = 0    
        #hr = hr + hr_change
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
        pack = struct.pack('B' * 9,0,0,0,0,0,0,0,hr_seq,hr)
        payload = pack
        msg.setPayload(payload)
        #print 'Heart Rate:', ord(msg.payload[-1])
        channel.node.driver.write(msg.encode()) 
        time.sleep(0.1)
except Exception, e:
    print e
    tb = traceback.format_exc()
    print tb
    #pass

# Shutdown
channel.close()
channel.unassign()
antnode.stop()
