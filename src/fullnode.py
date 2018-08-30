import sys
import requests
import random
from flask import Flask, jsonify, request
import time
import json
from typing import Dict, Any, List, Set
from threading import Thread, Timer
from multiprocessing import Process
from wallet import Wallet
import copy

sys.path.append("..")
from core import Block, Chain, genesis_block, Transaction, SingleOutput, TxOut, TxIn
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

PAYOUT_ADDR = consts.WALLET_PUBLIC

miner = Miner()


def mining_thread_task():
    while True:
        if not miner.is_mining():
            mlist = list(MEMPOOL)
            fees, size = miner.calculate_transaction_fees_and_size(mlist)
            time_diff = -get_time_difference_from_now_secs(ACTIVE_CHAIN.header_list[-1].timestamp)
            if (
                fees >= 1000
                or (size >= consts.MAX_BLOCK_SIZE_KB / 1.6)
                or (time_diff > consts.AVERAGE_BLOCK_MINE_INTERVAL / consts.BLOCK_MINING_SPEEDUP)
            ):
                miner.start_mining(MEMPOOL, ACTIVE_CHAIN, PAYOUT_ADDR)
        time.sleep(consts.AVERAGE_BLOCK_MINE_INTERVAL / consts.BLOCK_MINING_SPEEDUP)


def start_mining_thread():
    time.sleep(5)
    t = Thread(target=mining_thread_task, name="Miner", daemon=True)
    t.start()


def remove_transactions_from_mempool(block: Block):
    """Removes transaction from the mempool based on a new received block

    Arguments:
        block {Block} -- The block which is received
    """

    global MEMPOOL
    new_mempool = set()
    for x in MEMPOOL:
        DONE = True
        for t in block.transactions:
            if dhash(x) == dhash(t):
                DONE = False
        if DONE:
            new_mempool.add(x)
    MEMPOOL = new_mempool


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
    if peer_list and len(peer_list) > 0:
        max_peer = max(peer_list, key=lambda k: k["blockheight"])
        logger.debug(get_peer_url(max_peer))
        r = requests.post(get_peer_url(max_peer) + "/getblockhashes", data={"myheight": ACTIVE_CHAIN.length})
        hash_list = json.loads(r.text)
        logger.debug("Received the Following HashList from peer " + str(max_peer))
        logger.debug(hash_list)
        for hhash in hash_list:
            block = receive_block_from_peer(random.choice(peer_list), hhash)
            if not ACTIVE_CHAIN.add_block(block):
                logger.error("SYNC: Block received is invalid, Cannot Sync")
                raise Exception("WTF")
    return


w = Wallet([consts.WALLET_PRIVATE, consts.WALLET_PUBLIC])


def display_wallet():
    print("Public key is : " + w.public_key)
    print("Private key is : " + w.private_key)


def check_balance():
    current_balance = 0
    for x, utxo_list in ACTIVE_CHAIN.utxo.utxo.items():
        tx_out = utxo_list[0]
        if tx_out.address == w.public_key:
            current_balance += int(tx_out.amount)
    print("Your current balance is : " + str(current_balance))
    return int(current_balance)


def send_bounty(bounty: int, receiver_public_key: str):
    current_balance = check_balance()
    if current_balance < bounty:
        print("Insuficient balance ")
        print("Current balance : " + str(current_balance))
        print("you need " + str(current_balance - bounty) + "more money")

    else:
        transaction = Transaction(
            version=1,
            locktime=0,
            timestamp=2,
            is_coinbase=False,
            fees=0,
            vin={},
            vout={0: TxOut(amount=bounty, address=receiver_public_key), 1: TxOut(amount=0, address=w.public_key)},
        )
        calculate_transaction_fees(transaction, w, bounty, fees=100)

        logger.debug(transaction)
        logger.debug("Wallet: Attempting to Send Transaction")
        requests.post(
            "http://0.0.0.0:" + str(consts.MINER_SERVER_PORT) + "/newtransaction", data={"transaction": transaction.to_json()}
        )


def calculate_transaction_fees(tx: Transaction, w: Wallet, bounty: int, fees: int):
    current_amount = 0
    i = 0
    for so, utxo_list in ACTIVE_CHAIN.utxo.utxo.items():
        tx_out = utxo_list[0]
        if utxo_list[2]:
            # check for coinbase TxIn Maturity
            if not ACTIVE_CHAIN.length - utxo_list[1].height > consts.COINBASE_MATURITY:
                continue
        if current_amount > bounty:
            break
        if tx_out.address == w.public_key:
            current_amount += tx_out.amount
            tx.vin[i] = TxIn(payout=SingleOutput.from_json(so), pub_key=w.public_key, sig="")
            i += 1
    tx.vout[1].amount = current_amount - bounty - fees

    tx.fees = fees

    sign_transaction(tx, w)


def sign_transaction(transaction: "Transaction", w: Wallet):
    sign_copy_of_tx = copy.deepcopy(transaction)
    sign_copy_of_tx.vin = {}

    sig = w.sign(sign_copy_of_tx.to_json())
    for i in range(0, len(transaction.vin)):
        transaction.vin[i].sig = sig


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
    global BLOCKCHAIN
    block_json = str(request.form.get("block", None))
    if block_json:
        try:
            block = Block.from_json(block_json).object()
            for ch in BLOCKCHAIN:
                if ch.add_block(block):
                    logger.debug("Flask: Received a New Valid Block, Adding to Chain")
                    # Remove the transactions from MemPools
                    remove_transactions_from_mempool(block)

                    # Broadcast block t other peers
                    for peer in PEER_LIST:
                        try:
                            requests.post(get_peer_url(peer) + "/newblock", data={"block": block.to_json()})
                        except Exception as e:
                            logger.debug("Flask: Requests: cannot send block to peer" + str(peer))
                    break
            # TODO Make new chain/ orphan set for Block that is not added
        except Exception as e:
            logger.error("Flask: New Block: invalid block received " + str(e))
            return "Invalid Block Received"

        # Kill Miner
        t = Timer(1, miner.stop_mining)
        t.start()
        return "Block Received"
    return "Invalid Block"


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


def user_input():
    while True:
        try:
            print("Welcome to your wallet!")
            option = input("1 -> Check balance\n2 -> Send money\n")
            if option == "1":
                check_balance()
            elif option == "2":
                bounty = int(input("Enter bounty\n"))
                receiver_public_key = input("Enter address of receiver\n")
                send_bounty(bounty, receiver_public_key)
            elif option == "3":
                print(ACTIVE_CHAIN.length)
            else:
                print("Invalid Input. Try Again")
        except Exception as e:
            logger.error("UserInput: " + str(e))


if __name__ == "__main__":
    try:
        ACTIVE_CHAIN.add_block(genesis_block)

        peer_list = fetch_peer_list()
        new_peer_list = []
        for peer in peer_list:
            if greet_peer(peer):
                new_peer_list.append(peer)
        peer_list = new_peer_list
        sync(peer_list)

        t = Thread(target=user_input, name="UserInterface", daemon=True)
        t.start()

        t = Thread(target=start_mining_thread, daemon=True)
        t.start()

        # Start Flask Server
        logger.info("Flask: Server running at port " + str(consts.MINER_SERVER_PORT))
        app.run(port=consts.MINER_SERVER_PORT, threaded=True)

    except KeyboardInterrupt:
        miner.stop_mining()
