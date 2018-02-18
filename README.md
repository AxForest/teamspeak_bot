# teamspeak_bot
Guild Wars 2 - Teamspeak Bot

requirements: 
* python3
* ts3 < 1.0

1.) Create a sqlite3 Database with 5 collums (name, world, apikey, tsid, timestamp)
* Name      : Account name
* World     : e.g Kodash
* apikey    : The API - Key
* tsid      : The Teamspeak Id
* timestamp : Date and Time

2.) Create a Teamspeak Query Admin 
Insert your IP and login into bot.py and cycle.py

3.) Adjust your Servergroup and Channel

4.) 
* Start bot.py within a screen or tmux
* start cycle.py via cronjob whenever you like.

5.) done
