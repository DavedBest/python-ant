from ant.core.event import *
from ant.core.constants import *

import struct


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
                
             
        
