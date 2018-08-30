import argparse
import sys
import logging

# LOGGING CONSTANTS
LOG_DIRECTORY = "log/"
DATE_FORMAT = "%d %b %H:%M:%S"
LOG_LEVEL = logging.DEBUG

# WALLET CONSTANTS
WALLET_STORAGE_FILE = "wallets.log"

# DNS SEED CONSTANTS
ENTRY_DURATION = 60 * 60 * 24 * 1  # duration in seconds
SEED_SERVER_URL = "http://localhost:8080"
SEED_SERVER_PORT = 8080

# MINER CONSTANTS
MINER_SERVER_PORT = 9000
MINER_VERSION = "0.1"

# DB CONSTANTS
BLOCK_DB_LOC = "db/block.db"

# BLOCKCHAIN CONSTANTS
HASH_LENGTH_HEX = 64  # 256 bit string is 64 hexa_dec string

MAX_BLOCK_SIZE_KB = 4096
MAX_SATOSHIS_POSSIBLE = 21_000_000 * 100_000_000

INITIAL_BLOCK_REWARD = 50 * 100_000_000
REWARD_UPDATE_INTERVAL = 20_000

# A block cannot have timestamp greater than this time in the future
BLOCK_MAX_TIME_FUTURE_SECS = 2 * 60 * 60

BLOCK_DIFFICULTY_UPDATE_INTERVAL = 1024  # number of blocks
AVERAGE_BLOCK_MINE_INTERVAL = 10 * 60  # seconds
MAXIMUM_TARGET_DIFFICULTY = 255

# Cheat Code
BLOCK_MINING_SPEEDUP = 40

# Define Values from arguments passed
parser = argparse.ArgumentParser()

parser.add_argument("--version", help="Print Implementation Version", action="store_true")
parser.add_argument("-p", "--port", type=int, help="Port on which the somechain server should run", default=MINER_SERVER_PORT)
parser.add_argument("-s", "--seed-server", type=str, help="Url on which the seed server is running", default=SEED_SERVER_URL)
group = parser.add_mutually_exclusive_group()
group.add_argument("-v", "--verbose", action="store_true")
group.add_argument("-q", "--quiet", action="store_true")
args = parser.parse_args()

# Print Somechain Version
if args.version:
    print("## Somchain Version: " + str(MINER_VERSION) + " ##")
    sys.exit(0)

# Set Logging Level
if args.quiet:
    LOG_LEVEL = logging.INFO
elif args.verbose:
    LOG_LEVEL = logging.DEBUG

# Set Server Port
MINER_SERVER_PORT = args.port

# Set Seed Server URL
SEED_SERVER_URL = args.seed_server

# Coinbase Maturity
COINBASE_MATURITY = 0

# public key
WALLET_PUBLIC = "758144305b954de508f7fd32d0b8751eb3de887e897812e9c86e7476d59dbe45fd79853c7f26941c3eb3368a7e061094f07b325421be7f38caa8970e4255a2db"

# private key
WALLET_PRIVATE = "652ef10ccab3d0b8879def583b3fd6b40c22458a0098da7d395b1978a556d8cb"
