import pickledb
from ..core import Block, dhash
import constants as consts

BLOCK_DB = None


def load_block_db():
    global BLOCK_DB
    if not BLOCK_DB:
        BLOCK_DB = pickledb.load(consts.BLOCK_DB_LOC, False)
    return BLOCK_DB


def get_block_from_db(header_hash: str) -> str:
    db = load_block_db()
    return db.get(header_hash)


def add_block_to_db(block: Block) -> bool:
    db = load_block_db()
    return db.set(dhash(block.header), block.to_json())
