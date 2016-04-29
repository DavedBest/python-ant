# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2011, Martín Raúl Villalba
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
#
##############################################################################
# pylint: disable=missing-docstring,invalid-name,too-many-ancestors

from __future__ import division, absolute_import, print_function, unicode_literals

from struct import pack, unpack

from six import with_metaclass

from ant.core import constants
from ant.core.constants import MESSAGE_TX_SYNC, RESPONSE_NO_ERROR
from ant.core.exceptions import MessageError


class MessageType(type):
    
    def __init__(cls, name, bases, dict_):
        super(MessageType, cls).__init__(name, bases, dict_)
        type_ = cls.type
        if type_ is not None:
            cls.TYPES[type_] = cls
    
    def __call__(cls, *args, **kwargs):
        if cls.type is not None:
            return super(MessageType, cls).__call__(*args, **kwargs)
        
        type_ = kwargs.get('type')
        if type_ is None:
            raise RuntimeError("Message' cannot be untyped")
        del kwargs['type']
        
        msgType = cls.TYPES.get(type_)
        if msgType is not None:
            return msgType(*args, **kwargs)
        
        if 0x00 <= type_ <= 0xFF:
            msg = super(MessageType, cls).__call__(*args, **kwargs)
            msg.type = type_
            return msg
        else:
            raise MessageError('Could not set type (type out of range).',
                               internal=Message.CORRUPTED)


MSG_HEADER_SIZE = 3
MSG_FOOTER_SIZE = 1

class Message(with_metaclass(MessageType)):
    TYPES = {}
    type = None
    PAYLOAD_SIZE = 9
    
    INCOMPLETE = 'incomplete'
    CORRUPTED = 'corrupted'
    MALFORMED = 'malformed'
    
    def __init__(self, payload=None, sync=MESSAGE_TX_SYNC):
        self._payload = None
        self.payload = payload if payload is not None else bytearray()
        self._sync = sync
    
    @property
    def payload(self):
        return self._payload
    @payload.setter
    def payload(self, payload):
        if len(payload) > self.PAYLOAD_SIZE:
            raise MessageError('Could not set payload (payload too long).',
                               internal=Message.MALFORMED)
        self._payload = payload
    
    @property
    def sync(self):
        return self._sync
    @sync.setter
    def sync(self, sync):
        if sync not in (constants.MESSAGE_TX_SYNC, constants.MESSAGE_TX_SYNC_LSB):
            raise MessageError('Could not decode (expected TX sync).',
                               internal=Message.CORRUPTED)
        self.sync = sync
    
    @property
    def checksum(self):
        checksum = MESSAGE_TX_SYNC ^ len(self._payload) ^ self.type
        for byte in self._payload:
            checksum ^= byte
        return checksum
    
    def encode(self):
        raw, payload = bytearray(len(self)), self._payload
        raw[0:MSG_HEADER_SIZE-1] = ( MESSAGE_TX_SYNC, len(payload), self.type )
        raw[MSG_HEADER_SIZE:-MSG_FOOTER_SIZE] = payload
        raw[-1] = self.checksum
        return raw
    
    @classmethod
    def decode(cls, raw):
        raw = bytearray(raw)
        if len(raw) < 5:
            raise MessageError('Could not decode (message is incomplete).',
                               internal=Message.INCOMPLETE)
        
        sync, length, type_ = raw[:MSG_HEADER_SIZE]
        
        if len(raw) < (length + MSG_HEADER_SIZE + MSG_FOOTER_SIZE):
            raise MessageError('Could not decode (message is incomplete).',
                               internal=Message.INCOMPLETE)
        
        if length == Message.PAYLOAD_SIZE:
            cls = Message
        elif length == LegacyExtendedMessage.PAYLOAD_SIZE:
            cls = LegacyExtendedMessage
        else:
            cls = FlaggedExtendedMessage
        msg = cls(type=type_, sync=sync)
        msg.payload = raw[MSG_HEADER_SIZE:length + MSG_HEADER_SIZE]
        
        if msg.checksum != raw[length + MSG_HEADER_SIZE]:
            raise MessageError('Could not decode (bad checksum).',
                               internal=Message.CORRUPTED)
        
        return msg
    
    def __len__(self):
        return len(self._payload) + MSG_HEADER_SIZE + MSG_FOOTER_SIZE
    
    def __str__(self, data=None):
        rawstr = '<' + self.__class__.__name__
        if data is not None:
            rawstr += ': ' + data
        return rawstr + '>'


class ChannelData(object):
    channelDataOffset = 0
    _payload = None
    SIZE = 4
    
    @property
    def deviceNumber(self):
        offset = self.channelDataOffset
        return unpack(b'<H', bytes(self._payload[offset:offset+2]))[0]
    @deviceNumber.setter
    def deviceNumber(self, deviceNumber):
        offset = self.channelDataOffset
        self._payload[offset:offset+2] = pack(b'<H', deviceNumber)
    
    @property
    def deviceType(self):
        return self._payload[self.channelDataOffset+2]
    @deviceType.setter
    def deviceType(self, deviceType):
        self._payload[self.channelDataOffset+2] = deviceType
    
    @property
    def transmissionType(self):
        return self._payload[self.channelDataOffset+3]
    @transmissionType.setter
    def transmissionType(self, transmissionType):
        self._payload[self.channelDataOffset+3] = transmissionType


class FlaggedExtendedMessage(Message, ChannelData):
    channelDataOffset = 10
    
    ENABLE_CHANNEL_ID = 0x80
    ENABLE_RSSI_OUTPUT = 0x40
    ENABLE_RX_TIMESTAMP = 0x20
    
    def __init__(self, flag=0x00, payload='\x00'*11, sync=MESSAGE_TX_SYNC):
        super(FlaggedExtendedMessage, self).__init__(payload=payload, sync=sync)
        self.rssiType = None
        self.rssiValue = None
        self.rssiThreshold = None
        
        self.timestamp = None
        
        self.isEnabledChannelID = False
        self.isEnabledRSSIOutput = False
        self.isEnabledRXTimestamp = False
        
        self.decodeFlag(flag)

    def decodeFlag(self, flag):
        self.isEnabledChannelID = (flag & FlaggedExtendedMessage.ENABLE_CHANNEL_ID) == \
                                   FlaggedExtendedMessage.ENABLE_CHANNEL_ID
        self.isEnabledRSSIOutput = (flag & FlaggedExtendedMessage.ENABLE_RSSI_OUTPUT) == \
                                    FlaggedExtendedMessage.ENABLE_RSSI_OUTPUT
        self.isEnabledRXTimestamp = (flag & FlaggedExtendedMessage.ENABLE_RX_TIMESTAMP) \
                                  == FlaggedExtendedMessage.ENABLE_RX_TIMESTAMP
    
    def encodeFlag(self, isEnabledChannelID=False, isEnabledRSSIOutput=False,
                   isEnabledRXTimestamp=False):
        flag = 0x00
        if isEnabledChannelID:
            flag |= FlaggedExtendedMessage.ENABLE_CHANNEL_ID
        if isEnabledRSSIOutput:
            flag |= FlaggedExtendedMessage.ENABLE_RSSI_OUTPUT
        if isEnabledRXTimestamp:
            flag |= FlaggedExtendedMessage.ENABLE_RX_TIMESTAMP
        self.flag = flag
        return flag
    
    @payload.setter
    def payload(self, payload):  # pylint: disable=arguments-differ
        if len(payload) < 10:
            raise MessageError('Too few bytes for an extended message (too few bytes)')
        
        self.decodeFlag(payload[9])
        
        offset = FlaggedExtendedMessage.channelDataOffset
        if self.isEnabledChannelID:
            self.isEnabledChannelID = offset
            offset += ChannelData.SIZE
        if self.isEnabledRSSIOutput:
            self.isEnabledRSSIOutput = offset
            offset += 3
        if self.isEnabledRXTimestamp:
            self.isEnabledRXTimestamp = offset
            offset += 2
        self.PAYLOAD_SIZE = offset
        
        super(FlaggedExtendedMessage, self).paylod = payload

    
    @property
    def flag(self):
        return self._payload[9]
    @flag.setter
    def flag(self, flag):
        if not ~FlaggedExtendedMessage.ENABLE_CHANNEL_ID & \
               ~FlaggedExtendedMessage.ENABLE_RSSI_OUTPUT & \
               ~FlaggedExtendedMessage.ENABLE_RX_TIMESTAMP & \
               flag:
            raise MessageError("wrong flag")
        self.decodeFlag(flag)
        self._payload[9] = flag
    
    def _getEnableRSSIOutput(self, offset):
        enableRSSIOutput = self.isEnabledRSSIOutput
        if enableRSSIOutput is False:
            raise MessageError("data not available")
        return self._payload[enableRSSIOutput + offset]
    def _setEnableRSSIOutput(self, data, offset):
        enableRSSIOutput = self.isEnabledRSSIOutput
        if enableRSSIOutput is False:
            raise MessageError("data not available")
        self._payload[enableRSSIOutput + offset] = data
    
    @property
    def rssiType(self):
        return self._getEnableRSSIOutput(0)
    @rssiType.setter
    def rssiType(self, rssiType):
        self._setEnableRSSIOutput(rssiType, 0)
    
    @property
    def rssiValue(self):
        return self._getEnableRSSIOutput(1)
    @rssiValue.setter
    def rssiValue(self, rssiValue):
        return self._setEnableRSSIOutput(rssiValue, 1)
    
    @property
    def rssiThreshold(self):
        return self._getEnableRSSIOutput(2)
    @rssiThreshold.setter
    def rssiThreshold(self, rssiThreshold):
        return self._setEnableRSSIOutput(rssiThreshold, 2)
    
    @property
    def rxTimestamp(self):
        enableRXTimestamp = self.isEnabledRSSIOutput
        if enableRXTimestamp is False:
            raise MessageError("rssiType not available")
        return self._payload[enableRXTimestamp + 2]
    @rxTimestamp.setter
    def rxTimestamp(self, rxTimestamp):
        enableRXTimestamp = self.isEnabledRXTimestamp
        if enableRXTimestamp is False:
            raise MessageError("rssiType not available")
        self._payload[enableRXTimestamp] = rxTimestamp


class LegacyExtendedMessage(Message, ChannelData):
    channelDataOffset = 5
    PAYLOAD_SIZE = 13
    
    def __init__(self, payload=bytearray(LegacyExtendedMessage.PAYLOAD_SIZE),
                 sync=MESSAGE_TX_SYNC):
        super(LegacyExtendedMessage, self).__init__(payload=payload, sync=sync)



class ChannelMessage(Message):
    def __init__(self, payload=b'', number=0x00, *args, **kwargs):
        super(ChannelMessage, self).__init__(bytearray(1) + payload, *args, **kwargs)
        self.channelNumber = number
    
    @property
    def channelNumber(self):
        return self._payload[0]
    @channelNumber.setter
    def channelNumber(self, number):
        if (number > 0xFF) or (number < 0x00):
            raise MessageError('Could not set channel number (out of range).')
        
        self._payload[0] = number
    
    def __str__(self, data=None):
        rawstr = "C(%d)" % self.channelNumber
        if data is not None:
            rawstr += ': ' + data
        return super(ChannelMessage, self).__str__(data=rawstr)


# Config messages

class ChannelLibConfigMessage(Message):
    type = constants.MESSAGE_LIB_CONFIG
    
    def __init__(self, mask=FlaggedExtendedMessage.ENABLE_RX_TIMESTAMP | \
                            FlaggedExtendedMessage.ENABLE_CHANNEL_ID):
        # usb2 stick doesn't support rssi | ExtendedMessageFlags.ENABLE_RSSI_OUTPUT 
        # filler byte required
        payload = pack('BB', 0, mask)
        super(ChannelLibConfigMessage, self).__init__(payload)


class ChannelEnableExtendedMessage(Message):
    type = constants.MESSAGE_ENABLE_EXTENDED_MESSAGES
    
    def __init__(self, enable=True):
        payload = pack('BB', 0, 1 if enable else 0)
        super(ChannelEnableExtendedMessage, self).__init__(payload)


class ChannelUnassignMessage(ChannelMessage):
    type = constants.MESSAGE_CHANNEL_UNASSIGN
    
    def __init__(self, number=0x00):
        super(ChannelUnassignMessage, self).__init__(number=number)


class ChannelAssignMessage(ChannelMessage):
    type = constants.MESSAGE_CHANNEL_ASSIGN
    
    def __init__(self, number=0x00, channelType=0x00, network=0x00):
        super(ChannelAssignMessage, self).__init__(payload=bytearray(2), number=number)
        self.channelType = channelType
        self.networkNumber = network
    
    @property
    def channelType(self):
        return self._payload[1]
    @channelType.setter
    def channelType(self, type_):
        self._payload[1] = type_
    
    @property
    def networkNumber(self):
        return self._payload[2]
    @networkNumber.setter
    def networkNumber(self, number):
        self._payload[2] = number


class ChannelIDMessage(ChannelMessage, ChannelData):
    _offset = 1
    type = constants.MESSAGE_CHANNEL_ID
    
    def __init__(self, number=0x00,
                 deviceNumber=0x0000, deviceType=0x00, transmissionType=0x00):
        super(ChannelIDMessage, self).__init__(payload=bytearray(4), number=number,
                                               deviceNumber=deviceNumber,
                                               deviceType=deviceType,
                                               transmissionType=transmissionType)


class ChannelPeriodMessage(ChannelMessage):
    type = constants.MESSAGE_CHANNEL_PERIOD
    
    def __init__(self, number=0x00, period=8192):
        super(ChannelPeriodMessage, self).__init__(payload=bytearray(2), number=number)
        self.channelPeriod = period
    
    @property
    def channelPeriod(self):
        return unpack('<H', bytes(self._payload[1:3]))[0]
    @channelPeriod.setter
    def channelPeriod(self, period):
        self._payload[1:3] = pack('<H', period)


class ChannelSearchTimeoutMessage(ChannelMessage):
    type = constants.MESSAGE_CHANNEL_SEARCH_TIMEOUT
    
    def __init__(self, number=0x00, timeout=0xFF):
        super(ChannelSearchTimeoutMessage, self).__init__(payload=bytearray(1),
                                                          number=number)
        self.timeout = timeout
    
    @property
    def timeout(self):
        return self._payload[1]
    @timeout.setter
    def timeout(self, timeout):
        self._payload[1] = timeout


class ChannelFrequencyMessage(ChannelMessage):
    type = constants.MESSAGE_CHANNEL_FREQUENCY
    
    def __init__(self, number=0x00, frequency=66):
        super(ChannelFrequencyMessage, self).__init__(payload=bytearray(1), number=number)
        self.frequency = frequency
    
    @property
    def frequency(self):
        return self._payload[1]
    @frequency.setter
    def frequency(self, frequency):
        self._payload[1] = frequency


class ChannelTXPowerMessage(ChannelMessage):
    type = constants.MESSAGE_CHANNEL_TX_POWER
    
    def __init__(self, number=0x00, power=0x00):
        super(ChannelTXPowerMessage, self).__init__(payload=bytearray(1), number=number)
        self.power = power
    
    @property
    def power(self):
        return self._payload[1]
    @power.setter
    def power(self, power):
        self._payload[1] = power


class NetworkKeyMessage(Message):
    type = constants.MESSAGE_NETWORK_KEY
    
    def __init__(self, number=0x00, key=b'\x00' * 8):
        super(NetworkKeyMessage, self).__init__(payload=bytearray(9))
        self.number = number
        self.key = key
    
    @property
    def number(self):
        return self._payload[0]
    @number.setter
    def number(self, number):
        self._payload[0] = number
    
    @property
    def key(self):
        return self._payload[1:]
    @key.setter
    def key(self, key):
        self._payload[1:] = key


class TXPowerMessage(Message):
    type = constants.MESSAGE_TX_POWER
    
    def __init__(self, power=0x00):
        super(TXPowerMessage, self).__init__(payload=bytearray(2))
        self.power = power
    
    @property
    def power(self):
        return self._payload[1]
    @power.setter
    def power(self, power):
        self._payload[1] = power


# Control messages
class SystemResetMessage(Message):
    type = constants.MESSAGE_SYSTEM_RESET
    
    def __init__(self):
        super(SystemResetMessage, self).__init__(payload=bytearray(1))


class ChannelOpenMessage(ChannelMessage):
    type = constants.MESSAGE_CHANNEL_OPEN
    
    def __init__(self, number=0x00):
        super(ChannelOpenMessage, self).__init__(number=number)


class ChannelOpenRxScanMessage(ChannelMessage):
    type = constants.MESSAGE_OPEN_RX_SCAN
    
    def __init__(self, number=0x00):
        super(ChannelOpenRxScanMessage, self).__init__(number=number)


class ChannelCloseMessage(ChannelMessage):
    type = constants.MESSAGE_CHANNEL_CLOSE
    
    def __init__(self, number=0x00):
        super(ChannelCloseMessage, self).__init__(number=number)


class ChannelRequestMessage(ChannelMessage):
    type = constants.MESSAGE_CHANNEL_REQUEST
    
    def __init__(self, number=0x00, messageID=constants.MESSAGE_CHANNEL_STATUS):
        super(ChannelRequestMessage, self).__init__(payload=bytearray(1), number=number)
        self.messageID = messageID
    
    @property
    def messageID(self):
        return self._payload[1]
    @messageID.setter
    def messageID(self, messageID):
        if (messageID > 0xFF) or (messageID < 0x00):
            raise MessageError('Could not set message ID (out of range).')
        
        self._payload[1] = messageID


class BurstChannelMixin(object):
    CHANNEL_MASK = 0b11111
    SEQUENCE_MASK = 0b111 << 5
    payload = None  # for linting
    
    @property
    def channelNumber(self):
        return self.payload[0] & BurstChannelMixin.CHANNEL_MASK
    @channelNumber.setter
    def channelNumber(self, number):
        if (number > BurstChannelMixin.CHANNEL_MASK) or (number < 0x00):
            raise MessageError('Could not set channel number ' \
                                   '(out of range).')
        payload = self.payload
        burstSequence = ord(payload[0]) & BurstChannelMixin.SEQUENCE_MASK
        payload[0] = chr(number | burstSequence << 5)
        self.payload = payload
    
    @property
    def sequenceCode(self):
        payload = self.payload
        return ord(payload[0]) & BurstChannelMixin.SEQUENCE_MASK
    @sequenceCode.setter
    def sequenceCode(self, code):
        if (code > 0b111) or (code < 0x00):
            raise MessageError('Could not set sequence code ' \
                                   '(out of range).')
        payload = self.payload
        number = ord(payload[0]) & BurstChannelMixin.CHANNEL_MASK
        payload[0] = chr(number | code << 5)
        self.payload = payload


# Data messages

class ChannelDataMessage(ChannelMessage):
    def __init__(self, number=0x00, data=b'\x00' * 8):
        super(ChannelDataMessage, self).__init__(payload=data, number=number)

class ChannelBroadcastDataMessage(ChannelDataMessage):
    type = constants.MESSAGE_CHANNEL_BROADCAST_DATA

class ChannelAcknowledgedDataMessage(ChannelDataMessage):
    type = constants.MESSAGE_CHANNEL_ACKNOWLEDGED_DATA

class ChannelBurstDataMessage(ChannelDataMessage):
    type = constants.MESSAGE_CHANNEL_BURST_DATA


#legacy extended data

class LegacyChannelMessage(ChannelMessage, LegacyExtendedMessage):
    def __init__(self, number=0x00, data=b'\x00' * 12):
        super(LegacyChannelMessage, self).__init__(payload=data, number=number)

class LegacyChannelBroadcastDataMessage(LegacyChannelMessage):
    type = constants.MESSAGE_CHANNEL_EXTENDED_BROADCAST_DATA

class LegacyChannelAcknowledgedDataMessage(LegacyChannelMessage):
    type = constants.MESSAGE_CHANNEL_EXTENDED_ACKNOWLEDGED_DATA

class LegacyChannelBurstDataMessage(BurstChannelMixin, LegacyChannelMessage):
    type = constants.MESSAGE_CHANNEL_EXTENDED_BURST_DATA


#extended data

class ExtendedChannelMessage(ChannelMessage, FlaggedExtendedMessage):
    def __init__(self, number=0x00, data=b'\x00' * 10):
        super(ExtendedChannelMessage, self).__init__(payload=data, number=number)

class ExtendedChannelBroadcastDataMessage(ChannelBroadcastDataMessage,
                                          ExtendedChannelMessage):
    type = constants.MESSAGE_CHANNEL_BROADCAST_DATA

class ExtendedChannelAcknowledgedDataMessage(ChannelAcknowledgedDataMessage,
                                             ExtendedChannelMessage):
    type = constants.MESSAGE_CHANNEL_ACKNOWLEDGED_DATA

class ExtendedChannelBurstDataMessage(ChannelBurstDataMessage, ExtendedChannelMessage):
    type = constants.MESSAGE_CHANNEL_BURST_DATA


# Channel event messages
class ChannelEventResponseMessage(ChannelMessage):
    type = constants.MESSAGE_CHANNEL_EVENT
    
    def __init__(self, number=0x00, message_id=0x00, message_code=0x00):
        super(ChannelEventResponseMessage, self).__init__(payload=bytearray(2),
                                                          number=number)
        self.messageID = message_id
        self.messageCode = message_code
    
    @property
    def messageID(self):
        return self._payload[1]
    @messageID.setter
    def messageID(self, message_id):
        if (message_id > 0xFF) or (message_id < 0x00):
            raise MessageError('Could not set message ID (out of range).')
        
        self._payload[1] = message_id
    
    @property
    def messageCode(self):
        return self._payload[2]
    @messageCode.setter
    def messageCode(self, message_code):
        if (message_code > 0xFF) or (message_code < 0x00):
            raise MessageError('Could not set message code (out of range).')
        
        self._payload[2] = message_code
    
    def __str__(self):  # pylint: disable=W0221
        msgCode = self.messageCode
        if self.messageID != 1:
            return "<ChannelResponse: '%s' on C(%d): %s>" % (
                        self.TYPES[self.messageID].__name__, self.channelNumber,
                        'OK' if msgCode == RESPONSE_NO_ERROR else '0x%.2x' % msgCode)
        else:
            return "<ChannelEvent: C(%d): 0x%.2x>" % (self.channelNumber, msgCode)


# Requested response messages
class ChannelStatusMessage(ChannelMessage):
    type = constants.MESSAGE_CHANNEL_STATUS
    
    def __init__(self, number=0x00, status=0x00):
        super(ChannelStatusMessage, self).__init__(payload=bytearray(1), number=number)
        self.status = status
    
    @property
    def status(self):
        return self._payload[1]
    @status.setter
    def status(self, status):
        if (status > 0xFF) or (status < 0x00):
            raise MessageError('Could not set channel status (out of range).')
        
        self._payload[1] = status


class VersionMessage(Message):
    type = constants.MESSAGE_VERSION
    
    def __init__(self, version=b'\x00' * 9):
        super(VersionMessage, self).__init__(payload=bytearray(9))
        self.version = version
    
    @property
    def version(self):
        return self._payload
    @version.setter
    def version(self, version):
        if len(version) != 9:
            raise MessageError('Could not set ANT version (expected 9 bytes).')
        
        self.payload = bytearray(version)


class StartupMessage(Message):
    type = constants.MESSAGE_STARTUP
    
    def __init__(self, startupMessage=0x00):
        super(StartupMessage, self).__init__(payload=bytearray(1))
        self.startupMessage = startupMessage
    
    @property
    def startupMessage(self):
        return self._payload[0]
    @startupMessage.setter
    def startupMessage(self, startupMessage):
        if (startupMessage > 0xFF) or (startupMessage < 0x00):
            raise MessageError('Could not set start-up message (out of range).')
        self._payload[0] = startupMessage
    
    def isPowerOnReset(self):
        return self.startupMessage == 0x00
    
    def _hasFlag(self, pad):
        return self.startupMessage & (1 << pad) != 0
    
    def isHardwareLineReset(self):
        return self._hasFlag(0)
    
    def isWatchDogReset(self):
        return self._hasFlag(1)
    
    def isCommandReset(self):
        return self._hasFlag(5)
    
    def isSynchronousReset(self):
        return self._hasFlag(6)
    
    def isSuspendReset(self):
        return self._hasFlag(7)


class CapabilitiesMessage(Message):
    type = constants.MESSAGE_CAPABILITIES
    def __init__(self, max_channels=0x00, max_nets=0x00, std_opts=0x00,
                 adv_opts=0x00, adv_opts2=0x00):
        super(CapabilitiesMessage, self).__init__(payload=bytearray(4))
        self.maxChannels = max_channels
        self.maxNetworks = max_nets
        self.stdOptions = std_opts
        self.advOptions = adv_opts
        if adv_opts2 is not None:
            self.advOptions2 = adv_opts2
    
    @property
    def maxChannels(self):
        return self._payload[0]
    @maxChannels.setter
    def maxChannels(self, num):
        if (num > 0xFF) or (num < 0x00):
            raise MessageError('Could not set max channels ' \
                                   '(out of range).')
        self._payload[0] = num
    
    @property
    def maxNetworks(self):
        return self._payload[1]
    @maxNetworks.setter
    def maxNetworks(self, num):
        if (num > 0xFF) or (num < 0x00):
            raise MessageError('Could not set max networks (out of range).')
        self._payload[1] = num
    
    @property
    def stdOptions(self):
        return self._payload[2]
    @stdOptions.setter
    def stdOptions(self, num):
        if (num > 0xFF) or (num < 0x00):
            raise MessageError('Could not set std options (out of range).')
        self._payload[2] = num
    
    @property
    def advOptions(self):
        return self._payload[3]
    @advOptions.setter
    def advOptions(self, num):
        if (num > 0xFF) or (num < 0x00):
            raise MessageError('Could not set adv options (out of range).')
        self._payload[3] = num
    
    @property
    def advOptions2(self):
        return self._payload[4] if len(self._payload) == 5 else 0x00
    @advOptions2.setter
    def advOptions2(self, num):
        if (num > 0xFF) or (num < 0x00):
            raise MessageError('Could not set adv options 2 (out of range).')
        if len(self._payload) == 4:
            self._payload.append(0)
        self._payload[4] = num


class SerialNumberMessage(Message):
    type = constants.MESSAGE_SERIAL_NUMBER
    
    def __init__(self, serial=b'\x00' * 4):
        super(SerialNumberMessage, self).__init__()
        self.serialNumber = serial
    
    @property
    def serialNumber(self):
        return self._payload
    @serialNumber.setter
    def serialNumber(self, serial):
        if len(serial) != 4:
            raise MessageError('Could not set serial number (expected 4 bytes).')
        
        self.payload = bytearray(serial)


# utilities for burst messages

class BurstSequence(object):
    
    INIT_VAL    = 0b00
    MAX_VAL     = 0b011
    WRAP_VAL    = 0b001
    FINISH_VAL  = 0b110
    MAX_CHANNEL = 0b11111
    
    def __init__(self):
        self.current_val = BurstSequence.INIT_VAL
    
    def next(self):
        rtn = self.current_val
        if self.current_val == BurstSequence.MAX_VAL:
            self.current_val = BurstSequence.INIT_VAL
        elif self.current_val > BurstSequence.FINISH_VAL:
            raise ValueError("Value out of bounds. "
                             "Who has been messing with my internals?")
        elif self.current_val == BurstSequence.FINISH_VAL:
            pass
        else:
            self.current_val += 1
        return rtn
    
    def finish(self):
        self.current_val = BurstSequence.FINISH_VAL
    
    def reset(self):
        self.current_val = BurstSequence.INIT_VAL
    
    def combine(self,channel_no):
        if channel_no > BurstSequence.MAX_CHANNEL:
            raise ValueError('Channel number limited to 5 bits (value too large)')
        elif channel_no < 0:
            raise ValueError('Channel number cannot be subzero (value too small)')
        return channel_no | (self.next() << 5)
