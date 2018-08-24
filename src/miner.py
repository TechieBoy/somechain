import utils.constants as consts
import requests
import random
from flask import Flask, jsonify, request
from core import *
import time
import json
import threading
from utils.storage import *
from typing import Mapping, Any

app = Flask(__name__)

ACTIVE_CHAIN = []

BLOCKCHAIN = [ACTIVE_CHAIN]

PEER_LIST = []


def fetch_peer_list():
    r = requests.post(consts.SEED_SERVER_URL, data={'port': consts.MINER_SERVER_PORT})
    peer_list = json.loads(r.text)
    return peer_list


def get_peer_url(peer: Mapping[str, Any]) -> str:
    return "http://" + str(peer['ip']) + ':' + str(peer['port'])


def greet_peer(peer: Mapping[str, Any]) -> List:
    url = get_peer_url(peer)
    r = requests.get(url)
    return json.loads(r.text)


def add_block_to_chain(block: Block) -> bool:
    ACTIVE_CHAIN.append(block.header)
    return True


def receive_block_from_peer(peer: Mapping[str, Any], header_hash) -> Block:
    r = requests.post(get_peer_url(peer), data={'header_hash': header_hash})
    return Block.from_json(r.text)


def sync(peer_list):
    max_peer = max(peer_list, key=lambda k: k['blockheight'])
    r = requests.post(get_peer_url(max_peer) + "/getblockhashes/", data={'myheight': len(ACTIVE_CHAIN)})
    hash_list = json.loads(r.text)
    for hhash in hash_list:
        peer_url = get_peer_url(random.choice(peer_list)) + "/getblock/"
        r = requests.post(peer_url, data={"headerhash": hhash})
        block = Block.from_json(r.text)
        if block.is_valid():
            add_block_to_db(block)
            add_block_to_chain(block)
        else:
            raise Exception("WTF")


@app.route("/")
def hello():
    data = {
        'version': consts.MINER_VERSION,
        'blockheight': len(ACTIVE_CHAIN)
    }
    return jsonify(data)


@app.route("/getblock", methods=['POST'])
def getblock():
    hhash = request.form.get('headerhash')
    if hhash:
        return get_block_from_db(hhash)
    return "Hash hi nahi bheja LOL"


@app.route("/getblockhashes", methods=['POST'])
def send_block_hashes():
    peer_height = request.form.get('myheight')
    hash_list = []
    for i in range(peer_height + 1, len(ACTIVE_CHAIN)):
        hash_list.append(str(ACTIVE_CHAIN[i]))
    return jsonify(hash_list)


if __name__ == "__main__":

    add_block_to_chain(genesis_block)
    add_block_to_db(genesis_block)


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
            data = greet_peer(peer)
            # Update the peer data in the peer list with the new data recieved from the peer.
            peer.update(data)
        print(peer_list)
        sync(peer_list)


    t = threading.Thread(target=func)
    t.start()

    app.run(port=consts.MINER_SERVER_PORT, threaded=True, debug=True)
