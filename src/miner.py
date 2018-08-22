import utils.constants as consts
import requests
import json
from flask import Flask, jsonify, request
from core import *
import time
import threading

app = Flask(__name__)

ACTIVE_CHAIN = [genesis_block]

BLOCKCHAIN = [ACTIVE_CHAIN]

PEER_LIST = []

def fetch_peer_list():
    r = requests.post(consts.SEED_SERVER_URL, data={'port':consts.MINER_SERVER_PORT})
    peer_list = json.loads(r.text)
    return peer_list

def greet_peer(ip, port):
    url = "http://"+str(ip)+":"+str(port)+"/"
    r = requests.get(url)
    return json.loads(r.text)



@app.route("/")
def hello():
    data = {
            'version': consts.MINER_VERSION,
            'blockheight': len(ACTIVE_CHAIN)
            }
    return jsonify(data)



if __name__ == "__main__":
    # # ORDER
    # Get list of peers
    # Contact peers and get current state of blockchain
    # Sync upto the current blockchain
    # Start the flask server and listen for future blocks and transactions.
    # Start a thread to handle the new block/transaction

    def func():
        time.sleep(2) # wait for the flask server to start running
        peer_list = fetch_peer_list() 
        # Add yourself as a peer( doing so just to test as currently this node is the only node on the network)
        peer_list.append({'ip':"localhost", 'port':consts.MINER_SERVER_PORT, 'time':time.time()})
        for peer in peer_list:
            #TODO delete the peer if could not establish a connection.
            data = greet_peer(ip=peer['ip'], port=peer['port'])
            # Update the peer data in the peer list with the new data recieved from the peer.
            peer.update(data)
        print(peer_list)
    
    t = threading.Thread(target=func)
    t.start()

    app.run(port=consts.MINER_SERVER_PORT, threaded=True, debug=True)

    