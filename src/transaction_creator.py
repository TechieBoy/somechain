from utils import constants as consts
import json
import requests
import random
from flask import Flask, jsonify, request
from core import Transaction, Block, Chain, SingleOutput, TxIn, TxOut, BlockHeader
from core import genesis_block, genesis_block_transaction, genesis_block_header
from typing import Dict, List, Any, TYPE_CHECKING
from utils.utils import merkle_hash, dhash
from utils.logger import logger
from utils.storage import get_block_from_db
from wallet import Wallet
import copy


def fetch_peer_list():
    r = requests.get(consts.SEED_SERVER_URL)
    peer_list = json.loads(r.text)
    return peer_list


def get_peer_url(peer: Dict[str, Any]) -> str:
    return "http://" + str(peer["ip"]) + ":" + str(peer["port"])


if __name__ == "__main__":

    # The singleOutput for first coinbase transaction in genesis block
    so = SingleOutput(txid=dhash(genesis_block_transaction[0]), vout=0)

    first_transaction = Transaction(
        version=1,
        locktime=0,
        timestamp=3,
        is_coinbase=False,
        fees=4000000000,
        vin={0: TxIn(payout=so, sig="", pub_key=consts.WALLET_PUBLIC)},
        vout={0: TxOut(amount=1000000000, address=consts.WALLET_PUBLIC)},
    )

    sign_copy_of_tx = copy.deepcopy(first_transaction)
    sign_copy_of_tx.vin = {}
    w = Wallet()
    w.public_key = consts.WALLET_PUBLIC
    w.private_key = consts.WALLET_PRIVATE
    sig = w.sign(sign_copy_of_tx.to_json())
    first_transaction.vin[0].sig = sig

    peer_list = fetch_peer_list()
    print(peer_list)
    for peer in peer_list:
        try:
            print(get_peer_url(peer))
            requests.post(get_peer_url(peer) + "/newtransaction", data={"transaction": first_transaction.to_json()})
        except Exception as e:
            logger.debug("TransactionCreator: Could no send transaction")
            pass
