import utils.constants as consts
import requests
import json

def fetch_peer_list():
    r = requests.post(consts.SEED_SERVER_URL, data={'port':consts.MINER_SERVER_PORT})
    peer_list = json.loads(r.text)
    return peer_list

print(fetch_peer_list())
