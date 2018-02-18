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
        if not ('world' in r_json and r_json['world'] == 2201):
            try:
                cldbid = ts3conn.clientgetdbidfromuid(cluid=row[2]).parsed[0]['cldbid']
                ts3conn.servergroupdelclient(sgid=127, cldbid=cldbid)
            except ts3.query.TS3QueryError as e:
                print('Failed to remove group from cluid={}, id={}'.format(row[2], row[0]))
                print(e)

            user_delete.append(row[0])

    c.execute('DELETE FROM users WHERE id IN ({})'.format(', '.join(['?'] * len(user_delete))), user_delete)
    c.close()
    conn.commit()
    conn.close()
