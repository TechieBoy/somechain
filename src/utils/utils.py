import datetime
import hashlib
from typing import TYPE_CHECKING, List, Union

from . import constants as consts

if TYPE_CHECKING:
    import os
    import sys

    sys.path.append(os.path.split(sys.path[0])[0])
    from src.core import Transaction, BlockHeader  # noqa


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
    return int(difference.total_seconds())


def merkle_hash(transactions: List["Transaction"]) -> str:
    """ Computes and returns the merkle tree root for a list of transactions """
    if transactions is None or len(transactions) == 0:
        return "F" * consts.HASH_LENGTH_HEX
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


def dhash(s: Union[str, "Transaction", "BlockHeader"]) -> str:
    """ Double sha256 hash """
    if not isinstance(s, str):
        s = str(s)
    s = s.encode()
    return hashlib.sha256(hashlib.sha256(s).digest()).hexdigest()


def lock(lock):
    def decorator(f):

        def call(*args, **argd):
            with lock:
                return f(*args, **argd)
        return call

    return decorator
