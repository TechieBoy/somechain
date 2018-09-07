import os
from typing import TYPE_CHECKING

from sqlitedict import SqliteDict

from .constants import BLOCK_DB_LOC, WALLET_DB_LOC
from .utils import dhash
from .encode_keys import encode_public_key

from fastecdsa.keys import export_key, import_key
from fastecdsa.curve import secp256k1

if TYPE_CHECKING:
    import sys

    sys.path.append(os.path.split(sys.path[0])[0])

    from src.core import Block  # noqa
    from src.wallet import Wallet  # noqa

WALLET_DB = None

try:
    os.remove(BLOCK_DB_LOC)
except OSError:
    pass


# WALLET FUNCTIONS
def get_wallet_from_db(port: str) -> str:
    try:
        location = WALLET_DB_LOC + str(port) + ".key"
        priv_key, pub_key_point = import_key(location)
        return priv_key, encode_public_key(pub_key_point)
    except Exception as e:
        return None


def add_wallet_to_db(port: str, wallet: "Wallet"):
    location = WALLET_DB_LOC + str(port)
    export_key(wallet.private_key, curve=secp256k1, filepath=location + ".key")
    with open(location + ".pub", "w") as file:
        file.write(wallet.public_key)


# BLOCK FUNCTIONS
def get_block_from_db(header_hash: str) -> str:
    with SqliteDict(BLOCK_DB_LOC, autocommit=False) as db:
        return db.get(header_hash, None)


def add_block_to_db(block: "Block"):
    with SqliteDict(BLOCK_DB_LOC, autocommit=False) as db:
        db[dhash(block.header)] = block.to_json()
        db.commit(blocking=False)


def check_block_in_db(header_hash: str) -> bool:
    with SqliteDict(BLOCK_DB_LOC, autocommit=False) as db:
        if db.get(header_hash, None):
            return True
    return False


def remove_block_from_db(header_hash: str):
    with SqliteDict(BLOCK_DB_LOC, autocommit=False) as db:
        del db[header_hash]
        db.commit()
