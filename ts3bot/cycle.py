import datetime
import logging
import typing

import requests
import ts3
from sqlalchemy import and_, func
from sqlalchemy.orm import Session, load_only

import ts3bot
from ts3bot.bot import Bot
from ts3bot.database import models


class Cycle:
    def __init__(self, session: Session):
        self.bot = Bot(session, is_cycle=True)
        self.session = session

    def revoke(self, account: typing.Optional[models.Account], cldbid: str):
        if account:
            account.invalidate(self.session)

        changes = ts3bot.sync_groups(
            self.bot, cldbid, account, remove_all=True, skip_whitelisted=True
        )
        if len(changes["removed"]) > 0:
            logging.info(
                "Revoked user's (cldbid:%s) groups (%s).", cldbid, changes["removed"]
            )
        else:
            logging.debug("Removed no groups from user (cldbid:%s).", cldbid)

    def fix_user_guilds(self):
        """
        Removes duplicate selected guilds from users.
        No need to force-sync the user as that's done on join and in the
        following verification function.
        """

        duplicate_guilds = (
            self.session.query(models.LinkAccountGuild)
            .filter(models.LinkAccountGuild.is_active.is_(True))
            .group_by(models.LinkAccountGuild.account_id)
            .having(func.count(models.LinkAccountGuild.guild_id) > 1)
        )
        for row in duplicate_guilds:
            logging.warning(f"{row.account} has multiple guilds.")

            # Delete duplicates
            self.session.query(models.LinkAccountGuild).filter(
                models.LinkAccountGuild.id
                != (
                    self.session.query(models.LinkAccountGuild)
                    .filter(models.LinkAccountGuild.account_id == row.account_id)
                    .filter(models.LinkAccountGuild.is_active.is_(True))
                    .order_by(models.LinkAccountGuild.id.desc())
                    .options(load_only(models.LinkAccountGuild.id))
                    .limit(1)
                    .subquery()
                )
            ).delete(synchronize_session="fetch")

    def run(self):
        self.fix_user_guilds()
        self.verify_accounts()

        # Clean up "empty" guilds
        models.Guild.cleanup(self.session)

    def verify_accounts(self):
        """
        Removes users from known groups if no account is known or the account is invalid
        """
        # Retrieve users
        users = self.bot.exec_("clientdblist", duration=200)
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
                    self.bot.ts3c.send_keepalive()

                # Get user's account
                account = models.Account.get_by_guid(self.session, uid)

                if not account:
                    self.revoke(None, cldbid)
                else:
                    # User was checked, don't check again
                    if (datetime.datetime.today() - account.last_check).days < 2:
                        continue

                    logging.info("Checking %s/%s", account, uid)

                    try:
                        account.update(self.session)
                        # Sync groups
                        ts3bot.sync_groups(self.bot, cldbid, account)
                    except ts3bot.InvalidKeyException:
                        self.revoke(account, cldbid)
                    except requests.RequestException:
                        logging.exception("Error during API call")
                        raise

            # Skip to next user block
            start += len(users)
            try:
                users = self.bot.exec_("clientdblist", start=start, duration=200)
            except ts3.query.TS3QueryError as e:
                # Fetching users failed, most likely at end
                if e.args[0].error["id"] != "1281":
                    logging.exception("Error retrieving user list")
                users = []

        # Update all other accounts
        accounts = self.session.query(models.Account).filter(
            and_(
                models.Account.last_check
                <= datetime.datetime.today() - datetime.timedelta(days=2),
                models.Account.is_valid.is_(True),
            )
        )

        num_accounts = accounts.count()

        for idx, account in enumerate(accounts):
            if idx % 100 == 0 or idx - 1 == num_accounts:
                logging.info("%s/%s: Checking %s", idx + 1, num_accounts, account.name)

            try:
                account.update(self.session)
            except ts3bot.InvalidKeyException:
                pass
            except requests.RequestException:
                logging.exception("Error during API call")
                raise
