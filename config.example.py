# List of server's ids, names and the related TS3 group id
SERVERS = [
    {"id": 2201, "name": "Kodash", "group_id": "156"},
    {"id": 2206, "name": "Millersund", "group_id": "158"},
]

# The API bot's default TS3 channel
CHANNEL_ID = 565

# TS3 virtual server
SERVER_ID = 2

# Login data
CLIENT_NICK = "API-Bot"
CLIENT_USER = "API-Bot"
CLIENT_PASS = "abc"

# Login data for cycle.py
CYCLE_USER = "Bicycle"
CYCLE_PASS = "abc"

# TS3 connection details
QUERY_HOST = "localhost:10011"
TS3_PROTOCOL = "telnet"

# MySQL server
SQL_HOST = "localhost"
SQL_PORT = 3306
SQL_USER = "root"
SQL_PASS = "root"
SQL_DB = "ts"

# Which channel to render the current reset sheet on
SHEET_CHANNEL_ID = 634

WHITELIST = {
    # List of admins/mods, can use !help/!ignore etc
    "ADMIN": ["V2h5IGhlbGxvIHRoZXJlIQ==", "R28gc2V0IHlvdXIgYWRtaW4gdWlkcyBoZXJl"],
    # TS3 groups that can list group members
    "GROUP_LIST": ["Gilden-Admin"],
    # TS3 groups that won't be removed by cycle
    "CYCLE": ["Server-Admin"],
}

# List of registered guilds
GUILDS = {
    # "Guild GUID": ["tag": ts_id]
    "A09E65A6-F378-E511-AEFB-AC162DC05865": ["Kdsh", 11]
}

# Legacy group for users without a registered key
LEGACY_ANNOYANCE_GROUP = "13"
ASSIGN_LEGACY = False

# URL for sentry's error reports
SENTRY_DSN = None
