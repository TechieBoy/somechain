import copy
import sys
import time
from multiprocessing import Process
from operator import attrgetter
from sys import getsizeof
from typing import List, Optional, Set, Tuple

import requests

import utils.constants as consts
from core import Block, BlockHeader, Chain, Transaction, TxIn, TxOut
from utils.logger import logger
from utils.utils import compress, dhash, merkle_hash


class Miner:
    def __init__(self):
        self.p: Optional[Process] = None

    def is_mining(self):
        if self.p:
            if self.p.is_alive():
                return True
            else:
                self.p = None
        return False

    def start_mining(self, mempool: Set[Transaction], chain: Chain, payout_addr: str):
        if not self.is_mining():
            self.p = Process(target=self.__mine, args=(mempool, chain, payout_addr))
            self.p.start()
            # logger.debug("Started mining")

    def stop_mining(self):
        if self.is_mining():
            # logger.debug("Miner: Called Stop Mining")
            self.p.terminate()
            self.p = None

    def calculate_transaction_fees_and_size(self, transactions: List[Transaction]) -> Tuple[int, int]:
        transactions.sort(key=attrgetter("fees"), reverse=True)
        size = 0
        fees = 0
        for t in transactions:
            size += sys.getsizeof(t.to_json())
            fees += t.fees
        return fees, size

    def __calculate_best_transactions(self, transactions: List[Transaction]) -> Tuple[List[Transaction], int]:
        """Returns the best transactions to be mined which don't exceed the max block size
        
        Arguments:
            transactions {List[Transaction]} -- The transactions to be mined
        
        Returns:
            List[Transaction] -- the transactions which give the best fees
            int -- The fees in scoins
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

    def __mine(self, mempool: Set[Transaction], chain: Chain, payout_addr: str) -> Block:
        c_pool = list(copy.deepcopy(mempool))
        mlist, fees = self.__calculate_best_transactions(c_pool)
        # logger.debug(f"Miner: Will mine {len(mlist)} transactions and get {fees} scoins in fees")
        coinbase_tx_in = {0: TxIn(payout=None, sig="Receiving some Money", pub_key="Does it matter?")}
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
        block_header = BlockHeader(
            version=consts.MINER_VERSION,
            height=chain.length,
            prev_block_hash=dhash(chain.header_list[-1]),
            merkle_root=merkle_hash(mlist),
            timestamp=int(time.time()),
            target_difficulty=chain.target_difficulty,
            nonce=0,
        )
        DONE = False
        for n in range(2 ** 64):
            block_header.nonce = n
            bhash = dhash(block_header)
            if chain.is_proper_difficulty(bhash):
                block = Block(header=block_header, transactions=mlist)
                requests.post("http://0.0.0.0:" + str(consts.MINER_SERVER_PORT) + "/newblock", data=compress(block.to_json()))
                logger.info(
                    f"Miner: Mined Block with {len(mlist)} transactions, Got {fees} in fees and {chain.current_block_reward()} as reward"
                )
                DONE = True
                break
        if not DONE:
            logger.error("Miner: Exhausted all 2 ** 64 values without finding proper hash")
