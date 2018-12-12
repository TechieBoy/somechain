import json
import time
from functools import lru_cache
from multiprocessing import Pool, Process
from threading import Thread, Timer
from typing import Any, Dict, List

import requests
import waitress
from bottle import BaseTemplate, Bottle, request, response, static_file, template

import utils.constants as consts
from core import Block, BlockChain, SingleOutput, Transaction, TxIn, TxOut, genesis_block
from miner import Miner
from utils.logger import logger
from utils.storage import get_block_from_db, get_wallet_from_db
from utils.utils import compress, decompress, dhash, get_time_difference_from_now_secs
from wallet import Wallet

app = Bottle()
BaseTemplate.defaults["get_url"] = app.get_url

LINE_PROFILING = False

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


def send_to_all_peers(url, data):
    def request_task(peers, url, data):
        for peer in peers:
            try:
                requests.post(get_peer_url(peer) + url, data=data, timeout=(5, 1))
            except Exception as e:
                logger.debug("Server: Requests: Error while sending data in process" + str(peer))

    Process(target=request_task, args=(PEER_LIST, url, data), daemon=True).start()


def start_mining_thread():
    time.sleep(5)
    Thread(target=mining_thread_task, name="Miner", daemon=True).start()


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
    return Block.from_json(decompress(r.text)).object()


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
    hash_list = json.loads(decompress(r.text.encode()))
    # logger.debug("Received the Following HashList from peer " + str(get_peer_url(max_peer)))
    # logger.debug(hash_list)
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
    if current_balance < bounty + fees:
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
                data=compress(transaction.to_json()),
                timeout=(5, 1),
            )
        except Exception as e:
            logger.error("Wallet: Could not Send Transaction. Try Again." + str(e))
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
    tx.fees = fees
    tx.sign(w)


@app.post("/greetpeer")
def hello():
    try:
        peer = {}
        peer["port"] = request.forms.get("port")
        peer["ip"] = request.remote_addr
        peer["time"] = time.time()
        peer["version"] = request.forms.get("version")
        peer["blockheight"] = request.forms.get("blockheight")

        ADD_ENTRY = True
        for entry in PEER_LIST:
            ip = entry["ip"]
            port = entry["port"]
            if ip == peer["ip"] and port == peer["port"]:
                ADD_ENTRY = False
        if ADD_ENTRY:
            PEER_LIST.append(peer)
            logger.debug("Server: Greet, A new peer joined, Adding to List")
    except Exception as e:
        logger.debug("Server: Greet Error: " + str(e))
        pass

    data = {"version": consts.MINER_VERSION, "blockheight": BLOCKCHAIN.active_chain.length}
    response.content_type = "application/json"
    return json.dumps(data)


@lru_cache(maxsize=128)
def cached_get_block(headerhash: str) -> str:
    if headerhash:
        db_block = get_block_from_db(headerhash)
        if db_block:
            return compress(db_block)
        else:
            logger.error("ERROR CALLED GETBLOCK FOR NON EXISTENT BLOCK")
    return "Hash hi nahi bheja LOL"


@app.post("/getblock")
def getblock():
    hhash = request.forms.get("headerhash")
    return cached_get_block(hhash)


@app.post("/checkblock")
def checkblock():
    headerhash = request.forms.get("headerhash")
    response.content_type = "application/json"
    if headerhash:
        with Pool(4) as p:
            hash_list = set(p.map(dhash, BLOCKCHAIN.active_chain.header_list))
            if headerhash in hash_list:
                return json.dumps(True)
    return json.dumps(False)


@app.post("/getblockhashes")
def send_block_hashes():
    peer_height = int(request.forms.get("myheight"))
    hash_list = []
    for i in range(peer_height, BLOCKCHAIN.active_chain.length):
        hash_list.append(dhash(BLOCKCHAIN.active_chain.header_list[i]))
    # logger.debug("Server: Sending Peer this Block Hash List: " + str(hash_list))
    return compress(json.dumps(hash_list)).decode()


@lru_cache(maxsize=16)
def process_new_block(request_data: bytes) -> str:
    global BLOCKCHAIN
    block_json = decompress(request_data)
    if block_json:
        try:
            block = Block.from_json(block_json).object()
            # Check if block already exists
            if get_block_from_db(dhash(block.header)):
                logger.info("Server: Received block exists, doing nothing")
                return "Block already Received Before"
            if BLOCKCHAIN.add_block(block):
                logger.info("Server: Received a New Valid Block, Adding to Chain")

                logger.debug("Server: Sending new block to peers")
                # Broadcast block to other peers
                send_to_all_peers("/newblock", request_data)

            # TODO Make new chain/ orphan set for Block that is not added
        except Exception as e:
            logger.error("Server: New Block: invalid block received " + str(e))
            return "Invalid Block Received"

        # Kill Miner
        t = Timer(1, miner.stop_mining)
        t.start()
        return "Block Received"
    logger.error("Server: Invalid Block Received")
    return "Invalid Block"


@app.post("/newblock")
def received_new_block():
    print(request)
    return process_new_block(request.body.read())


@lru_cache(maxsize=16)
def process_new_transaction(request_data: bytes) -> str:
    global BLOCKCHAIN
    transaction_json = decompress(request_data)
    if transaction_json:
        try:
            tx = Transaction.from_json(transaction_json).object()
            # Add transaction to Mempool
            if tx not in BLOCKCHAIN.mempool:
                if BLOCKCHAIN.active_chain.is_transaction_valid(tx):
                    logger.debug("Valid Transaction received, Adding to Mempool")
                    BLOCKCHAIN.mempool.add(tx)
                    # Broadcast block to other peers
                    send_to_all_peers("/newtransaction", request_data)
                else:
                    return "Transaction Already received"
            else:
                logger.debug("The transation is not valid, not added to Mempool")
                return "Not Valid Transaction"
        except Exception as e:
            logger.error("Server: New Transaction: Invalid tx received: " + str(e))
            raise e
            return "Not Valid Transaction"
    return "Done"


# Transactions for all active chains
@app.post("/newtransaction")
def received_new_transaction():
    return process_new_transaction(request.body.read())


@app.get("/")
def home():
    return template("home.html")


@app.get("/send")
def get_send():
    return template("send.html", message="")


@app.post("/send")
def post_send():
    receiver_port = request.forms.get("port")
    publickey = get_wallet_from_db(receiver_port)[1]
    bounty = request.forms.get("scoins")
    message = ""
    try:
        amt = int(bounty)
        if check_balance() > amt:
            message = "Your scoins are sent !!!"
            send_bounty(amt, publickey, consts.FEES)
        else:
            message = "You have insufficient balance !!!"
        return template("send.html", message=message)
    except Exception as e:
        print(e)
        message = "The value must be numeric"
        return template("send.html", message=message)


@app.get("/checkbalance")
def checkblance():
    return str(check_balance())


@app.route("/static/<filename:path>", name="static")
def serve_static(filename):
    return static_file(filename, root="static")


@app.get("/info")
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
        + "<br>Public Key: <br>"
        + str(get_wallet_from_db(consts.MINER_SERVER_PORT)[1])
    )
    return s

@app.get("/chains")
def visualize_chain():
    data = []
    for i, chain in enumerate(BLOCKCHAIN.chains):
        headers = []
        for hdr in chain.header_list:
            d = {}
            d['hash'] = dhash(hdr)[-5:]
            d['time'] = hdr.timestamp
            headers.append(d)
        data.append(headers)
    return template('chains.html', data=data)


if __name__ == "__main__":
    try:
        BLOCKCHAIN.add_block(genesis_block)

        # Sync with all my peers
        sync_with_peers()

        # Start mining Thread
        Thread(target=start_mining_thread, daemon=True).start()

        # Start server
        if LINE_PROFILING:
            from wsgi_lineprof.middleware import LineProfilerMiddleware

            with open("lineprof" + str(consts.MINER_SERVER_PORT) + ".log", "w") as f:
                app = LineProfilerMiddleware(app, stream=f, async_stream=True)
                waitress.serve(app, host="0.0.0.0", threads=16, port=consts.MINER_SERVER_PORT)
        else:
            waitress.serve(app, host="0.0.0.0", threads=16, port=consts.MINER_SERVER_PORT)

    except KeyboardInterrupt:
        miner.stop_mining()
