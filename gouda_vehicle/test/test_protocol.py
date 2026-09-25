import binascii
from gouda_vehicle.protocol import Frame, Parser, COMMAND


def test_crc_and_fragments():
    assert binascii.crc_hqx(b'123456789',0xffff)==0x29b1
    f=Frame(COMMAND,0x123456789abcdef0,0xffffffff,4,1)
    p=Parser();result=[]
    for b in b'garbage'+f.encode():result.extend(p.feed(bytes([b])))
    assert result==[f]


def test_corruption_resync_and_back_to_back():
    f=Frame(COMMAND,123,27,1,1);bad=bytearray(f.encode());bad[16]^=4
    assert Parser().feed(bad+f.encode()+f.encode())==[f,f]
