import logging

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
        if response.status_code in [400, 403]:  # Invalid API key
            return None
        elif response.status_code == 200:
            return response.json()
        elif response.status_code == 429:  # Rate limit
            raise RateLimitException()
        raise requests.RequestException()  # API down
    except requests.RequestException:
        logging.exception("Failed to fetch API")
        raise
