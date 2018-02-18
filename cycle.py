import sqlite3

import requests
import ts3

if __name__ == '__main__':
    ts3conn = ts3.query.TS3Connection("youriphere")
    ts3conn.login(
        client_login_name="API-Bot",
        client_login_password="clientpwhere"
    )
    ts3conn.use(sid=1)
    ts3conn.clientupdate(client_nickname='API-Bot1')

    conn = sqlite3.connect('ts.db')
    c = conn.cursor()
    c.execute('SELECT id, apikey, tsid FROM users ORDER BY timestamp ASC')

    user_delete = []

    for row in c:
        r = requests.get('https://api.guildswars2.com/v2/account?access_token={}'.format(row[1]))
        r_json = r.json()
        if not (r_json['world'] and r_json['world'] == 2201):
            cldbid = ts3conn.clientgetdbidfromuid(cluid=row[2])
            ts3conn.servergroupdelclient(sgid=127, cldbid=cldbid)

            user_delete.append(row[0])

    c.execute('DELETE FROM users WHERE id IN ({})'.format(''.join(user_delete)))
