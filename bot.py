#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging.handlers
import re
import sys
import traceback
from pathlib import Path

import mysql.connector as msql
import requests
import ts3

from common import fetch_account
from config import *


def send_message(recipient: str, msg: str):
    try:
        ts3c.exec_('sendtextmessage', targetmode=1, target=recipient, msg=msg)
    except ts3.query.TS3Error:
        logger.error('Seems like the user I tried to message vanished into thin air')
        logger.error(traceback.format_exc())


def handle_event():
    if event.event == 'notifyclientmoved':
        if event[0]['ctid'] == str(CHANNEL_ID):
            logger.info('User id:{} joined channel'.format(event[0]['clid']))
            send_message(event[0]['clid'], 'Willkommen bei der automatischen Registrierung auf dem Kodash-TS. Bitte '
                                           'schicken Sie mir Ihren API-Key, welchen Sie hier generieren können: < ['
                                           'url=https://account.arena.net/applications]ArenaNet[/url] >')
        else:
            logger.info('User id:{} left channel'.format(event[0]['clid']))
    elif event.event == 'notifytextmessage':
        message = event[0]['msg'].strip()
        logger.info('{} ({}): {}'.format(event[0]['invokername'], event[0]['invokeruid'], message))

        match = re.match('!ignore +([A-Z0-9\-]+)', message)
        if match and event[0]['invokeruid'] in COMMAND_WHITELIST:
            msqlc = None
            cur = None
            try:
                json = fetch_account(match.group(1))
                if not json:
                    send_message(event[0]['invokerid'], 'Ungültiger API-Key.')
                    return
                msqlc = msql.connect(user=SQL_USER, password=SQL_PASS, host=SQL_HOST, port=SQL_PORT,
                                     database=SQL_DB)
                cur = msqlc.cursor()

                # Grab distinct TS unique IDs
                cur.execute('SELECT DISTINCT `tsuid` FROM `users` '
                            'WHERE `ignored` = FALSE AND (`apikey` = %s OR `name` = %s)',
                            (match.group(1), json.get('name')))
                results = cur.fetchall()
                server_groups = [x['group_id'] for x in SERVERS]
                for result in results:
                    try:
                        cldbid = ts3c.exec_('clientgetdbidfromuid', cluid=result[0])[0]['cldbid']
                        for server_group in server_groups:
                            try:
                                ts3c.exec_('servergroupdelclient', sgid=server_group, cldbid=cldbid)
                                logger.info(
                                    'Removed user dbid:{} ({}) from group {}'.format(cldbid, result[0], server_group))
                            except ts3.TS3Error:
                                # User most likely doesn't have the group
                                pass
                    except ts3.TS3Error:
                        # User might not exist in the db, whatever
                        pass

                cur.execute('UPDATE `users` SET `ignored` = TRUE '
                            'WHERE `ignored` = FALSE AND (`apikey` = %s OR `name` = %s)',
                            (match.group(1), json.get('name')))
                msqlc.commit()
                logger.info('{} ({}) marked previous instances of {} as ignored'.format(event[0]['invokername'],
                                                                                        event[0]['invokeruid'],
                                                                                        match.group(1)))
                send_message(event[0]['invokerid'],
                             'Done! Rechte von {} vorherigen Nutzern entzogen.'.format(len(results)))
            except msql.Error as err:
                logger.error('Failed to mark api key {} as ignored'.format(match.group(1)))
                logger.error(traceback.print_exc())
                raise err
            finally:
                if cur:
                    cur.close()
                if msqlc:
                    msqlc.close()
            return

        # Check with ArenaNet's API
        try:
            json = fetch_account(message)
            if not json:
                send_message(event[0]['invokerid'],
                             msg='Sie haben eine ungültige Eingabe getätigt. Bitte versuchen Sie es erneut.')
                return
            world = json.get('world')

            # Grab server info from config
            server = None
            for s in SERVERS:
                if s['id'] == world:
                    server = s
                    break

            # World is in config
            if server:
                msqlc = None
                cur = None
                try:
                    msqlc = msql.connect(user=SQL_USER, password=SQL_PASS, host=SQL_HOST, port=SQL_PORT,
                                         database=SQL_DB)
                    cur = msqlc.cursor()

                    # Check if API key/account was user previously by another uid
                    cur.execute('SELECT COUNT(`id`), `name` FROM `users` WHERE `tsuid` != %s AND '
                                ' (`apikey` = %s OR `name` = %s) AND `ignored` is FALSE',
                                (event[0]['invokeruid'], message, json.get('name')))
                    result = cur.fetchone()
                    if result[0] > 0:
                        logger.warning(
                            'User {} ({}) tried to use an already registered API key/account. ({})'.format(
                                event[0]['invokername'], event[0]['invokeruid'], result[1]))
                        send_message(event[0]['invokerid'],
                                     'Dieser API-Key/Account ist bereits auf einen anderen Nutzer registiert. '
                                     'Bitte kontaktieren Sie einen Admin.')
                        return

                    # Save API key and user info in database
                    cur.execute(
                        'INSERT INTO `users` (`name`, `world`, `apikey`, `tsuid`) VALUES (%s, %s, %s, %s)',
                        (json.get('name'), world, message, event[0]['invokeruid']))
                    msqlc.commit()

                    # Assign configured role
                    cldbid = ts3c.exec_('clientgetdbidfromuid', cluid=event[0]['invokeruid'])[0]['cldbid']
                    ts3c.exec_('servergroupaddclient', sgid=server['group_id'], cldbid=cldbid)
                    logger.info('Assigned world {} to {} ({})'.format(server['name'], event[0]['invokername'],
                                                                      event[0]['invokeruid']))
                except (ts3.TS3Error, msql.Error) as err:
                    if isinstance(err, ts3.query.TS3QueryError) and err.args[0].error['id'] == '2561':
                        logger.info(
                            'User {} ({}) registered a second time for whatever reason'.format(event[0]['invokername'],
                                                                                               event[0]['invokeruid']))
                        send_message(event[0]['invokerid'], 'Sie haben bereits die passende Servergruppe!')
                    else:
                        logger.error('Failed to assign server group to user uid:{}'.format(event[0]['invokeruid']))
                        logger.error(traceback.format_exc())
                        send_message(event[0]['invokerid'],
                                     'Fehler beim Speichern des API-Keys. Bitte kontaktieren Sie einen Admin.')
                finally:
                    if cur:
                        cur.close()
                    if msqlc:
                        msqlc.close()
            else:  # Invalid world on API
                logger.warning(
                    'User {} ({}) is currently on world {} and tried to register.'.format(event[0]['invokername'],
                                                                                          event[0]['invokeruid'],
                                                                                          world))
                send_message(event[0]['invokerid'],
                             'Sie haben eine andere Welt gewählt. Falls sie vor kurzer Zeit '
                             'ihre Heimatwelt gewechselt haben, versuchen Sie es in 24 Stunden '
                             'erneut. Spion!')
        except requests.RequestException:  # API seems to be down
            send_message(event[0]['invokerid'],
                         'Die API von Guild Wars 2 scheint derzeit offline zu sein. Bitte versuchen Sie es später '
                         'erneut oder wenden Sie sich an einen Admin')


if __name__ == '__main__':
    if not Path('logs').exists():
        Path('logs').mkdir()

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    hldr = logging.handlers.TimedRotatingFileHandler('logs/bot.log', when='W0', encoding='utf-8', backupCount=16)
    fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S")
    hldr.setFormatter(fmt)
    logger.addHandler(hldr)
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    stream.setLevel(logging.DEBUG)
    logger.addHandler(stream)

    with ts3.query.TS3ServerConnection(
            '{}://{}:{}@{}'.format(TS3_PROTOCOL, CLIENT_USER, CLIENT_PASS, QUERY_HOST)) as ts3c:
        ts3c.exec_('use', sid=SERVER_ID)
        ts3c.exec_('clientupdate', client_nickname=CLIENT_NICK)

        # Subscribe to events
        ts3c.exec_('servernotifyregister', event='channel', id=CHANNEL_ID)
        ts3c.exec_('servernotifyregister', event='textprivate')

        # Move to target channel
        own_id = ts3c.exec_('clientfind', pattern=CLIENT_NICK)[0]['clid']
        ts3c.exec_('clientmove', clid=own_id, cid=CHANNEL_ID)

        while True:
            ts3c.send_keepalive()
            try:
                event = ts3c.wait_for_event(timeout=60)
                # type: ts3.response.TS3Event
            except ts3.query.TS3TimeoutError:
                pass  # Ignore wait timeout
            else:
                # Ignore own events
                if 'invokername' in event[0] and event[0]['invokername'] == CLIENT_NICK \
                        or 'clid' in event[0] and event[0]['clid'] == own_id:
                    continue

                handle_event()
