import logging
import typing

from requests import RequestException

from ts3bot import (
    InvalidKeyException,
    RateLimitException,
    events,
    fetch_api,
    sync_groups,
)
from ts3bot.bot import Bot
from ts3bot.database import enums, models

MESSAGE_REGEX = "\\s*(\\w{8}(-\\w{4}){3}-\\w{20}(-\\w{4}){3}-\\w{12})\\s*"
USAGE = "<API KEY>"


def handle(bot: Bot, event: events.TextMessage, match: typing.Match):
    key = match.group(1)

    # Check with ArenaNet's API
    try:
        account_info = fetch_api("account", api_key=key)

        # Grab server info from database
        server_group: typing.Optional[models.WorldGroup] = (
            bot.session.query(models.WorldGroup)
            .filter(models.WorldGroup.world == enums.World(account_info.get("world")))
            .one_or_none()
        )

        # World is linked to a group
        if server_group:
            account: models.Account = models.Account.get_or_create(
                bot.session, account_info, key
            )
            identity: models.Identity = models.Identity.get_or_create(
                bot.session, event.uid
            )

            # Check if account is registered to anyone
            linked_identity: typing.Optional[
                models.LinkAccountIdentity
            ] = account.valid_identities.one_or_none()

            # Account is already linked
            if linked_identity:
                # Account is linked to another guid
                if linked_identity.identity.guid != event.uid:
                    logging.warning(
                        "{} ({}) tried to use an already registered API key/account. ({})".format(
                            event.name, event.uid, account_info.get("name"),
                        )
                    )
                    bot.send_message(event.id, "token_in_use")
                else:  # Account is linked to current guid
                    logging.info(
                        "User {} ({}) tried to register a second time for whatever reason using {}".format(
                            event.name,
                            event.uid,
                            account_info.get("name", "Unknown account"),
                        )
                    )

                    # Save new API key
                    if account.api_key != key:
                        account.api_key = key
                        account.is_valid = True
                        bot.session.commit()

                    bot.send_message(event.id, "registration_exists")
            else:
                # Otherwise account is not yet linked and can be used

                # Save API key
                account.api_key = key
                account.is_valid = True
                bot.session.commit()

                # Get user's DB id
                cldbid = bot.exec_("clientgetdbidfromuid", cluid=event.uid)[0]["cldbid"]

                # Unlink previous account from identity
                current_account = models.Account.get_by_guid(bot.session, event.uid)
                if current_account:
                    logging.info("Delinking %s from cldbid:%s", current_account, cldbid)
                    current_account.invalidate(bot.session)

                # Register link between models
                bot.session.add(
                    models.LinkAccountIdentity(account=account, identity=identity)
                )
                bot.session.commit()

                # Sync groups
                sync_groups(bot, cldbid, account)

                logging.info(
                    "Assigned world %s to %s (%s) using %s",
                    server_group.world.name,
                    event.name,
                    event.uid,
                    account_info.get("name", "Unknown account"),
                )

                # Was registered with other account previously
                if current_account:
                    bot.send_message(
                        event.id, "registration_update", account=account.name,
                    )
                else:
                    bot.send_message(event.id, "welcome_registered")
                    bot.send_message(event.id, "welcome_registered_2")
        else:
            bot.send_message(
                event.id,
                "invalid_world",
                world=enums.World(account_info.get("world")).proper_name,
            )

    except InvalidKeyException:
        logging.info("This seems to be an invalid API key.")
        bot.send_message(event.id, "invalid_token_retry")
    except (RateLimitException, RequestException):
        bot.send_message(event.id, "error_api")
