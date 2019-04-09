# -*- coding: utf-8 -*-

import logging.handlers
import sys
from pathlib import Path

import requests
from ratelimit import limits


class RateLimitException(Exception):
    pass


@limits(calls=500, period=60 * 60)  # Rate limit is 600/600 but let's play it safe
def fetch_account(key: str):
    try:
        response = requests.get(
            "https://api.guildwars2.com/v2/account?access_token=" + key
        )
        if (
            response.status_code in [400, 403] and "invalid key" in response.text
        ):  # Invalid API key
            return None
        elif response.status_code == 200:
            return response.json()
        elif response.status_code == 429:  # Rate limit
            raise RateLimitException()
        raise requests.RequestException()  # API down
    except requests.RequestException:
        logging.exception("Failed to fetch API")
        raise


def init_logger(name: str):
    if not Path("logs").exists():
        Path("logs").mkdir()

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    hldr = logging.handlers.TimedRotatingFileHandler(
        "logs/{}.log".format(name), when="W0", encoding="utf-8", backupCount=16
    )
    fmt = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    hldr.setFormatter(fmt)
    logger.addHandler(hldr)
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    stream.setLevel(logging.DEBUG)
    logger.addHandler(stream)
