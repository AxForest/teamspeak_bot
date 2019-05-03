# teamspeak_bot
A TeamSpeak bot for assigning server groups based on the user's world in Guild Wars 2

# Requirements 
* python3
* mysql-connector-python==8.0.15
* requests==2.21.0
* ts3==2.0.0b2
* ratelimit==2.2.1

# Installation/Usage
- Create a table in a MySQL/MariaDB database  
```mysql
CREATE TABLE `users` (
  `id` int UNSIGNED NOT NULL AUTO_INCREMENT,
  `name` varchar(40) NOT NULL,
  `world` int(4) NOT NULL,
  `apikey` varchar(80) NOT NULL,
  `tsuid` varchar(30) NOT NULL,
  `timestamp` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `last_check` datetime NULL DEFAULT NULL,
  `ignored` tinyint(1) NOT NULL DEFAULT 0,
  `guilds` varchar(255) NULL DEFAULT '[]',
  PRIMARY KEY (`id`),
  INDEX `tsuid`(`tsuid`)
);
```
- Create two TeamSpeak Query Admin accounts
- Copy `config.example.py` to `config.py` and set the required values
- Start `bot.py` within `screen` or `tmux`
- Run `cycle.py` via cron in regular intervals

# Notes
- The bot assumes that the guest role is still called `Guest`