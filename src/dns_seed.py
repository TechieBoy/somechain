import time

from flask import Flask, jsonify, request

import utils.constants as consts
from utils.logger import logger

app = Flask(__name__)

PEER_LIST = []


def validate_peer_list():
    global PEER_LIST
    validated_peer_list = []
    for entry in PEER_LIST:
        last_time = time.time()
        if time.time() - last_time < consts.ENTRY_DURATION:
            validated_peer_list.append(entry)
    PEER_LIST = validated_peer_list


@app.route("/", methods=["GET", "POST"])
def peer_list():
    global PEER_LIST
    ADD_ENTRY = False

    validate_peer_list()

    if request.method == "POST":
        if request.form.get("port"):
            new_port = request.form["port"]
            new_ip = request.remote_addr
            ADD_ENTRY = True

    peer_list = []
    for entry in PEER_LIST:
        ip = entry["ip"]
        port = entry["port"]
        if ADD_ENTRY and ip == new_ip and port == new_port:
            entry["time"] = time.time()
            ADD_ENTRY = False
        else:
            peer_list.append(entry)
    if ADD_ENTRY:
        PEER_LIST.append({"ip": new_ip, "port": new_port, "time": time.time()})
    logger.debug(PEER_LIST)
    return jsonify(peer_list)


app.run(host="0.0.0.0", port=consts.SEED_SERVER_PORT)
