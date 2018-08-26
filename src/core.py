"""
Core blockchain implementation goes here
TODO:
    Transactions
    Blocks
    Block Validation
    Storage

"""
import sys
sys.path.append("..")

from dataclasses import dataclass
from typing import Optional, List, Union, Dict
import hashlib
from src.utils.dataclass_json import DataClassJson
from src.utils.storage import *
import src.utils.constants as consts
import datetime


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


@dataclass
class Transaction(DataClassJson):
    """ A transaction as defined by bitcoin core """

    def __str__(self):
        return self.to_json()

    # Whether this transaction is coinbase transaction
    is_coinbase: bool

    # Version for this transaction
    version: int

    # Timestamp for this transaction
    timestamp: int

    # The earliest block(< 500000000) or
    # earliest time(Unix timestamp >500000000)
    # when this transaction may be added to the block chain.
    locktime: int

    # The input transactions
    vin: Dict[int, TxIn]

    # The output transactions
    vout: Dict[int, TxOut]


@dataclass
class BlockHeader(DataClassJson):
    """ The header of a block """

    def __str__(self):
        return f"{self.version}|{self.prev_block_hash}|{self.merkle_root}|{self.timestamp}|{self.target_bits}|{self.nonce}"

    # Version
    version: int

    # Block Height
    height: Optional[int]

    # A reference to the hash of the previous block
    prev_block_hash: Optional[str]

    # A hash of the root of the merkle tree of this block’s transactions
    merkle_root: str

    # The approximate creation time of this block (seconds from Unix Epoch)
    timestamp: int

    # Proof-of-Work target as number of zero bits in the beginning of the hash
    target_bits: int

    # Nonce to try to get a hash below target_bits
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

    def is_valid(self, target_difficulty: int) -> bool:
        from sys import getsizeof

        # Block should be of valid size
        if getsizeof(self.to_json()) > consts.MAX_BLOCK_SIZE_KB * 1024 or \
                len(self.transactions) == 0:
            print("Block Size Exceeded")
            return False

        # Block hash should have proper difficulty
        hhash = str(self)
        pow = 0
        for c in hhash:
            if not c == '0':
                break
            else:
                pow += 1
        if pow < target_difficulty:
            print("POW not valid")
            return False

        # Block should not have been mined more than 2 hours in the future
        now = datetime.datetime.now()
        mined_time = datetime.datetime.fromtimestamp(self.header.timestamp)
        difference = mined_time - now
        if difference.total_seconds() > 2 * 60 * 60:
            print("Time Stamp not valid")
            return False

        # Reject if timestamp is the median time of the last 11 blocks or before
        # TODO

        # The first and only first transaction should be coinbase
        transaction_status = [transaction.is_coinbase for transaction in self.transactions]
        first_transaction = transaction_status[0]
        other_transactions = transaction_status[1:]
        if not first_transaction or any(other_transactions):
            print("Coinbase transaction not valid")
            return False

        # Make sure each transaction is valid
        # TODO

        # Verify merkle hash
        if self.header.merkle_root != merkle_hash(self.transactions):
            print("Merkle Hash failed")
            return False
        return True

@dataclass
class Utxo:
    # Mapping from string repr of SingleOutput to TxOut
    utxo: Dict[str, TxOut] = None

    def get(self, so: SingleOutput)-> [TxOut, None]:
        so_str = so.to_json()
        if so_str in self.utxo:
            return self.utxo[so_str]
        print(so_str)
        print(self.utxo)
        return None

    def set(self, so: SingleOutput, txout: TxOut):
        if not self.utxo:
            self.utxo = {}
        so_str = so.to_json()
        self.utxo[so_str] = txout

    def remove(self, so: SingleOutput)-> bool:
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
    header_list: List[BlockHeader] = None

    # The UTXO Set
    utxo: Utxo = Utxo()

    # Build the UTXO Set from scratch
    # TODO Test this lol
    def build_utxo(self):
        for header in self.header_list:
            block = Block.from_json(get_block_from_db(dhash(header)))
            self.update_utxo(block)

    # Update the UTXO Set on adding new block
    def update_utxo(self, block: Block):

        # TODO ensure that the block & all transactions are valid as per current utxo

        block_transactions: List[Transaction] = block.transactions
        for t in block_transactions:
            thash = dhash(t)
            if not t.is_coinbase:
                # Remove the spent outputs
                for tinput in t.vin:
                    so = t.vin[tinput].payout
                    # if so in self.utxo:
                    #     # TODO verify sig and pub key?!(shouldn't it be done before hand?)
                    #     # add to utxo if valid
                    #     del self.utxo[so]
                    self.utxo.remove(so)
            # Add new unspent outputs
            for touput in t.vout:
                self.utxo.set(SingleOutput(txid=thash, vout=touput), t.vout[touput])

    def add_block(self, block: Block):
        if not block.is_valid(get_target_difficulty(self)):
            print("Block is not valid")
            return False

        if not self.header_list:
            self.header_list = []

        if len(self.header_list) == 0 or \
                dhash(self.header_list[-1]) == block.header.prev_block_hash:
            self.header_list.append(block.header)
            add_block_to_db(block)
            self.update_utxo(block)
            return True
        print("No idea what happened")
        return False


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


def get_target_difficulty(chain: Chain) -> int:
    # TODO
    return 0


genesis_block_transaction = [Transaction(version=1,
                                         locktime=0,
                                         timestamp=1,
                                         is_coinbase=True,
                                         vin={
                                             0: TxIn(payout=None, sig='0', pub_key='', sequence=0)
                                         },
                                         vout={
                                             0: TxOut(amount=5000000000, address='1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa')
                                         }),
                             ]

genesis_block_header = BlockHeader(version=1, prev_block_hash=None, height=1,
                                   merkle_root=merkle_hash(genesis_block_transaction),
                                   timestamp=1231006505, target_bits=0xFFFF001D, nonce=2083236893)
genesis_block = Block(header=genesis_block_header, transactions=genesis_block_transaction)

if __name__== "__main__":
    print(genesis_block)