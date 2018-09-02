import json
import random
from typing import Any, Dict, List

import requests
from flask import Flask, jsonify, request

from core import (Block, BlockHeader, Chain, SingleOutput, Transaction, TxIn,
                  TxOut, genesis_block, genesis_block_header,
                  genesis_block_transaction)
from utils import constants as consts
from utils.logger import logger
from utils.storage import get_block_from_db
from utils.utils import dhash, merkle_hash

app = Flask(__name__)

PEER_LIST = []

BLOCK_DB = None

ACTIVE_CHAIN = Chain()


def fetch_peer_list():
    r = requests.post(consts.SEED_SERVER_URL, data={"port": consts.MINER_SERVER_PORT})
    peer_list = json.loads(r.text)
    return peer_list


def get_peer_url(peer: Dict[str, Any]) -> str:
    return "http://" + str(peer["ip"]) + ":" + str(peer["port"])


def greet_peer(peer: Dict[str, Any]) -> List:
    url = get_peer_url(peer)
    r = requests.get(url)
    return json.loads(r.text)


def receive_block_from_peer(peer: Dict[str, Any], header_hash) -> Block:
    r = requests.post(get_peer_url(peer), data={"header_hash": header_hash})
    return Block.from_json(r.text)


def sync(peer_list):
    max_peer = max(peer_list, key=lambda k: k["blockheight"])
    r = requests.post(get_peer_url(max_peer) + "/getblockhashes/", data={"myheight": len(ACTIVE_CHAIN)})
    hash_list = json.loads(r.text)
    for hhash in hash_list:
        peer_url = get_peer_url(random.choice(peer_list)) + "/getblock/"
        r = requests.post(peer_url, data={"headerhash": hhash})
        block = Block.from_json(r.text)
        if not ACTIVE_CHAIN.add_block(block):
            raise Exception("WTF")


@app.route("/")
def hello():
    data = {"version": consts.MINER_VERSION, "blockheight": ACTIVE_CHAIN.length}
    return jsonify(data)


@app.route("/getblock", methods=["POST"])
def getblock():
    hhash = request.form.get("headerhash")
    if hhash:
        return get_block_from_db(hhash)
    return "Hash hi nahi bheja LOL"


@app.route("/getblockhashes", methods=["POST"])
def send_block_hashes():
    peer_height = int(request.form.get("myheight"))
    hash_list = []
    for i in range(peer_height, ACTIVE_CHAIN.length):
        hash_list.append(dhash(ACTIVE_CHAIN.header_list[i]))
    logger.debug(peer_height)
    return jsonify(hash_list)


# The singleOutput for first coinbase transaction in genesis block
so = SingleOutput(txid=dhash(genesis_block_transaction[0]), vout=0)

first_block_transactions = [
    Transaction(
        version=1,
        locktime=0,
        timestamp=2,
        is_coinbase=True,
        fees=0,
        vin={0: TxIn(payout=None, sig="", pub_key=consts.WALLET_PUBLIC)},
        vout={
            0: TxOut(amount=5000000000, address=consts.WALLET_PUBLIC),
            1: TxOut(amount=4000000000, address=consts.WALLET_PUBLIC),
        },
    ),
    Transaction(
        version=1,
        locktime=0,
        timestamp=3,
        is_coinbase=False,
        fees=4000000000,
        vin={0: TxIn(payout=so, sig="", pub_key=consts.WALLET_PUBLIC)},
        vout={0: TxOut(amount=1000000000, address=consts.WALLET_PUBLIC)},
    ),
]


for tx in first_block_transactions:
    tx.sign()

first_block_header = BlockHeader(
    version=1,
    prev_block_hash=dhash(genesis_block_header),
    height=1,
    merkle_root=merkle_hash(first_block_transactions),
    timestamp=1231006505,
    target_difficulty=0,
    nonce=2083236893,
)
first_block = Block(header=first_block_header, transactions=first_block_transactions)

if __name__ == "__main__":

    result = ACTIVE_CHAIN.add_block(genesis_block)
    logger.debug(result)

    logger.debug(ACTIVE_CHAIN.utxo)

    result = ACTIVE_CHAIN.add_block(first_block)
    logger.debug(result)
    logger.debug(ACTIVE_CHAIN.utxo)

    # # ORDER
    # Get list of peers ✓
    # Contact peers and get current state of blockchain ✓
    # Sync upto the current blockchain ✓
    # Start the flask server and listen for future blocks and transactions.
    # Start a thread to handle the new block/transaction

    fetch_peer_list()

    app.run(host="0.0.0.0", port=consts.MINER_SERVER_PORT, threaded=True, debug=True)
