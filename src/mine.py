from core import Transaction, Block, BlockHeader, Chain, dhash, merkle_hash
import constants as consts
from typing import List
import time
import copy

mempool: List[Transaction] = []


def add_transaction(transaction: Transaction):
    if transaction.is_valid():
        mempool.append(transaction)


def mine(chain: Chain) -> Block:
    # TODO pick and choose which transactions to add
    c_pool = copy.deepcopy(mempool)
    for n in range(2 ** 64):
        block_header = BlockHeader(
            version=consts.MINER_VERSION,
            height=chain.length + 1,
            prev_block_hash=dhash(chain.header_list[-1]),
            merkle_root=merkle_hash(c_pool),
            timestamp=int(time.time()),
            target_bits=chain.get_target_difficulty(),
            nonce=n,
        )
        bhash = dhash(block_header)
        if chain.is_proper_difficulty(bhash):
            return Block(header=block_header, transactions=c_pool)
            
