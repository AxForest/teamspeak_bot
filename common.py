import logging
import traceback

import requests


def fetch_account(key: str):
    try:
        response = requests.get('https://api.guildwars2.com/v2/account?access_token=' + key)
        if 200 < response.status_code < 500:  # Invalid API key
            return None
        elif response.status_code >= 500:
            raise requests.RequestException()  # Probably gateway timeout, API down
        return response.json()
    except requests.RequestException as e:
        logging.error(traceback.format_exc())
        logging.warning('Failed to fetch API')
        raise e
