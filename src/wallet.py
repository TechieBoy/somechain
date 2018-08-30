from ecdsa import SigningKey, VerifyingKey, SECP256k1, BadDigestError, BadSignatureError
import utils.constants as consts
import json


class Wallet:
    def __init__(self):
        self.private_key, self.public_key = self.generate_address()
        with open(consts.WALLET_STORAGE_FILE, "a") as file:
            file.write(json.dumps((self.private_key, self.public_key)))

    def __repr__(self):
        return f"PubKey:{self.public_key}\nPrivKey:{self.private_key}"

    def generate_address(self):
        priv_key = SigningKey.generate(curve=SECP256k1)
        priv_key_string = priv_key.to_string().hex()
        pub_key = priv_key.get_verifying_key()
        pub_key_string = pub_key.to_string().hex()
        return priv_key_string, pub_key_string

    def sign(self, transaction: str) -> str:
        transaction = bytes(transaction.encode())
        sk = SigningKey.from_string(bytes.fromhex(self.private_key), curve=SECP256k1)
        signature = sk.sign(transaction)
        return signature.hex()

    @staticmethod
    def verify(transaction: str, signature: str, public_key: str) -> bool:
        transaction = bytes(transaction.encode())
        signature = bytes.fromhex(signature)
        vk = VerifyingKey.from_string(bytes.fromhex(public_key), curve=SECP256k1)
        try:
            return vk.verify(signature, transaction)
        except (BadDigestError, BadSignatureError):
            return False


if __name__ == "__main__":
    w = Wallet()
    print(w)
    message = "Send 100 btc to Teknas"
    sig = w.sign(message)
    print(type(sig))
    result = w.verify(message, sig, w.public_key)
    print(result)
    print(sig)

    print(w.public_key)
    print("hololaaa")
    print(w.private_key)

