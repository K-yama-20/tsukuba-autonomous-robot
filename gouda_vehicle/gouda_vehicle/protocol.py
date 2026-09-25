"""Protocol v2; deliberately incompatible with the unimplemented 6-byte proposal."""
import binascii
import struct
from dataclasses import dataclass

COMMAND, ARM, DISARM, STATUS = 1, 2, 3, 128
SIZE = 22


@dataclass
class Frame:
    kind: int
    token: int
    seq: int
    motion: int = 0
    flags: int = 0
    fault: int = 0

    def encode(self):
        data = struct.pack('<2sBBQIBBBB', b'\xa5\x5a', 2, self.kind, self.token,
                           self.seq, self.motion, self.flags, self.fault, 0)
        return data + struct.pack('<H', binascii.crc_hqx(data, 0xffff))


class Parser:
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data):
        self.buffer.extend(data)
        result = []
        while len(self.buffer) >= SIZE:
            b = self.buffer[:SIZE]
            if b[:3] != b'\xa5\x5a\x02' or b[19] or binascii.crc_hqx(b[:20], 0xffff) != int.from_bytes(b[20:], 'little'):
                del self.buffer[0]
                continue
            _, _, kind, token, seq, motion, flags, fault, _ = struct.unpack('<2sBBQIBBBB', b[:20])
            result.append(Frame(kind, token, seq, motion, flags, fault))
            del self.buffer[:SIZE]
        return result
