import time

import json
import waitress
from bottle import Bottle, request

import utils.constants as consts
from utils.logger import logger

app = Bottle()

PEER_LIST = []


def validate_peer_list():
    global PEER_LIST
    validated_peer_list = []
    for entry in PEER_LIST:
        last_time = time.time()
        if time.time() - last_time < consts.ENTRY_DURATION:
            validated_peer_list.append(entry)
    PEER_LIST = validated_peer_list


@app.route("/")
def return_peer_list():
    global PEER_LIST
    validate_peer_list()
    return json.dumps(PEER_LIST)


@app.route("/", method="POST")
def update_and_return_peer_list():
    global PEER_LIST
    validate_peer_list()

    new_port = request.forms.get("port")
    new_ip = request.environ.get("HTTP_X_FORWARDED_FOR") or request.environ.get("REMOTE_ADDR")
    ADD_ENTRY = True

    peer_list = []
    for entry in PEER_LIST:
        ip = entry["ip"]
        port = entry["port"]
        if new_port and ip == new_ip and port == new_port:
            entry["time"] = time.time()
            ADD_ENTRY = False
        else:
            peer_list.append(entry)
    if new_port and ADD_ENTRY:
        PEER_LIST.append({"ip": new_ip, "port": new_port, "time": time.time()})
    logger.debug(PEER_LIST)
    return json.dumps(peer_list)


waitress.serve(app, host="0.0.0.0", threads=4, port=consts.SEED_SERVER_PORT)
