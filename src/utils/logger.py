import logging
from datetime import datetime
import src.utils.constants as consts

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s\t%(message)s\t%(levelname)s",
    datefmt=consts.DATE_FORMAT,
    handlers=[
        logging.FileHandler(consts.LOG_DIRECTORY + datetime.strftime(datetime.now(), consts.DATE_FORMAT) + ".log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()