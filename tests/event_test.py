from ant.core.event import *
from ant.core.constants import *

import unittest
import struct
from anttestutils import *

class ProcessBufferTest(unittest.TestCase):

                
         
    def setUp(self):
        self.buffer1_data = [2,3,0,0,0,0,0,0,0,4,5]
        self.buffer2_data = [7,8,0,0,0,0,0,0,0,9,10]
        self.buffer3_data = [12,13,0,0,0,0,0,0,0,14,15]      
        
        self.combind_buffer1 = struct.pack(*get_pack_args(self.buffer1_data))
        self.combind_buffer2 = struct.pack(*get_pack_args(self.buffer2_data))
        self.combind_buffer3 = struct.pack(*get_pack_args(self.buffer3_data, sync = MESSAGE_TX_SYNC_LSB ))
    # tests whether sync byte of next message is sucessfully found
    def test_combind_buffer(self):
        buffer_ = self.combind_buffer1 + self.combind_buffer2 + self.combind_buffer3
        sync, length, type_ = struct.unpack('BBB', buffer_[:3])
        self.assertEqual(sync, MESSAGE_TX_SYNC )
        buffer_, messages = ProcessBuffer(buffer_)
        for i,msg in enumerate(messages):
            self.assertEqual(msg.getType(),MESSAGE_CHANNEL_BROADCAST_DATA)
           #if (i ==0 ):
                #self.assertEqual(msg.getPayload(),self.buffer1_data)    





if __name__ == '__main__':
    unittest.main()     
        
