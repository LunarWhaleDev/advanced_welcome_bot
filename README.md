# Advanced Welcome Bot

#### A Python Telegram Bot that greets everyone who joins a group chat, with additional features

It uses the [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) library and [pickledb](https://bitbucket.org/patx/pickledb) for basic persistence.

Before running the python script, remember to add your telegram bot TOKEN you received from bot father. 
The command framework was inspired by [@jh0ker_welcomebot](https://telegram.me/jh0ker_welcomebot)

## Requirements

- Python 3
- Python telegram bot library (pip install python-telegram-bot)
- PickleDB (pip install pickledb)
- Bot must have admin permission in the group

## How to use

- Clone the repo or download the file welcome.py
- Edit `TOKEN` in welcome.py
- Follow Bot instructions
- By default, only the user who added the bot can use the commands To set welcome/goodbye messages

## Bot Features

- All messages sent by the bot to the group auto-delete after 30 seconds.
- /report triggers the bot to send a report notification via private messages to users in a database list.
- /receive_reports and /stop_reports add/remove users from the report notification list
- /show_chats displays the chats currently using the bot
- /help displays help information for setting up welcome and goodbye messages
