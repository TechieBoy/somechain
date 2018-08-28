"""
Core blockchain implementation goes here
TODO:
    Transactions
    Blocks
    Block Validation
    Storage

"""

from sys import getsizeof, path
from dataclasses import dataclass, field
from typing import Optional, List, Union, Dict, Any
import hashlib
import datetime

path.append("..")
from utils.dataclass_json import DataClassJson
from utils.storage import *
import utils.constants as consts
from utils.logger import logger


@dataclass
class SingleOutput(DataClassJson):
    """ References a single output """

    # The transaction id which contains this output
    txid: str

    # The index of this output in the transaction
    vout: int


@dataclass
class TxOut(DataClassJson):
    """ A single Transaction Output """

    # The amount in satoshis
    amount: int

    # Public key hash of receiver in pubkey script
    address: str


@dataclass
class TxIn(DataClassJson):
    """ A single Transaction Input """

    # The UTXO we will be spending
    # Can be None for coinbase tx
    payout: Optional[SingleOutput]

    # Signature and public key in the scriptSig
    sig: str
    pub_key: str

    # Sequence number
    sequence: int

    # Check if the TxIn is Valid
    def is_valid(self, is_coinbase: bool) -> bool:
        if is_coinbase:
            # Coinbase payout must be None.
            if self.payout is not None:
                logger.debug("TxIn: Payout is not None for Coinbase Tx")
                return False
        else:
            try:
                # Ensure the Transaction Id is valid hex string
                if not len(self.payout.txid or "") == consts.TRANSACTION_ID_LENGTH_HEX:
                    logger.debug("TxIn: TxID of invalid length")
                    return False
                # Ensure the payment index is valid
                if not self.payout.vout >= 0:
                    logger.debug("TxIn: Payment index(vout) invalid")
                    return False
                # Ensure the sig and pubkey are valid
                if len(self.sig or "") == 0 or len(self.pub_key or "") == 0:
                    logger.debug("TxIN: Sig/Pubkey of invalid length")
                    logger.debug(self.sig)
                    return False
            except Exception as e:
                logger.error(e)
                return False
        return True


@dataclass
class Transaction(DataClassJson):
    """ A transaction as defined by bitcoin core """

    def __str__(self):
        return self.to_json()

    def is_valid(self):

        # No empty inputs or outputs -1
        if len(self.vin) == 0 or len(self.vout) == 0:
            logger.debug("Transaction: Empty vin/vout")
            return False

        # Transaction size should not exceed max block size -2
        if getsizeof(str(self)) > consts.MAX_BLOCK_SIZE_KB * 1024:
            logger.debug("Transaction: Size Exceeded")
            return False

        # All outputs in legal money range -3
        for index, out in self.vout.items():
            if out.amount > consts.MAX_SATOSHIS_POSSIBLE or out.amount < 0:
                logger.debug("Transaction: Invalid Amount")
                return False

        # Verify all Inputs are valid - 4
        for index, inp in self.vin.items():
            if not inp.is_valid(self.is_coinbase):
                logger.debug("Transaction: Invalid TxIn")
                return False

        # Verify locktime -5
        difference = get_time_difference_from_now_secs(self.locktime)
        if difference > 0:
            logger.debug("Transaction: Locktime Verify Failed")
            return False
        return True

    # Whether this transaction is coinbase transaction
    is_coinbase: bool

    # Version for this transaction
    version: int

    # Timestamp for this transaction
    timestamp: int

    # Earliest time(Unix timestamp >500000000)
    # when this transaction may be added to the block chain.
    locktime: int

    # The input transactions
    vin: Dict[int, TxIn]

    # The output transactions
    vout: Dict[int, TxOut]


@dataclass
class BlockHeader(DataClassJson):
    """ The header of a block """

    # Version
    version: int

    # Block Height
    height: Optional[int] = field(repr=False)

    # A reference to the hash of the previous block
    prev_block_hash: Optional[str]

    # A hash of the root of the merkle tree of this block’s transactions
    merkle_root: str

    # The approximate creation time of this block (seconds from Unix Epoch)
    timestamp: int

    # Proof-of-Work target as number of zero bits in the beginning of the hash
    target_difficulty: int = field(repr=False)

    # Nonce to try to get a hash below target_difficulty
    nonce: int


@dataclass
class Block(DataClassJson):
    """ A single block """

    # The block header
    header: BlockHeader

    # The transactions in this block
    transactions: List[Transaction]

    def __repr__(self):
        return dhash(self.header)

    def is_valid(self) -> bool:
        # Block should be of valid size and List of Transactions should not be empty -1
        if getsizeof(self.to_json()) > consts.MAX_BLOCK_SIZE_KB * 1024 or len(self.transactions) == 0:
            logger.debug("Block: Size Exceeded/No. of Tx==0")
            return False

        # The first and only first transaction should be coinbase -2
        transaction_status = [transaction.is_coinbase for transaction in self.transactions]
        first_transaction = transaction_status[0]
        other_transactions = transaction_status[1:]
        if not first_transaction or any(other_transactions):
            logger.debug("Block: First Tx is not Coinbase")
            return False

        # Make sure each transaction is valid -3
        for tx in self.transactions:
            if not tx.is_valid():
                logger.debug("Block: Transaction is not Valid")
                return False

        # Verify merkle hash -4
        if self.header.merkle_root != merkle_hash(self.transactions):
            logger.debug("Block: Merkle Hash failed")
            return False
        return True


@dataclass
class Utxo:
    # Mapping from string repr of SingleOutput to List[TxOut, Blockheader]
    utxo: Dict[str, List[Any]] = field(default_factory=dict)

    def get(self, so: SingleOutput) -> Optional[List[Any]]:
        so_str = so.to_json()
        if so_str in self.utxo:
            return self.utxo[so_str]
        return None

    def set(self, so: SingleOutput, txout: TxOut, blockheader: BlockHeader):
        so_str = so.to_json()
        self.utxo[so_str] = [txout, blockheader]

    def remove(self, so: SingleOutput) -> bool:
        so_str = so.to_json()
        if so_str in self.utxo:
            del self.utxo[so_str]
            return True
        return False


@dataclass
class Chain:
    # The max length of the blockchain
    length: int = 0

    # The list of blocks
    header_list: List[BlockHeader] = field(default_factory=list)

    # The UTXO Set
    utxo: Utxo = Utxo()

    # The Target difficulty
    target_difficulty: int = 0

    # Build the UTXO Set from scratch
    # TODO Test this lol
    def build_utxo(self):
        for header in self.header_list:
            block = Block.from_json(get_block_from_db(dhash(header)))
            self.update_utxo(block)

    # Update the UTXO Set on adding new block, *Assuming* the block being added is valid
    def update_utxo(self, block: Block):
        block_transactions: List[Transaction] = block.transactions
        for t in block_transactions:
            thash = dhash(t)
            if not t.is_coinbase:
                # Remove the spent outputs
                for tinput in t.vin:
                    so = t.vin[tinput].payout
                    self.utxo.remove(so)
            # Add new unspent outputs
            for touput in t.vout:
                self.utxo.set(SingleOutput(txid=thash, vout=touput), t.vout[touput], block.header)

    def is_transaction_valid(self, transaction: Transaction):
        # TODO check for coinbase TxIn Maturity
        # TODO ensure the TxIn is present in utxo, i.e exists and has not been spent
        # TODO ensure sum of amounts of all inputs is in valid amount range
        # TODO ensure sum of amounts of all inputs is > sum of amounts of all outputs
        # TODO Verify that the Signature is valid for all inputs
        pass

    def is_block_valid(self, block: Block):
        # Check if the block is valid -1
        if not block.is_valid():
            logger.debug("Block is not valid")
            return False

        # Block hash should have proper difficulty -2
        if not block.header.target_difficulty == self.target_difficulty:
            logger.debug("Chain: BlockHeader has invalid difficulty")
            return False
        if not self.is_proper_difficulty(dhash(block.header)):
            logger.debug("Chain: Block has invalid POW")
            return False

        # Block should not have been mined more than 2 hours in the future -3
        difference = get_time_difference_from_now_secs(block.header.timestamp)
        if difference > consts.BLOCK_MAX_TIME_FUTURE_SECS:
            logger.debug("Block: Time Stamp not valid")
            return False

        # TODO Reject if timestamp is the median time of the last 11 blocks or before

        # Ensure the prev block header matches the previous block hash in the Chain -4
        if len(self.header_list) > 0 and not dhash(self.header_list[-1]) == block.header.prev_block_hash:
            logger.debug("Chain: Block prev header does not match previous block")
            return False

        return True

    def add_block(self, block: Block):
        if self.is_block_valid(block):
            self.header_list.append(block.header)
            add_block_to_db(block)
            self.update_utxo(block)
            self.update_target_difficulty()
            logger.info("Chain: Added Block " + str(block))
            return True
        return False

    def update_target_difficulty(self):
        dui = consts.BLOCK_DIFFICULTY_UPDATE_INTERVAL
        length = len(self.header_list)
        if length > 0 and length % dui == 0:
            time_elapsed = self.header_list[-1].timestamp - self.header_list[-dui].timestamp
            num_of_blocks = dui if length > dui else length
            if time_elapsed / num_of_blocks > consts.AVERAGE_BLOCK_MINE_INTERVAL:
                if self.target_difficulty < consts.MAXIMUM_TARGET_DIFFICULTY:
                    logger.info("Updating Block Difficulty")
                    self.target_difficulty += 1

    def is_proper_difficulty(self, bhash: str) -> bool:
        pow = 0
        for c in bhash:
            if not c == "0":
                break
            else:
                pow += 1
        if pow < self.target_difficulty:
            logger.debug("Chain: POW not valid")
            return False
        return True


def get_time_difference_from_now_secs(timestamp: int) -> int:
    """Get time diference from current time in seconds

    Arguments:
        timestamp {int} -- Time from which difference is calculated

    Returns:
        int -- Time difference in seconds
    """
    now = datetime.datetime.now()
    mtime = datetime.datetime.fromtimestamp(timestamp)
    difference = mtime - now
    return difference.total_seconds()


def merkle_hash(transactions: List[Transaction]) -> str:
    """ Computes and returns the merkle tree root for a list of transactions """
    if len(transactions) == 1:
        return dhash(transactions[0])
    if len(transactions) % 2 != 0:
        transactions = transactions + [transactions[-1]]
    transactions_hash = list(map(dhash, transactions))

    def recursive_merkle_hash(t: List[str]) -> str:
        if len(t) == 1:
            return t[0]
        t_child = []
        for i in range(0, len(t), 2):
            new_hash = dhash(t[i] + t[i + 1])
            t_child.append(new_hash)
        return recursive_merkle_hash(t_child)

    return recursive_merkle_hash(transactions_hash)


def dhash(s: Union[str, Transaction, BlockHeader]) -> str:
    """ Double sha256 hash """
    if not isinstance(s, str):
        s = str(s)
    s = s.encode()
    return hashlib.sha256(hashlib.sha256(s).digest()).hexdigest()


genesis_block_transaction = [
    Transaction(
        version=1,
        locktime=0,
        timestamp=1,
        is_coinbase=True,
        vin={0: TxIn(payout=None, sig="0", pub_key="", sequence=0)},
        vout={0: TxOut(amount=5000000000, address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")},
    )
]

genesis_block_header = BlockHeader(
    version=1,
    prev_block_hash=None,
    height=1,
    merkle_root=merkle_hash(genesis_block_transaction),
    timestamp=1231006505,
    target_difficulty=0,
    nonce=2083236893,
)
genesis_block = Block(header=genesis_block_header, transactions=genesis_block_transaction)

if __name__ == "__main__":
    logger.debug(genesis_block)
