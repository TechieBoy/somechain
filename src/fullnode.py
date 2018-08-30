import sys
import requests
import random
from flask import Flask, jsonify, request
import time
import json
from typing import Dict, Any, List, Set
from threading import Thread

sys.path.append("..")
from core import Block, Chain, genesis_block, Transaction
from miner import Miner
from utils.storage import get_block_from_db
import utils.constants as consts
from utils.utils import dhash, get_time_difference_from_now_secs
from utils.logger import logger


app = Flask(__name__)

# TODO: Guarantee that ACTIVE_CHAIN is max length chain
ACTIVE_CHAIN = Chain()

BLOCKCHAIN: List[Chain] = [ACTIVE_CHAIN]

PEER_LIST: List[Dict[str, Any]] = []

MEMPOOL: Set[Transaction] = set()

PAYOUT_ADDR = "Put my wallet address here"

miner = Miner()


def mining_thread_task():
    global miner, MEMPOOL, ACTIVE_CHAIN, PAYOUT_ADDR
    if not miner.is_mining():
        mlist = list(MEMPOOL)
        fees, size = miner.calculate_transaction_fees_and_size(mlist)
        time_diff = -get_time_difference_from_now_secs(ACTIVE_CHAIN.header_list[-1].timestamp)
        if fees >= 1000 or (size >= consts.MAX_BLOCK_SIZE_KB / 1.6) or (time_diff > consts.AVERAGE_BLOCK_MINE_INTERVAL / 2):
            miner.start_mining(MEMPOOL, ACTIVE_CHAIN, PAYOUT_ADDR)
    time.sleep(consts.AVERAGE_BLOCK_MINE_INTERVAL / 5)


def start_mining_thread():
    t = Thread(target=mining_thread_task, name="Miner", daemon=True)
    t.start()


def remove_transactions_from_mempool(block: Block):
    """Removes transaction from the mempool based on a new received block

    Arguments:
        block {Block} -- The block which is received
    """

    global MEMPOOL
    MEMPOOL = set([x for x in MEMPOOL if x not in block.transactions])


def fetch_peer_list() -> List[Dict[str, Any]]:
    try:
        r = requests.post(consts.SEED_SERVER_URL, data={"port": consts.MINER_SERVER_PORT})
        peer_list = json.loads(r.text)
        return peer_list
    except Exception as e:
        return []


def get_peer_url(peer: Dict[str, Any]) -> str:
    return "http://" + str(peer["ip"]) + ":" + str(peer["port"])


def greet_peer(peer: Dict[str, Any]) -> bool:
    try:
        url = get_peer_url(peer)
        # Send a GET request to the peer
        r = requests.get(url + "/")
        data = json.loads(r.text)
        # Update the peer data in the peer list with the new data received from the peer.
        if data.get("blockheight", None):
            peer.update(data)
        else:
            logger.debug("Main: Peer data does not have Block Height")
            return False
        return True
    except Exception as e:
        logger.debug("Main: Could not greet peer" + str(e))
    return False


def receive_block_from_peer(peer: Dict[str, Any], header_hash) -> Block:
    r = requests.post(get_peer_url(peer) + "/getblock", data={"headerhash": header_hash})
    logger.debug(r.text)
    return Block.from_json(r.text).object()


def sync(peer_list):
    max_peer = max(peer_list, key=lambda k: k["blockheight"])
    logger.debug(get_peer_url(max_peer))
    r = requests.post(get_peer_url(max_peer) + "/getblockhashes", data={"myheight": ACTIVE_CHAIN.length})
    hash_list = json.loads(r.text)
    logger.debug(hash_list)
    for hhash in hash_list:
        block = receive_block_from_peer(random.choice(peer_list), hhash)
        if not ACTIVE_CHAIN.add_block(block):
            logger.error("SYNC: Block received is incomplete")
            raise Exception("WTF")


@app.route("/")
def hello():
    data = {"version": consts.MINER_VERSION, "blockheight": len(ACTIVE_CHAIN)}
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
    for i in range(peer_height + 1, ACTIVE_CHAIN.length):
        hash_list.append(dhash(ACTIVE_CHAIN.header_list[i]))
    logger.debug(hash_list)
    return jsonify(hash_list)


@app.route("/newblock", methods=["POST"])
def received_new_block():
    block_json = str(request.form.get("block", None))
    if block_json:
        try:
            block = Block.from_json(block_json)
            for ch in BLOCKCHAIN:
                if ch.add_block(block):
                    # Remove the transactions from MemPools
                    remove_transactions_from_mempool(block)
                    # Broadcast block t other peers
                    for peer in PEER_LIST:
                        try:
                            requests.post(get_peer_url(peer) + "/newblock", data={"block": block.to_json()})
                        except Exception as e:
                            logger.debug("Flask: Requests: cannot send block to peer" + str(peer))
                            pass
                        break
            # TODO Make new chain/ orphan set for Block that is not added
        except Exception as e:
            logger.error("Flask: New Block: invalid block received" + str(e))
            pass


@app.route("/newtransaction", methods=["POST"])
def received_new_transaction():
    global MEMPOOL
    transaction_json = str(request.form.get("transaction", None))
    if transaction_json:
        try:
            tx = Transaction.from_json(transaction_json).object()
            # Add transaction to Mempool
            if ACTIVE_CHAIN.is_transaction_valid(tx):
                logger.debug("Valid Transaction received, Adding to Mempool")
                MEMPOOL.add(tx)
            else:
                logger.debug("The transation is not valid, not added to Mempool")
                return jsonify("Not Valid Transaction")

            # Broadcast block t other peers
            for peer in PEER_LIST:
                try:
                    requests.post(get_peer_url(peer) + "/newtransaction", data={"transaction": tx.to_json()})
                except Exception as e:
                    logger.debug("Flask: Requests: cannot send block to peer" + str(peer))
                    pass
        except Exception as e:
            logger.error("Flask: New Transaction: invalid tx received" + str(e))
            pass
    return jsonify("Done")


if __name__ == "__main__":

    ACTIVE_CHAIN.add_block(genesis_block)

    peer_list = fetch_peer_list()
    new_peer_list = []
    for peer in peer_list:
        if greet_peer(peer):
            new_peer_list.append(peer)
    peer_list = new_peer_list

    print(peer_list)
    sync(peer_list)
    start_mining_thread()
    # Start Flask Server
    app.run(port=consts.MINER_SERVER_PORT, threaded=True, debug=True)
