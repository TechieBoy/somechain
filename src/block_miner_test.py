import time

from core import genesis_block, genesis_block_header
from utils.utils import dhash


def is_proper_difficulty(target_difficulty, bhash: str) -> bool:
    pow = 0
    for c in bhash:
        if not c == "0":
            break
        else:
            pow += 1
    if pow < target_difficulty:
        return False
    return True


print(genesis_block, dhash(genesis_block_header))

for difficulty in range(5, 10):
    tss = time.time()
    for n in range(2 ** 64):
        genesis_block_header.nonce = n
        genesis_block_header.target_difficulty = difficulty
        bhash = dhash(genesis_block_header)
        if is_proper_difficulty(difficulty, bhash):
            print(f"Timestamp {int(tss)} Nonce {n} hash {bhash}\n Difficulty {difficulty} in {(time.time() - tss)} secs")
            print(genesis_block_header)
            DONE = True
            break
    if not DONE:
        print("Miner: Exhausted all 2 ** 64 values without finding proper hash")
