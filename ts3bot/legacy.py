import json
import logging
import time
import typing

import ts3
from sqlalchemy import and_, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, load_only, sessionmaker

import ts3bot
from ts3bot import Config
from ts3bot.bot import Bot
from ts3bot.database import enums
from ts3bot.database.models import (
    Account,
    Guild,
    Identity,
    LinkAccountGuild,
    LinkAccountIdentity,
    WorldGroup,
)

# region Monkey patch fetch_api
real_fetch = ts3bot.fetch_api


def limit_fetch_api(endpoint: str, api_key: typing.Optional[str] = None):
    while True:
        try:
            return real_fetch(endpoint, api_key)
        except ts3bot.RateLimitException:
            logging.warning("Got rate-limited, waiting 1 minute.")
            time.sleep(60)
            return real_fetch(endpoint, api_key)


ts3bot.fetch_api = limit_fetch_api


# endregion


def update_accounts(session: Session):
    logging.info("--- Verifying all known accounts ---")
    accounts = session.query(Account).all()
    num_accounts = session.query(Account).count()

    # Verify accounts and update guild links
    for idx, account in enumerate(accounts):
        logging.info("%s/%s: Updating %s", idx + 1, num_accounts, account.name)
        account.update(session)

    logging.info("--- Verification complete ---")


def fetch_identity_guilds(session: Session):
    logging.info("--- Migrating user's current guild ---")

    valid_guilds = session.query(Guild).filter(Guild.group_id.isnot(None)).all()
    guild_mapper = {}
    for guild in valid_guilds:
        guild_mapper[guild.group_id] = guild

    # Create TS3 bot
    bot = Bot(session, is_cycle=True)

    num_identities = session.query(Identity).count()

    # Fetch identity's guild
    for idx, identity in enumerate(session.query(Identity).all()):
        logging.info("%s/%s: Checking %s", idx + 1, num_identities, identity)

        try:
            cldbid = bot.exec_("clientgetdbidfromuid", cluid=identity.guid)[0]["cldbid"]
            server_groups = bot.exec_("servergroupsbyclientid", cldbid=cldbid)

            guild = None
            # Find known guild
            for server_group in server_groups:
                if int(server_group["sgid"]) in guild_mapper:
                    guild = guild_mapper[int(server_group["sgid"])]

            # User has no valid guild
            if guild is None:
                continue

            account = Account.get_by_guid(session, identity.guid)

            if not account:
                logging.warning(
                    "%s/%s: %s is not linked to any account",
                    idx + 1,
                    num_identities,
                    identity,
                )
                continue

            logging.info(
                "%s/%s: Linking %s to %s", idx + 1, num_identities, identity, guild
            )

            # Unlink all current
            session.query(LinkAccountGuild).filter(
                LinkAccountGuild.account_id == account.id
            ).update({"is_active": False})

            # Link correct guild
            session.query(LinkAccountGuild).filter(
                and_(
                    LinkAccountGuild.guild_id == guild.id,
                    LinkAccountGuild.account_id == account.id,
                )
            ).update({"is_active": True})

            session.commit()

        except ts3.TS3Error as e:
            if e.args[0].error["id"] == "512":
                logging.info("%s does not exist on server, deleting.", identity)
                session.query(LinkAccountIdentity).filter(
                    LinkAccountIdentity.identity == identity
                ).delete()
                session.delete(identity)
                session.commit()
            else:
                logging.info("Failed to link %s", identity, exc_info=True)

    logging.info("--- Migrating current guilds done ---")


def migrate_known_guilds(session: Session):
    logging.info("--- Migrating known guilds from config.py ---")
    try:
        from config import GUILDS

        num_guilds = len(GUILDS)
        for idx, (guild_id, info) in enumerate(GUILDS.items()):
            logging.info("%s/%s: Creating %s", idx + 1, num_guilds, info[0])
            Guild.get_or_create(session, guild_id, group_id=info[1])

        logging.info("--- Migrating complete, config.py can be deleted now ---")
    except:
        logging.exception("Failed to migrate known guilds.")


def migrate_database(session: Session, source_database: str):
    engine = create_engine(source_database, echo=False)
    source_session: Session = sessionmaker(bind=engine)()

    # Verify login for source database is valid
    try:
        source_session.execute("SELECT VERSION();")
    except OperationalError:
        logging.warning("Failed to connect to source database.")
        raise

    # Check if target DB is empty
    if session.query(Account).count() > 0 or session.query(Identity).count() > 0:
        raise Exception("Target database is not empty!")

    logging.info("--- Migrating database ---")

    known_identities = []
    num_accounts = 0
    rows = source_session.execute(
        """
        SELECT
            `name`,
            `world`,
            SUBSTRING_INDEX( GROUP_CONCAT( DISTINCT `apikey` ORDER BY `timestamp` DESC SEPARATOR ',' ), ',', 1 ),
            `tsuid`,
            `timestamp`,
            `last_check`,
            `guilds`
        FROM
            `users` 
        WHERE
            `ignored` = FALSE 
        GROUP BY
            `name`
        """
    )
    for idx, row in enumerate(rows):
        logging.info("%s: Copying %s", idx + 1, row[0])

        if row[3] in known_identities:
            identity = session.query(Identity).filter_by(guid=row[3]).one_or_none()
        else:
            identity = Identity(guid=row[3], created_at=row[4])
            known_identities.append(row[3])

        account = Account(
            name=row[0],
            world=enums.World(row[1]),
            api_key=row[2],
            last_check=row[5],
            created_at=row[4],
        )
        num_accounts += 1

        session.add(identity)
        session.add(account)
        session.add(
            LinkAccountIdentity(account=account, identity=identity, created_at=row[4])
        )

        # Create guilds
        _guilds = json.loads(row[6])
        for guild in _guilds:
            Guild.get_or_create(session, guild)

        session.commit()

    # Verify accounts and update guild links
    update_accounts(session)

    # Migrate known guilds
    migrate_known_guilds(session)

    # Associate identity with currently selected guild
    fetch_identity_guilds(session)

    logging.info("--- Migration done ---")


def apply_generic_groups(session: Session):
    """
    Applies generic world/guild groups for users in known groups
    :param session:
    :return:
    """
    logging.info("--- Applying generic permission groups to users ---")
    logging.warning("Updating the permissions is a manual action!")

    guild_groups = {
        _.group_id: _.name
        for _ in session.query(Guild)
        .filter(Guild.group_id.isnot(None))
        .options(load_only(Guild.group_id, Guild.name))
    }
    world_groups = {
        _.group_id: _.world
        for _ in session.query(WorldGroup)
        .filter(WorldGroup.is_linked.is_(True))
        .options(load_only(WorldGroup.group_id, WorldGroup.world))
    }
    generic_world = int(Config.get("teamspeak", "generic_world_id"))
    generic_guild = int(Config.get("teamspeak", "generic_guild_id"))

    # Create TS3 bot
    bot = Bot(session, is_cycle=True)

    users = bot.exec_("clientdblist", duration=200)
    start = 0
    while len(users) > 0:
        for counter, user in enumerate(users):
            uid = user["client_unique_identifier"]
            cldbid = user["cldbid"]

            # Skip SQ account
            if "ServerQuery" in uid:
                continue

            # Send keepalive
            if counter % 100 == 0:
                bot.ts3c.send_keepalive()

            # Get user's groups
            server_groups = bot.exec_("servergroupsbyclientid", cldbid=cldbid)

            has_guild = None
            has_linked_world = None
            groups_exist = False
            for server_group in server_groups:
                sgid = int(server_group["sgid"])
                if sgid in world_groups:
                    has_linked_world = world_groups[sgid]
                elif sgid in guild_groups:
                    has_guild = guild_groups[sgid]
                elif sgid == generic_world or sgid == generic_guild:
                    groups_exist = True
                    break

            # User was already migrated (manually?)
            if groups_exist:
                logging.info("Skipping cldbid:%s, generic groups exist already", cldbid)
                continue

            try:
                if has_guild:
                    logging.info(
                        "Adding cldbid:%s to generic GUILD due to %s", cldbid, has_guild
                    )
                    bot.exec_("servergroupaddclient", sgid=generic_guild, cldbid=cldbid)
                elif has_linked_world:
                    logging.info(
                        "Adding cldbid:%s to generic WORLD due to %s",
                        cldbid,
                        has_linked_world,
                    )
                    bot.exec_("servergroupaddclient", sgid=generic_world, cldbid=cldbid)
            except ts3.TS3Error:
                logging.exception("Failed to add user to generic group")

        # Skip to next user block
        start += len(users)
        try:
            users = bot.exec_("clientdblist", start=start, duration=200)
        except ts3.query.TS3QueryError as e:
            # Fetching users failed, most likely at end
            if e.args[0].error["id"] != "1281":
                logging.exception("Error retrieving user list")
            users = []

    logging.info("--- Done ---")
