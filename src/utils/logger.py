import logging
from datetime import datetime
import src.utils.constants as consts
from flask.logging import default_handler

logger = logging.getLogger("somechain")
formatter = logging.Formatter("%(asctime)s %(levelname)-10s %(message)s", consts.DATE_FORMAT)
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler(consts.LOG_DIRECTORY + datetime.strftime(datetime.now(), consts.DATE_FORMAT) + ".log")
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.DEBUG)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
stream_handler.setLevel(consts.LOG_LEVEL)

logger.addHandler(file_handler)
logger.addHandler(stream_handler)

log = logging.getLogger('werkzeug')
log.setLevel(logging.INFO)
flask_handler = logging.FileHandler(consts.LOG_DIRECTORY + datetime.strftime(datetime.now(), consts.DATE_FORMAT) + ".flask.log")
flask_handler.setFormatter(formatter)
log.addHandler(flask_handler)
