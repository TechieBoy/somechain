import sys
import requests
import random
from flask import Flask, jsonify, request
import time
import json
import threading
from typing import Dict, Any, List, Set

sys.path.append("..")
from core import Block, Chain, genesis_block, Transaction
from miner import Miner
from utils.storage import get_block_from_db, add_block_to_db
import utils.constants as consts
from utils.utils import dhash
from utils.logger import logger


app = Flask(__name__)

# TODO: Guarantee that ACTIVE_CHAIN is max length chain
ACTIVE_CHAIN = Chain()

BLOCKCHAIN: List[Chain] = [ACTIVE_CHAIN]

PEER_LIST = []

mempool: Set[Transaction]

PAYOUT_ADDR = "Put my wallet address here"


def remove_transactions_from_mempool(block: Block):
    """Removes transaction from the mempool based on a new received block
    
    Arguments:
        block {Block} -- The block which is received
    """

    global mempool
    mempool = set([x for x in mempool if x not in block.transactions])


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
    r = requests.post(get_peer_url(peer) + "/getblock", data={"headerhash": header_hash})
    return Block.from_json(r.text)


def sync(peer_list):
    max_peer = max(peer_list, key=lambda k: k["blockheight"])
    r = requests.post(get_peer_url(max_peer) + "/getblockhashes", data={"myheight": ACTIVE_CHAIN.length})
    hash_list = json.loads(r.text)
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
    for i in range(peer_height + 1, len(ACTIVE_CHAIN)):
        hash_list.append(dhash(ACTIVE_CHAIN[i]))
    return jsonify(hash_list)


@app.route("/newblock", methods=["POST"])
def received_new_block():
    block_json = str(request.form.get("block", None))
    if block_json:
        try:
            block = Block.from_json(block_json)
            for ch in BLOCKCHAIN:
                if ch.add_block(block):
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


if __name__ == "__main__":

    ACTIVE_CHAIN.add_block(genesis_block)

    # # ORDER
    # Get list of peers ✓
    # Contact peers and get current state of blockchain ✓
    # Sync upto the current blockchain ✓
    # Start the flask server and listen for future blocks and transactions.
    # Start a thread to handle the new block/transaction

    def func():
        time.sleep(2)  # wait for the flask server to start running
        peer_list = fetch_peer_list()
        # # Add yourself as a peer( doing so just to test as currently this node is the only node on the network)
        # peer_list.append({'ip': "localhost", 'port': consts.MINER_SERVER_PORT, 'time': time.time()})
        for peer in peer_list:
            # TODO delete the peer if could not establish a connection.
            print(get_peer_url(peer))
            data = greet_peer(peer)
            # Update the peer data in the peer list with the new data recieved from the peer.
            peer.update(data)
        print(peer_list)
        sync(peer_list)
        # print(ACTIVE_CHAIN)
        # print(get_block_from_db(dhash(ACTIVE_CHAIN[0])))

    t = threading.Thread(target=func)
    t.start()

    miner = Miner()
    miner.start_mining(mempool, ACTIVE_CHAIN, PAYOUT_ADDR)
    miner.stop_mining()
    app.run(port=consts.MINER_SERVER_PORT, threaded=True, debug=True)
