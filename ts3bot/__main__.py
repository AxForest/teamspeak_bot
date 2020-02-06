from ts3bot import common
from ts3bot.config import Config

if __name__ == "__main__":
    Config.load()
    common.init_logger("bot")
    Bot().loop()
