from core import Transaction, Block, BlockHeader, Chain, TxIn, TxOut
from sys import getsizeof
from utils.utils import dhash, merkle_hash
import constants as consts
from typing import Set, List, Tuple
from operator import attrgetter
import time
import copy


mempool: Set[Transaction] = set()

# TODO how will this work across processes?!
mining_interrupted = False


def add_transaction(transaction: Transaction):
    if transaction.is_valid():
        mempool.add(transaction)


def remove_transactions_from_mempool(block: Block):
    """Removes transaction from the mempool based on a new received block
    
    Arguments:
        block {Block} -- The block which is received
    """

    global mempool
    mempool = set([x for x in mempool if x not in block.transactions])


def calculate_best_transactions(transactions: List[Transaction]) -> Tuple[List[Transaction], int]:
    """Returns the best transactions to be mined which don't exceed the max block size
    
    Arguments:
        transactions {List[Transaction]} -- The transactions to be mined
    
    Returns:
        List[Transaction] -- the transactions which give the best fees
        int -- The fees in satoshis
    """
    transactions.sort(key=attrgetter("fees"), reverse=True)
    size = 0
    fees = 0
    mlist = []
    for t in transactions:
        if size < consts.MAX_BLOCK_SIZE_KB:
            mlist.append(t)
            size += getsizeof(t.to_json())
            fees += t.fees
        else:
            break
    return mlist, fees


def mine(mempool: Set[Transaction], chain: Chain, payout_addr: str) -> Block:
    c_pool = list(copy.deepcopy(mempool))
    mlist, fees = calculate_best_transactions(c_pool)
    for n in range(2 ** 64):
        if mining_interrupted:
            # TODO send death notification to fullnode and die
            pass
        block_header = BlockHeader(
            version=consts.MINER_VERSION,
            height=chain.length + 1,
            prev_block_hash=dhash(chain.header_list[-1]),
            merkle_root=merkle_hash(mlist),
            timestamp=int(time.time()),
            target_difficulty=chain.get_target_difficulty(),
            nonce=n,
        )
        bhash = dhash(block_header)
        if chain.is_proper_difficulty(bhash):
            coinbase_tx_in = {0: TxIn(payout=None, sig="Paisa mila mujhe", pub_key="Olla Olla")}
            coinbase_tx_out = {
                0: TxOut(amount=chain.current_block_reward(), address=payout_addr),
                1: TxOut(amount=fees, address=payout_addr),
            }
            coinbase_tx = Transaction(
                is_coinbase=True,
                version=consts.MINER_VERSION,
                fees=0,
                timestamp=int(time.time()),
                locktime=-1,
                vin=coinbase_tx_in,
                vout=coinbase_tx_out,
            )
            mlist.insert(0, coinbase_tx)
            return Block(header=block_header, transactions=mlist)
