import argparse

from ts3bot.bot import Bot
from ts3bot.config import Config
from ts3bot.cycle import Cycle
from ts3bot.database import create_session
from ts3bot.utils import init_logger

if __name__ == "__main__":
    Config.load()

    parser = argparse.ArgumentParser("ts3bot")
    sub = parser.add_subparsers(dest="mode")
    sub_cycle = sub.add_parser("cycle", help="Verifies/updates all known accounts")
    sub_cycle.add_argument(
        "--all",
        help="Verifies everyone irregardless of cycle_hours in config",
        action="store_true",
    )
    sub_cycle.add_argument(
        "--relink",
        help="Only verifies everyone on a world marked as is_linked, ignores cycle_hours",
        action="store_true",
    )
    sub_cycle.add_argument(
        "--ts3",
        help="Verify everyone known to the TS3 server, this is the default",
        action="store_true",
    )
    sub_cycle.add_argument("--world", help="Verify world (id)", type=int)
    sub.add_parser("bot", help="Runs the main bot")

    args = parser.parse_args()

    if args.mode == "bot":
        init_logger("bot")
        Bot(create_session(Config.get("database", "uri"))).loop()
    elif args.mode == "cycle":
        init_logger("cycle")
        Cycle(
            create_session(Config.get("database", "uri")),
            verify_all=args.all,
            verify_linked_worlds=args.relink,
            verify_ts3=args.ts3,
            verify_world=args.world,
        ).run()
    else:
        parser.print_help()

# TODO: !help: Respond with appropriate commands
# TODO: Wrapper for servergroupaddclient/servergroupdelclient
# TODO: API timeout, async rewrite
