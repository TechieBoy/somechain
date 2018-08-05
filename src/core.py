"""
Core blockchain implementation goes here
TODO:
    Transactions
    Blocks
    Block Validation
    Storage

"""
from dataclasses import dataclass
from typing import Optional, Iterable, List, Union
import hashlib


@dataclass
class SingleOutput:
    """ References a single output """
    # The transaction id which contains this output
    txid: str

    # The index of this output in the transaction
    vout: int


@dataclass
class TxOut:
    """ A single Transaction Output """
    # The amount in satoshis
    amount: int

    # Public key hash of receiver in pubkey script
    address: str


@dataclass
class TxIn:
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
class Transaction:
    """ A transaction as defined by bitcoin core """

    def __str__(self):
        # TODO add some representation of vin and vout or copy from bitcoin core
        return f'Transaction{self.version}{self.locktime}'

    # Version for this transaction
    version: int

    # The earliest block(< 500000000) or
    # earliest time(Unix timestamp >500000000)
    # when this transaction may be added to the block chain.
    locktime: int

    # The input transactions
    vin: Iterable[TxIn]

    # The output transactions
    vout: Iterable[TxOut]


@dataclass
class BlockHeader:
    """ The header of a block """

    def __str__(self):
        return f'{self.version}{self.prev_block_hash}{self.merkle_root}{self.timestamp}{self.target_bits}{self.nonce}'

    # Version
    version: int

    # A reference to the hash of the previous block
    prev_block_hash: Optional[str]

    # A hash of the root of the merkle tree of this block’s transactions
    merkle_root: str

    # The approximate creation time of this block (seconds from Unix Epoch)
    timestamp: int

    # Proof-of-Work target as a coefficient/exponent format
    # target = coefficient * 2^(8 * (exponent – 3))
    target_bits: int

    # Nonce to try to get a hash below target_bits
    nonce: int


@dataclass
class Block:
    """ A single block """

    # The block header
    header: BlockHeader

    # The transactions in this block
    transactions: Iterable[Transaction]


def dhash(s: Union[str, Transaction, BlockHeader]) -> str:
    """ Double sha256 hash """
    if not isinstance(s, str):
        s = str(s)
    s = s.encode()
    return hashlib.sha256(hashlib.sha256(s).digest()).hexdigest()


def merkle_hash(transactions: Iterable[Transaction]) -> str:
    """ Computes and returns the merkle tree root for a list of transactions """
    if len(transactions) == 1:
        return dhash(transactions[0])
    if len(transactions) % 2 != 0:
        transactions = transactions + transactions[-1]
    map(dhash, transactions)

    def recursive_merkle_hash(t: List[str]) -> str:
        if len(t) == 1:
            return t[0]
        t_child = []
        for i in range(0, len(t), 2):
            new_hash = dhash(t[i] + t[i + 1])
            t_child.append(new_hash)
        return recursive_merkle_hash(t_child)

    return recursive_merkle_hash(transactions)


genesis_block_transaction = Transaction(version=1, locktime=0,
                                        vin=[TxIn(payout=None, sig='0', pub_key='', sequence=0)],
                                        vout=[TxOut(amount=5000000000,
                                                    address='1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa')])
genesis_block_header = BlockHeader(version=1, prev_block_hash=None,
                                   merkle_root=merkle_hash([genesis_block_transaction]),
                                   timestamp=1231006505, target_bits=0xFFFF001D, nonce=2083236893)
genesis_block = Block(header=genesis_block_header, transactions=[genesis_block_transaction])

print(genesis_block)
