from ts3bot import Bot, common

if __name__ == "__main__":
    common.init_logger("bot")
    Bot().loop()
