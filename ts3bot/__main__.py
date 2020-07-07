import argparse
import typing

from sqlalchemy.orm import Session

from ts3bot import init_logger, legacy
from ts3bot.bot import Bot
from ts3bot.config import Config
from ts3bot.cycle import Cycle
from ts3bot.database import create_session

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
    sub_cycle.add_argument(
        "--world",
        help="Verify world (id)",
        type=int,
    )
    sub_migrate = sub.add_parser(
        "migrate",
        help="Migrates the old database (<2020) to the current version. Uses cycle account",
    )
    sub_migrate.add_argument(
        "source_database",
        help="Use a URI of the following schema: mysql+mysqldb://"
        "<user>:<password>@<host>[:<port>]/<dbname>. "
        "Requires sqlalchemy[mysql]",
    )
    sub.add_parser("bot", help="Runs the main bot")

    args = parser.parse_args()

    session: typing.Optional[Session] = None
    if args.mode in ["bot", "cycle", "migrate"]:
        session = create_session(Config.get("database", "uri"))

    if args.mode == "bot":
        init_logger("bot")
        Bot(session).loop()
    elif args.mode == "cycle":
        init_logger("cycle")
        Cycle(session, verify_all=args.all, verify_linked_worlds=args.relink, verify_ts3=args.ts3, verify_world=args.world).run()
    elif args.mode == "migrate":
        init_logger("migrate")
        legacy.apply_generic_groups(session)
        legacy.migrate_database(session, args.source_database)
    else:
        parser.print_help()

# TODO: !help: Respond with appropriate commands
# TODO: Wrapper for servergroupaddclient/servergroupdelclient
# TODO: API timeout, async rewrite
