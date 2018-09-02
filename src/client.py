"""
TODO:
    Functions for interacting with api's
    Send and receive coins
"""

import hashlib
import secrets
from typing import Tuple

from utils.secp256k1 import b58_encode, point_mul


class Wallet:
    def __init__(self):
        self.private_key = self.create_private_key()

    @staticmethod
    def create_private_key() -> bytes:
        return secrets.token_bytes(32)

    # See chp. 4 of Mastering Bitcoin
    def generate_address(self) -> Tuple[str, str]:
        q = point_mul(int.from_bytes(self.private_key, byteorder="big"))
        public_key = b"\x04" + q[0].to_bytes(32, byteorder="big") + q[1].to_bytes(32, byteorder="big")
        hsh = hashlib.sha256(public_key).digest()

        ripemd160hash = hashlib.new("ripemd160")
        ripemd160hash.update(hsh)
        ripemd160 = ripemd160hash.digest()

        address = b"\x00" + ripemd160
        checksum = hashlib.sha256(hashlib.sha256(address).digest()).digest()[:4]
        address += checksum

        wif = b"\x80" + self.private_key
        checksum = hashlib.sha256(hashlib.sha256(wif).digest()).digest()[:4]
        wif += checksum

        address = b58_encode(address)
        wif = b58_encode(wif)
        return address, wif


if __name__ == "__main__":
    w = Wallet()
    print(w.generate_address())
