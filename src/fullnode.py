import json
import time
from multiprocessing import Pool, Process
from threading import Thread, Timer
from typing import Any, Dict, List, Set

import flask_profiler
import requests
from flask import Flask, jsonify, render_template, request

import utils.constants as consts
from core import (Block, BlockChain, SingleOutput, Transaction, TxIn, TxOut,
                  genesis_block)
from miner import Miner
from utils.logger import logger
from utils.storage import get_block_from_db, get_wallet_from_db
from utils.utils import dhash, get_time_difference_from_now_secs
from wallet import Wallet

app = Flask(__name__)
app.config["DEBUG"] = True

# You need to declare necessary configuration to initialize
# flask-profiler as follows:
app.config["flask_profiler"] = {"enabled": app.config["DEBUG"], "storage": {"engine": "sqlite"}, "ignore": ["^/static/.*"]}

BLOCKCHAIN = BlockChain()

PEER_LIST: List[Dict[str, Any]] = []

MY_WALLET = Wallet()

miner = Miner()


def mining_thread_task():
    while True:
        if not miner.is_mining():
            mlist = list(BLOCKCHAIN.mempool)
            fees, size = miner.calculate_transaction_fees_and_size(mlist)
            time_diff = -get_time_difference_from_now_secs(BLOCKCHAIN.active_chain.header_list[-1].timestamp)
            if (
                fees >= 1
                or (size >= consts.MAX_BLOCK_SIZE_KB / 1.6)
                or (time_diff > consts.AVERAGE_BLOCK_MINE_INTERVAL / consts.BLOCK_MINING_SPEEDUP)
            ):
                miner.start_mining(BLOCKCHAIN.mempool, BLOCKCHAIN.active_chain, MY_WALLET.public_key)
        time.sleep(5)


def send_to_all_peers(peers, url, data):
    def request_task(peers, url, data):
        for peer in peers:
            try:
                requests.post(get_peer_url(peer) + url, data=data, timeout=(5, 1))
            except Exception as e:
                logger.debug("Flask: Requests: Error while sending data in process" + str(peer))

    Process(target=request_task, args=(peers, url, data), daemon=True).start()


def start_mining_thread():
    time.sleep(5)
    t = Thread(target=mining_thread_task, name="Miner", daemon=True)
    t.start()


def fetch_peer_list() -> List[Dict[str, Any]]:
    try:
        r = requests.post(consts.SEED_SERVER_URL, data={"port": consts.MINER_SERVER_PORT})
        peer_list = json.loads(r.text)
        return peer_list
    except Exception as e:
        logger.error("Could not connect to DNS Seed")
        return []


def get_peer_url(peer: Dict[str, Any]) -> str:
    return "http://" + str(peer["ip"]) + ":" + str(peer["port"])


def greet_peer(peer: Dict[str, Any]) -> bool:
    try:
        url = get_peer_url(peer)
        data = {"port": consts.MINER_SERVER_PORT, "version": consts.MINER_VERSION, "blockheight": BLOCKCHAIN.active_chain.length}
        # Send a POST request to the peer
        r = requests.post(url + "/greetpeer", data=data)
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
    return Block.from_json(r.text).object()


def check_block_with_peer(peer, hhash):
    r = requests.post(get_peer_url(peer) + "/checkblock", data={"headerhash": hhash})
    result = json.loads(r.text)
    if result:
        return True
    return False


def get_block_header_hash(height):
    return dhash(BLOCKCHAIN.active_chain.header_list[height])


def find_fork_height(peer):
    fork_height = BLOCKCHAIN.active_chain.length - 1
    if check_block_with_peer(peer, get_block_header_hash(fork_height)):
        return fork_height
    else:
        left = 0
        right = BLOCKCHAIN.active_chain.length - 1
        while left < right:
            mid = (left + right) // 2
            if check_block_with_peer(peer, get_block_header_hash(mid)):
                left = mid + 1
            else:
                right = mid
        return left


def sync(max_peer):
    fork_height = find_fork_height(max_peer)
    r = requests.post(get_peer_url(max_peer) + "/getblockhashes", data={"myheight": fork_height})
    hash_list = json.loads(r.text)
    logger.debug("Received the Following HashList from peer " + str(get_peer_url(max_peer)))
    logger.debug(hash_list)
    for hhash in hash_list:
        block = receive_block_from_peer(max_peer, hhash)
        if not BLOCKCHAIN.add_block(block):
            logger.error("Sync: Block received is invalid, Cannot Sync")
            break
    return


# Periodically sync with all the peers
def sync_with_peers():
    try:
        logger.debug("Sync: Calling Sync")
        PEER_LIST = fetch_peer_list()
        new_peer_list = []
        for peer in PEER_LIST:
            if greet_peer(peer):
                new_peer_list.append(peer)
        PEER_LIST = new_peer_list

        if PEER_LIST:
            max_peer = max(PEER_LIST, key=lambda k: k["blockheight"])
            logger.debug(f"Sync: Syncing with {get_peer_url(max_peer)}, he seems to have height {max_peer['blockheight']}")
            sync(max_peer)
    except Exception as e:
        logger.error("Sync: Error: " + str(e))
    Timer(consts.AVERAGE_BLOCK_MINE_INTERVAL // 2, sync_with_peers).start()


def check_balance():
    current_balance = 0
    for x, utxo_list in BLOCKCHAIN.active_chain.utxo.utxo.items():
        tx_out = utxo_list[0]
        if tx_out.address == MY_WALLET.public_key:
            current_balance += int(tx_out.amount)
    return int(current_balance)


def send_bounty(bounty: int, receiver_public_key: str, fees: int):
    current_balance = check_balance()
    if current_balance < bounty+fees:
        print("Insuficient balance ")
        print("Current balance : " + str(current_balance))
        print("You need " + str(current_balance - bounty) + "more money")

    else:
        transaction = Transaction(
            version=1,
            locktime=0,
            timestamp=2,
            is_coinbase=False,
            fees=0,
            vin={},
            vout={0: TxOut(amount=bounty, address=receiver_public_key), 1: TxOut(amount=0, address=MY_WALLET.public_key)},
        )
        calculate_transaction_fees(transaction, MY_WALLET, bounty, fees)

        logger.debug(transaction)
        logger.info("Wallet: Attempting to Send Transaction")
        try:
            requests.post(
                "http://0.0.0.0:" + str(consts.MINER_SERVER_PORT) + "/newtransaction",
                data={"transaction": transaction.to_json()},
                timeout=(5, 1),
            )
        except Exception as e:
            logger.error("Wallet: Could not Send Transaction. Try Again.")
        else:
            logger.info("Wallet: Transaction Sent, Wait for it to be Mined")


def calculate_transaction_fees(tx: Transaction, w: Wallet, bounty: int, fees: int):
    current_amount = 0
    i = 0
    for so, utxo_list in BLOCKCHAIN.active_chain.utxo.utxo.items():
        tx_out = utxo_list[0]
        if utxo_list[2]:
            # check for coinbase TxIn Maturity
            if not (BLOCKCHAIN.active_chain.length - utxo_list[1].height) >= consts.COINBASE_MATURITY:
                continue
        if current_amount >= bounty + fees:
            break
        if tx_out.address == w.public_key:
            current_amount += tx_out.amount
            tx.vin[i] = TxIn(payout=SingleOutput.from_json(so), pub_key=w.public_key, sig="")
            i += 1
    tx.vout[1].amount = current_amount - bounty - fees
    logger.debug(f"Amount: {tx.vout[1].amount}, CA:{current_amount}, Bounty:{bounty}, Fees:{fees}")
    tx.fees = fees

    tx.sign(w)


@app.route("/greetpeer", methods=["POST"])
def hello():
    try:
        peer = {}
        peer["port"] = request.form["port"]
        peer["ip"] = request.remote_addr
        peer["time"] = time.time()
        peer["version"] = request.form["version"]
        peer["blockheight"] = request.form["blockheight"]

        ADD_ENTRY = True
        for entry in PEER_LIST:
            ip = entry["ip"]
            port = entry["port"]
            if ip == peer["ip"] and port == peer["port"]:
                ADD_ENTRY = False
        if ADD_ENTRY:
            PEER_LIST.append(peer)
            logger.debug("Flask: Greet, A new peer joined, Adding to List")
    except Exception as e:
        logger.debug("Flask: Greet Error: " + str(e))
        pass

    data = {"version": consts.MINER_VERSION, "blockheight": BLOCKCHAIN.active_chain.length}
    return jsonify(data)


@app.route("/getblock", methods=["POST"])
def getblock():
    hhash = request.form.get("headerhash")
    if hhash:
        return get_block_from_db(hhash)
    return "Hash hi nahi bheja LOL"


@app.route("/checkblock", methods=["POST"])
def checkblock():
    hhash = request.form.get("headerhash")
    if hhash:
        with Pool(4) as p:
            hash_list = set(p.map(dhash, BLOCKCHAIN.active_chain.header_list))
            if hhash in hash_list:
                return jsonify(True)
    return jsonify(False)


@app.route("/getblockhashes", methods=["POST"])
def send_block_hashes():
    peer_height = int(request.form.get("myheight"))
    hash_list = []
    for i in range(peer_height, BLOCKCHAIN.active_chain.length):
        hash_list.append(dhash(BLOCKCHAIN.active_chain.header_list[i]))
    logger.debug("Flask: Sending Peer this Block Hash List: " + str(hash_list))
    return jsonify(hash_list)


@app.route("/newblock", methods=["POST"])
def received_new_block():
    global BLOCKCHAIN
    block_json = str(request.form.get("block", None))
    if block_json:
        try:
            block = Block.from_json(block_json).object()
            # Check if block already exists
            if get_block_from_db(dhash(block.header)):
                logger.info("Flask: Received block exists, doing nothing")
                return "Block already Received Before"
            if BLOCKCHAIN.add_block(block):
                logger.info("Flask: Received a New Valid Block, Adding to Chain")

                logger.debug("Flask: Sending new block to peers")
                # Broadcast block to other peers
                send_to_all_peers(PEER_LIST, "/newblock", data={"block": block.to_json()})

            # TODO Make new chain/ orphan set for Block that is not added
        except Exception as e:
            logger.error("Flask: New Block: invalid block received " + str(e))
            return "Invalid Block Received"

        # Kill Miner
        t = Timer(1, miner.stop_mining)
        t.start()
        return "Block Received"
    logger.error("Flask: Invalid Block Received")
    return "Invalid Block"


# Transactions for all active chains
@app.route("/newtransaction", methods=["POST"])
def received_new_transaction():
    transaction_json = str(request.form.get("transaction", None))
    if transaction_json:
        try:
            tx = Transaction.from_json(transaction_json).object()
            # Add transaction to Mempool
            if tx not in BLOCKCHAIN.mempool:
                if BLOCKCHAIN.active_chain.is_transaction_valid(tx):
                    logger.debug("Valid Transaction received, Adding to Mempool")
                    BLOCKCHAIN.mempool.add(tx)
                    # Broadcast block t other peers
                    send_to_all_peers(PEER_LIST, "/newtransaction", data={"transaction": tx.to_json()})
                else:
                    return jsonify("Transaction Already received")
            else:
                logger.debug("The transation is not valid, not added to Mempool")
                return jsonify("Not Valid Transaction")
        except Exception as e:
            logger.error("Flask: New Transaction: Invalid tx received: " + str(e))
            return jsonify("Not Valid Transaction")
    return jsonify("Done")


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/send", methods=["POST", "GET"])
def send():
    if request.method == "GET":
        return render_template("send.html")

    if request.method == "POST":
        publickey = request.form["public_key"]
        bounty = request.form["satoshis"]
        try:
            amt = int(bounty)
            if len(publickey) == 128:
                if check_balance() > amt:
                    message = "Your satoshis are sent !!!"
                    send_bounty(amt, publickey,consts.FEES)
                    return render_template("send.html", message=message)
                else:
                    message = "You have insufficient balance !!!"
                    return render_template("send.html", message=message)
            else:
                message = "Check your inputs"
                return render_template("send.html", message=message)
        except Exception as e:
            message = "Enter numeric satoshis"
            return render_template("send.html", message=message)


@app.route("/checkbalance")
def checkblance():
    return str(check_balance())


@app.route("/info")
def sendinfo():
    s = (
        "No. of Blocks: "
        + str(BLOCKCHAIN.active_chain.length)
        + "<br>"
        + dhash(BLOCKCHAIN.active_chain.header_list[-1])
        + "<br>"
        + "Number of chains "
        + str(len(BLOCKCHAIN.chains))
        + "<br>"
        + "Balance "
        + str(check_balance())
        + "<br>"
        + "Difficulty: "
        + str(BLOCKCHAIN.active_chain.target_difficulty)
        + "<br>Block reward "
        + str(BLOCKCHAIN.active_chain.current_block_reward())
    )
    return s


# def user_input():
#     while True:
#         try:
#             print("Welcome to your wallet!")
#             option = input("1 -> Check Balance\n2 -> Send Money\n")
#             if option == "1":
#                 current_balance = check_balance()
#                 print("Your current balance is : " + str(current_balance))
#             elif option == "2":
#                 bounty = int(input("Enter Amount\n"))
#                 receiver_port = input("Enter reciever port\n")
#                 send_bounty(bounty, json.loads(get_wallet_from_db(receiver_port))[1])
#             elif option == "3":
#                 print("No. of Blocks: ", ACTIVE_CHAIN.length)
#             elif option == "4":
#                 bounty = int(input("Enter Amount\n"))
#                 receiver_public_key = input("Enter address of receiver\n")
#                 send_bounty(bounty, receiver_public_key)
#             else:
#                 print("Invalid Input. Try Again")
#         except Exception as e:
#             logger.error("UserInput: " + str(e))


if __name__ == "__main__":
    try:
        BLOCKCHAIN.add_block(genesis_block)

        # Sync with all my peers
        sync_with_peers()

        # Start the User Interface Thread
        # t = Thread(target=user_input, name="UserInterface", daemon=True)
        # t.start()

        t = Thread(target=start_mining_thread, daemon=True)
        t.start()

        # Start Flask Server
        logger.info("Flask: Server running at port " + str(consts.MINER_SERVER_PORT))
        flask_profiler.init_app(app)
        app.run(port=consts.MINER_SERVER_PORT, threaded=True, host="0.0.0.0", use_reloader=False)

    except KeyboardInterrupt:
        miner.stop_mining()
