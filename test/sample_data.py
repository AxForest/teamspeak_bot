# region test_api_key
# API keys
API_KEY_VALID = (
    "00000000-0000-0000-0000-00000000000000000000-0000-0000-0000-000000000000"
)
API_KEY_VALID_OTHER = (
    "00000000-0000-0000-0000-00000000000000000000-0000-0000-0000-000000000001"
)
API_KEY_DUPLICATE = (
    "DUPLICAT-E000-0000-0000-00000000000000000000-0000-0000-0000-000000000000"
)
API_KEY_INVALID = (
    "INVALID0-0000-0000-0000-00000000000000000000-0000-0000-0000-000000000000"
)
API_KEY_INVALID_WORLD = (
    "INVALID0-WORL-D000-0000-00000000000000000000-0000-0000-0000-000000000000"
)
API_KEY_INVALID_RESPONSE = (
    "INVALID0-RESP-ONSE-0000-00000000000000000000-0000-0000-0000-000000000000"
)

# Account data
ACCOUNT = """
{
  "id": "ABCDEFGH-1234-1234-1234-ABCDEFGHIJKL",
  "name": "User.1234",
  "age": 25717980,
  "world": 2201,
  "guilds": ["4BBB52AA-D768-4FC6-8EDE-C299F2822F0F"],
  "guild_leader": [],
  "created": "2012-01-01T12:45:00Z",
  "access": ["GuildWars2","HeartOfThorns","PathOfFire"],
  "commander": true,
  "fractal_level": 100,
  "daily_ap": 9432,
  "monthly_ap": 553,
  "wvw_rank": 2021
}"""
ARENANET_GUILD = """
{
  "id": "4BBB52AA-D768-4FC6-8EDE-C299F2822F0F",
  "name": "ArenaNet",
  "tag": "ArenaNet",
  "emblem": {
    "background": {
      "id": 2,
      "colors": [
        473
      ]
    },
    "foreground": {
      "id": 40,
      "colors": [
        673,
        71
      ]
    },
    "flags": [
      "FlipBackgroundHorizontal",
      "FlipBackgroundVertical"
    ]
  }
}"""

ACCOUNT_INVALID_WORLD = ACCOUNT.replace('d": 2201', 'd": 1001')
ACCOUNT_INVALID = '{"text": "Invalid access token"}'
ACCOUNT_OTHER = ACCOUNT.replace(
    "ABCDEFGH-1234-1234-1234-ABCDEFGHIJKL", "ZBCDEFGH-1234-1234-1234-ABCDEFGHIJKL"
).replace("User.1234", "User.4321")
# endregion
