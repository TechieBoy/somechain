import json
from fastecdsa import keys, curve, ecdsa

import utils.constants as consts
from utils.logger import logger
from utils.storage import add_wallet_to_db, get_wallet_from_db
from utils.encode_keys import encode_public_key, decode_public_key
PORT = str(consts.MINER_SERVER_PORT)

class Wallet:

    private_key: str = None
    public_key: str = None

    def __init__(self):
        keys = get_wallet_from_db(PORT)
        if keys:
            self.private_key, self.public_key = keys
            logger.info("Wallet: Restoring Existing Wallet")
            return

        self.private_key, self.public_key = self.generate_address()
        logger.info("Wallet: Creating new Wallet")
        logger.info(self)
        add_wallet_to_db(PORT, self)

    def __repr__(self):
        return f"PubKey:\t{self.public_key}\nPrivKey:\t{self.private_key}"

    def generate_address(self):
        priv_key, pub_key_point = keys.gen_keypair(curve.secp256k1)
        return priv_key, encode_public_key(pub_key_point)

    def sign(self, transaction: str) -> str:
        r, s = ecdsa.sign(transaction, self.private_key, curve=curve.secp256k1)
        return json.dumps((r, s))

    @staticmethod
    def verify(transaction: str, signature: str, public_key: str) -> bool:
        r, s = json.loads(signature)
        public_key = decode_public_key(public_key)
        return ecdsa.verify((r, s), transaction, public_key, curve=curve.secp256k1)


if __name__ == "__main__":
    w = Wallet()
    print(w)

    print(w.public_key)
    print("hololaaa")
    print(w.private_key)

    message = "Send 100 btc to Teknas"
    sig = w.sign(message)
    print(type(sig))
    result = w.verify(message, sig, w.public_key)
    print(result)
    print(sig)
