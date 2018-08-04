"""
Core blockchain implementation goes here
TODO:
    Transactions
    Blocks
    Block Validation
    Storage

"""
from dataclasses import dataclass
from typing import Optional, Iterable


@dataclass
class SingleOutput:
    """ References a single output """
    # The transaction id which contains this output
    txid: str

    # The index of this output in the transaction
    vout: int


@dataclass
class TxOut:
    # The amount in satoshis
    amount: int

    # Public key hash of receiver in pubkey script
    address: str


@dataclass
class TxIn:
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
class Block:
    """ A single block """
    # Version
    version: int

    # A reference to the hash of the previous block
    prev_block_hash: str

    # A hash of the root of the merkle tree of this block’s transactions
    merkle_root: str

    # The approximate creation time of this block (seconds from Unix Epoch)
    timestamp: int

    # Proof-of-Work target as a coefficient/exponent format
    # target = coefficient * 2^(8 * (exponent – 3))
    target_bits: int

    # Nonce to try to get a hash below target_bits
    nonce: int

    # The transactions in this block
    transactions: Iterable[Transaction]


