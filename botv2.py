!/usr/bin/python3
id: 127 kodash
# import requests
# import ts3
# import sqlite3

# def my_event_handler(sender, event):
    # print(event.event)
    # if event.event == "notifyclientmoved":
        # if event.parsed[0]["ctid"] == "2228":
            # try:
                # ts3conn.sendtextmessage(targetmode=1, target=event.parsed[0]["clid"],
                                        # msg="Willkommen bei der automatischen Registrierung auf dem Kodash TS. Bitte "
                                            # "schicken Sie mir ihren API-Key, welchen Sie hier generieren können < ["
                                            # "url=https://account.arena.net/applications]ArenaNet[/url] >")
            # except ts3.query.TS3QueryError as err:
                # print(" Error:", err)
        # return None
    # elif event.event == "notifytextmessage":
        # if 'invokeruid' in event.parsed[0].keys():
            # if event.parsed[0]["invokeruid"] != "sMA75rC+zosl7S/eG9pKik1bt34=":
               # apikey = event.parsed[0]["msg"].strip()
               # invokeruid = event.parsed[0]["invokeruid"].strip()
               # invokerid = event.parsed[0]["invokerid"].strip()
               # r = requests.get('https://api.guildwars2.com/v2/account?access_token=' + apikey)
              conn = sqlite3.connect('test')
		name = r.json().get("name")
              c = conn.cursor();
		c.execute("SELECT id, name, world FROM tbl WHERE name =?",name)
		row = c.fetchone()
		world = row[2]
               # if r.json().get("world"):
                    # if r.json()["world"] == 2201:
                        # ts3conn.sendtextmessage(targetmode=1, target=invokerid,
                                                # msg="Sie haben die Welt 'Kodash' gewählt. Genießen Sie ihren Besuch "
                                                    # "und ihre neu erworbenen Privilegien. Nachdem sie sich erneut "
                                                    # "verbunden haben, können sie auch in die Channel schauen. "
                                                    # "Akutelle Builds gibt es [Url=www.kdshbuilds.de]hier[/url]")
                        # conn = sqlite3.connect('ts.db')
                        # c = conn.cursor()
                        # c.execute("INSERT INTO users (name, world, apikey, tsid, timestamp) values (?,?,?,?,datetime('now'))",(r.json().get("name"),r.json().get("world"),apikey,invokeruid))
                        # conn.commit()
                        # c.close()
                        # conn.close()
                        # id = ts3conn.clientgetdbidfromuid(cluid=event.parsed[0]["invokeruid"])
                        # print(id.parsed)
                        # try:
                            # ts3conn.servergroupaddclient(sgid=127, cldbid=id[0]['cldbid'])
                        # except:
                            # print("error")
                    # else:
                        # ts3conn.sendtextmessage(targetmode=1, target=event.parsed[0]["invokerid"],
                                                # msg="Sie haben eine andere Welt gewählt. Falls sie vor kurzer Zeit "
                                                    # "ihre Heimatwelt gewechselt haben versuchen Sie es in 24Stunden "
                                                    # "erneut. Spion!")
               # else:
                    # ts3conn.sendtextmessage(targetmode=1, target=event.parsed[0]["invokerid"],
                                            # msg="Sie haben eine fehlerhafte Eingabe getätigt. Bitte versuchen Sie es "
                                                # "erneut.")
    # print("Parsed", event.parsed)
    # return None


# with ts3.query.TS3Connection("youriphere") as ts3conn:
    # ts3conn.login(
        # client_login_name="API-Bot",
        # client_login_password="clientpwhere"
    # )
    # ts3conn.use(sid=1)
    # ts3conn.clientupdate(client_nickname='API-Bot1')
    Connect the signal. This is a **blinker.Signal** instance, shared
    by all TS3Connections.
    # ts3conn.on_event.connect(my_event_handler)
    If you only want to connect the handler to a specifc ts3
    connection, use:
    ts3conn.on_event.connect(my_event_handler, sender=ts3conn)

    Register for events
    # ts3conn.servernotifyregister(event="channel", id_="2228")
    # ts3conn.servernotifyregister(event="textprivate")
    Start the recv loop to catch all events.
    # ts3conn.recv_in_thread()
    Note, that you can still use the ts3conn to send queries:
    # ts3conn.clientlist()
    # ts3conn.keepalive()
    The recv thread can be stopped with:
    >>> ts3conn.stop_recv()
    Note, that the thread will be stopped automatically when the
    client disconnects.

    Block to avoid leaving the *with* statement and therefore closing
    the connection.
# input("> Hit enter to finish.")
