from core import Transaction, Block, BlockHeader, Chain, TxIn, TxOut
from sys import getsizeof
from utils.utils import dhash, merkle_hash
import utils.constants as consts
from utils.logger import logger
from typing import Set, List, Tuple, Optional
from operator import attrgetter
import requests
import time
import copy
import sys
from multiprocessing import Process


class Miner:
    def __init__(self):
        self.p: Optional[Process] = None

    def is_mining(self):
        if self.p:
            return True
        return False

    def start_mining(self, mempool: Set[Transaction], chain: Chain, payout_addr: str):
        if not self.is_mining():
            self.p = Process(target=self.__mine, args=(mempool, chain, payout_addr))
            self.p.start()
            logger.debug("Started mining")

    def stop_mining(self):
        if self.is_mining():
            self.p.terminate()
            self.p = None
            logger.debug("Stopped mining")

    def __calculate_best_transactions(self, transactions: List[Transaction]) -> Tuple[List[Transaction], int]:
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

    def __mine(self, mempool: Set[Transaction], chain: Chain, payout_addr: str) -> Block:
        c_pool = list(copy.deepcopy(mempool))
        mlist, fees = self.__calculate_best_transactions(c_pool)
        logger.debug(f"Will mine {len(mlist)} transactions and get {fees} satoshis in fees")
        for n in range(2 ** 64):
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
                coinbase_tx_in = {0: TxIn(payout=None, sig="Paisa mila mujhe", pub_key="Ole Ole Ole")}
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
                block = Block(header=block_header, transactions=mlist)
                requests.post("http://0.0.0.0" + "/newblock", data={"block": block})
                logger.debug(f"Mined block with hash {bhash}! I'm rich!!")
                sys.exit()
        logger.critical("Exhausted all 2 ** 64 values without finding proper hash")
        sys.exit()
