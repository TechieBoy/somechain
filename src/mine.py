from core import Transaction, Block, BlockHeader, Chain, dhash, merkle_hash
import constants as consts
from typing import List, Set
import time
import copy

mempool: Set[str] = set()

# TODO how will this work across processes?!
mining_interrupted = False


def add_transaction(transaction: Transaction):
    if transaction.is_valid():
        mempool.add(str(transaction))


def remove_transactions_from_mempool(block: Block):
    """Removes transaction from the mempool based on a new received block
    
    Arguments:
        block {Block} -- The block which is received
    """

    global mempool
    mempool = set([x for x in mempool if x not in block.transactions])


def mine(chain: Chain) -> Block:
    # TODO pick and choose which transactions to add for max profit
    # Also avoid exceeding the max size
    c_pool = list(copy.deepcopy(mempool))
    c_pool = list(map(Transaction.from_json, c_pool))
    for n in range(2 ** 64):
        if mining_interrupted:
            # TODO update current mempool with transactions of new block
            pass
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
            # TODO add coinbase with transaction fees
            return Block(header=block_header, transactions=c_pool)
