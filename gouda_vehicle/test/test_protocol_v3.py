from gouda_vehicle.protocol_v3 import (
    ARM, COMMAND, DISARM, FRAME_SIZE, Parser, encode_arm, encode_command, encode_disarm,
)


GOLDEN_COMMAND = bytes.fromhex('a55a0301efcdab8967452301030000007856341289fe710200000000000000000000000000000000000000000000000000000000000000000000000000008360')


def test_command_matches_firmware_golden_vector_and_round_trips():
    frame = encode_command(0x0123456789ABCDEF, 3, 0x12345678, .625, .375)
    assert frame == GOLDEN_COMMAND
    assert len(frame) == FRAME_SIZE
    parser = Parser()
    assert parser.feed(frame[:13]) == []
    parsed = parser.feed(frame[13:])
    assert len(parsed) == 1
    assert parsed[0].kind == COMMAND
    assert parsed[0].boot_token == 0x0123456789ABCDEF
    assert parsed[0].sender_seq == 3
    assert parsed[0].sender_monotonic_ms == 0x12345678


def test_arm_disarm_are_neutral_and_invalid_crc_is_ignored():
    arm = encode_arm(1, 2, 3)
    disarm = encode_disarm(1, 3, 4)
    assert arm[3] == ARM and disarm[3] == DISARM
    parser = Parser()
    assert parser.feed(arm)[0].kind == ARM
    corrupted = bytearray(disarm); corrupted[21] ^= 0x01
    assert parser.feed(corrupted) == []


def test_parser_keeps_split_magic_prefix_after_noise():
    parser = Parser()
    assert parser.feed(b'noise' * 20 + b'\xa5') == []
    packet = encode_arm(1, 2, 3)
    assert parser.feed(packet[1:])[0].kind == ARM


def test_encoder_rejects_out_of_range_norm():
    import pytest
    with pytest.raises(ValueError):
        encode_command(1, 1, 1, 1.01, 0)
