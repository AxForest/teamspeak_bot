# teamspeak_bot
A TeamSpeak bot for assigning server groups based on the user's world in Guild Wars 2

# Requirements 
* python3
* mysql-connector==2.1.6
* requests==2.18.4
* ts3==2.0.0b2
* ratelimit==2.2.1

# Installation/Usage
- Create a table in a MySQL/MariaDB database  
```mysql
CREATE TABLE `users`  (
  `id` int UNSIGNED NOT NULL AUTO_INCREMENT,
  `name` varchar(40) NOT NULL,
  `world` int(4) NOT NULL,
  `apikey` varchar(80) NOT NULL,
  `tsuid` varchar(30) NOT NULL,
  `timestamp` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP(0),
  `ignored` tinyint(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  INDEX `tsuid`(`tsuid`)
);
```
- Create a TeamSpeak Query Admin account
- Copy `config.example.py` to `config.py` and set the required values
- Start `bot.py` within `screen` or `tmux`
- Run `cycle.py` via cron in regular intervals
