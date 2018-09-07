from fastecdsa.asn1 import decode_key, encode_public_key as encode_pub_key_point
from binascii import a2b_base64


def decode_public_key(base64_key: str):
    raw_data = a2b_base64(base64_key)
    return decode_key(raw_data)[1]


def encode_public_key(pub_key_point):
    encoded_key = encode_pub_key_point(pub_key_point)
    base64_key = "".join(encoded_key.split("\n")[1:-1])
    return base64_key
