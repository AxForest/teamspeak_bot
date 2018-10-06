#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging
import sqlite3
import traceback

import requests
import ts3

from config import *


def handle_event():
    if event.event == 'notifyclientmoved':
        if event[0]['ctid'] == str(CHANNEL_ID):
            logger.info('User id:{} joined channel'.format(event[0]['clid']))
            try:
                ts3c.exec_('sendtextmessage', targetmode=1, target=event[0]['clid'],
                           msg='Willkommen bei der automatischen Registrierung auf dem Kodash-TS. Bitte '
                               'schicken Sie mir Ihren API-Key, welchen Sie hier generieren können: < ['
                               'url=https://account.arena.net/applications]ArenaNet[/url] >')
            except ts3.query.TS3Error:
                logging.error('Seems like the user vanished into thin air')
                logging.error(traceback.format_exc())
        else:
            logger.info('User id:{} left channel'.format(event[0]['clid']))
    elif event.event == 'notifytextmessage':
        message = event[0]['msg'].strip()
        logger.info('{}: {}'.format(event[0]['invokername'], message))

        # Check with ArenaNet's API
        try:
            response = requests.get('https://api.guildwars2.com/v2/account?access_token=' + message)
            if response.status_code == 403:  # Invalid API key
                ts3c.exec_('sendtextmessage', targetmode=1, target=event[0]['invokerid'],
                           msg='Sie haben eine ungültige Eingabe getätigt. Bitte versuchen Sie es erneut.')

            json = response.json()
            world = json.get('world')

            # Grab server info from config
            server = None
            for s in SERVERS:
                if s['id'] == world:
                    server = s
                    break

            # World is in config
            if server:
                try:
                    sqlc = sqlite3.connect('ts.db')
                    cur = sqlc.cursor()

                    # Check if API key/account was user previously by another uid
                    cur.execute('SELECT count(id), name FROM users WHERE tsid != ? AND (apikey = ? OR name = ?)',
                                (message, event[0]['invokeruid'], json.get('name')))
                    result = cur.fetchone()
                    if result[0] > 0:
                        logging.warning(
                            'User {} ({}) tried to use an already registered API key/account. ({})'.format(
                                event[0]['invokername'],
                                event[0]['invokeruid'],
                                result[1]))
                        ts3c.exec_('sendtextmessage', targetmode=1, target=event.parsed[0]['invokerid'],
                                   msg='Dieser API-Key/Account ist bereits auf einen anderen Nutzer registiert. '
                                       'Bitte kontaktieren Sie einen Admin.')
                        return

                    # Save API key and user info in database
                    cur.execute(
                        'INSERT INTO users (name, world, apikey, tsid, timestamp) '
                        'VALUES (?, ?, ?, ?, datetime(\'now\'))',
                        (json.get('name'), world, message, event[0]['invokeruid']))
                    sqlc.commit()
                    cur.close()
                    sqlc.close()

                    # Assign configured role
                    cldbid = ts3c.query('clientgetdbidfromuid', cluid=event[0]['invokeruid']).fetch()[0]['cldbid']
                    ts3c.exec_('servergroupaddclient', sgid=server['group_id'], cldbid=cldbid)
                    logging.info('Assigned world {} to {} ({})'.format(server['name'], event[0]['invokername'],
                                                                       event[0]['invokeruid']))
                except ts3.TS3Error and sqlite3.Error:
                    logging.error('Failed to assign server group to user uid:{}'.format(event[0]['invokeruid']))
                    logging.error(traceback.format_exc())
                return
            else:  # Invalid world on API
                logging.warning(
                    'User {} ({}) is currently on world {} and tried to register.'.format(event[0]['invokername'],
                                                                                          event[0]['invokeruid'],
                                                                                          world))
                ts3c.exec_('sendtextmessage', targetmode=1, target=event.parsed[0]['invokerid'],
                           msg='Sie haben eine andere Welt gewählt. Falls sie vor kurzer Zeit '
                               'ihre Heimatwelt gewechselt haben, versuchen Sie es in 24 Stunden '
                               'erneut. Spion!')
        except requests.RequestException:  # API seems to be down
            ts3c.exec_('sendtextmessage', targetmode=1, target=event[0]['invokerid'],
                       msg='Die API von Guild Wars 2 scheint derzeit offline zu sein. Bitte versuchen Sie es später '
                           'erneut oder wenden Sie sich an einen Admin')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger()

    with ts3.query.TS3ServerConnection(
            '{}://{}:{}@{}'.format(TS3_PROTOCOL, CLIENT_USER, CLIENT_PASS, QUERY_HOST)) as ts3c:
        ts3c.exec_('use', sid=SERVER_ID)
        ts3c.exec_('clientupdate', client_nickname=CLIENT_NICK)

        # Subscribe to events
        ts3c.exec_('servernotifyregister', event='channel', id=CHANNEL_ID)
        ts3c.exec_('servernotifyregister', event='textprivate')

        # Move to target channel
        own_id = ts3c.query('clientfind', pattern=CLIENT_NICK).fetch()[0]['clid']
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
