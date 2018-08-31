import pickledb
from typing import TYPE_CHECKING
from src.utils.utils import dhash
from src.utils.constants import BLOCK_DB_LOC, WALLET_DB_LOC

if TYPE_CHECKING:
    from src.core import Block  # noqa
    from src.wallet import Wallet  # noqa

BLOCK_DB = None
WALLET_DB = None


def load_wallet_db():
    global WALLET_DB
    if not WALLET_DB:
        WALLET_DB = pickledb.load(WALLET_DB_LOC, True)
    return WALLET_DB


def get_wallet_from_db(port: str) -> str:
    db = load_wallet_db()
    return db.get(port)


def add_wallet_to_db(port: str, wallet: str) -> bool:
    db = load_wallet_db()
    return db.set(port, wallet)


def load_block_db():
    global BLOCK_DB
    if not BLOCK_DB:
        BLOCK_DB = pickledb.load(BLOCK_DB_LOC, True)
    return BLOCK_DB


def get_block_from_db(header_hash: str) -> str:
    db = load_block_db()
    return db.get(header_hash)


def add_block_to_db(block: "Block") -> bool:
    db = load_block_db()
    return db.set(dhash(block.header), block.to_json())
