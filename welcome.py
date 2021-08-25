#!/usr/bin/env python
# pylint: disable=C0116,W0613
# This program is dedicated to the public domain under the CC0 license.

"""
Simple Bot to handle '(my_)chat_member' updates.
Greets new users & keeps track of which chats the bot is in.

Usage:
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""

import logging
from typing import Tuple, Optional
from time import sleep
import traceback
import sys
from html import escape
import pickledb
from telegram import Update, Chat, ChatMember, ParseMode, ChatMemberUpdated, TelegramError
from telegram.ext import (
    Updater,
    MessageHandler,
    Filters,
    CommandHandler,
    CallbackContext,
    ChatMemberHandler,
)

#Enter your telegram bot token from bot father
#between the quotes
TOKEN = ""

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)

# Create database object
db = pickledb.load("bot.db", True)
if not db.get("chats"):
    db.set("chats", [])

help_text = (
    "Welcomes everyone that enters a group chat that this bot is a "
    "part of. By default, only the person who invited the bot into "
    "the group is able to change settings.\nCommands:\n\n"
    "/welcome - Set welcome message\n"
    "/goodbye - Set goodbye message\n"
    "/disable_goodbye - Disable the goodbye message\n"
    "/lock - Only the person who invited the bot can change messages\n"
    "/unlock - Everyone can change messages\n"
    '/quiet - Disable "Sorry, only the person who..." '
    "& help messages\n"
    '/unquiet - Enable "Sorry, only the person who..." '
    "& help messages\n\n"
    "You can use $username and $title as placeholders when setting"
    " messages. [HTML formatting]"
    "(https://core.telegram.org/bots/api#formatting-options) "
    "is also supported.\n\n"
    "/show_chats - Displays information about the chats active with the bot\n"
    "/report - Send private report message to the authorized user list\n"
    "/receive_reports - Add yourself to the authorized user list for report notifications\n"
    "/stop_reports - Remove yourself from the authorized user list for report notifications"
)

"""
Create database object
Database schema:
<chat_id> -> welcome message
<chat_id>_bye -> goodbye message
<chat_id>_adm -> user id of the user who invited the bot
<chat_id>_lck -> boolean if the bot is locked or unlocked
<chat_id>_quiet -> boolean if the bot is quieted
chats -> list of chat ids where the bot has received messages in.
"""

def extract_status_change(
    chat_member_update: ChatMemberUpdated,
) -> Optional[Tuple[bool, bool]]:
    """Takes a ChatMemberUpdated instance and extracts whether the 'old_chat_member' was a member
    of the chat and whether the 'new_chat_member' is a member of the chat. Returns None, if
    the status didn't change.
    """
    status_change = chat_member_update.difference().get("status")
    old_is_member, new_is_member = chat_member_update.difference().get("is_member", (None, None))

    if status_change is None:
        return None

    old_status, new_status = status_change
    was_member = (
        old_status
        in [
            ChatMember.MEMBER,
            ChatMember.CREATOR,
            ChatMember.ADMINISTRATOR,
        ]
        or (old_status == ChatMember.RESTRICTED and old_is_member is True)
    )
    is_member = (
        new_status
        in [
            ChatMember.MEMBER,
            ChatMember.CREATOR,
            ChatMember.ADMINISTRATOR,
        ]
        or (new_status == ChatMember.RESTRICTED and new_is_member is True)
    )

    return was_member, is_member

def track_chats(update: Update, context: CallbackContext) -> None:
    """Tracks the chats the bot is in."""
    result = extract_status_change(update.my_chat_member)
    if result is None:
        return
    was_member, is_member = result

    # Let's check who is responsible for the change
    cause_name = update.effective_user.full_name

    # Handle chat types differently:
    chat_id = update.effective_chat.id
    chat = update.effective_chat
    if chat.type == Chat.PRIVATE:
        if not was_member and is_member:
            logger.info("%s started the bot", cause_name)
            context.bot_data.setdefault("user_ids", set()).add(chat.id)
        elif was_member and not is_member:
            logger.info("%s blocked the bot", cause_name)
            context.bot_data.setdefault("user_ids", set()).discard(chat.id)
    elif chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
        if not was_member and is_member:
            logger.info("%s added the bot to the group %s", cause_name, chat.title)
            context.bot_data.setdefault("group_ids", set()).add(chat.id)
            db.set(str(chat_id) + "_adm", update.effective_user.id)
            db.set(str(chat_id) + "_lck", True)
            db.set(str(chat_id) + "_quiet", False)
            db.set(str(chat_id) + "_title", chat.title)
            # Keep chatlist
            chats = db.get("chats")
            if str(chat_id) not in chats:
                chats.append(str(chat_id))
                db.set("chats", chats)
                logger.info("I have been added to %d chats" % len(chats))
        elif was_member and not is_member:
            logger.info("%s removed the bot from the group %s", cause_name, chat.title)
            context.bot_data.setdefault("group_ids", set()).discard(chat.id)
            chats = db.get("chats")
            chats.remove(str(chat_id))
            db.set("chats", chats)
            logger.info("Removed chat_id %s from chat list" % chat_id)
    else:
        if not was_member and is_member:
            logger.info("%s added the bot to the channel %s", cause_name, chat.title)
            context.bot_data.setdefault("channel_ids", set()).add(chat.id)
        elif was_member and not is_member:
            logger.info("%s removed the bot from the channel %s", cause_name, chat.title)
            context.bot_data.setdefault("channel_ids", set()).discard(chat.id)

def show_chats(update: Update, context: CallbackContext) -> None:
    """Shows which chats the bot is in"""
    user_ids = ", ".join(str(uid) for uid in context.bot_data.setdefault("user_ids", set()))
    group_ids = ", ".join(str(gid) for gid in context.bot_data.setdefault("group_ids", set()))
    channel_ids = ", ".join(str(cid) for cid in context.bot_data.setdefault("channel_ids", set()))
    text = (
        f"As of the last script initilization, @{context.bot.username} has started a conversation with the user IDs: {user_ids}\n"
        f"Moreover it has become a member of the groups with IDs: {group_ids}\n"
        f"and administrator in the channels with IDs: {channel_ids}\n\n"
        f"Group Titles active in the database:\n"
    )
    list = db.get("chats")
    for group in list:
        title = db.get(str(group) + "_title")
        text = f"{text}{title}\n"
    a = update.effective_message.reply_text(text)
    mess = []
    mess.append(update.effective_chat.id)
    mess.append(a.message_id)
    context.job_queue.run_once(rm_message, 30, context=mess)

def receive_reports(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if chat_id > 0:
        update.effective_chat.send_message("Please send this command in a group!")
        return
    if not db.get(str(chat_id) + "_reports"):
        db.set(str(chat_id) + "_reports", [])
    list = db.get(str(chat_id) + "_reports")
    if user_id not in list:
        list.append(user_id)
        db.set(str(chat_id) + "_reports", list)
        a = update.effective_chat.send_message("Added! You will receive report notifications in a private chat with me!")
        mess = []
        mess.append(chat_id)
        mess.append(a.message_id)
        context.job_queue.run_once(rm_message, 30, context=mess)

def stop_reports(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if chat_id > 0:
        update.effective_chat.send_message("Please send this command in a group!")
        return
    if not db.get(str(chat_id) + "_reports"):
        return
    list = db.get(str(chat_id) + "_reports")
    if user_id in list:
        list.remove(user_id)
        db.set(str(chat_id) + "_reports", list)
        a = update.effective_chat.send_message("You will no longer receive notifications of reports.")
        mess = []
        mess.append(chat_id)
        mess.append(a.message_id)
        context.job_queue.run_once(rm_message, 30, context=mess)

def report(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    title = update.effective_chat.title
    if chat_id > 0:
        return
    list = db.get(str(chat_id) + "_reports")
    for user in list:
        context.bot.send_message(user, f"Message reported in the group: {title}")
    a = update.effective_chat.send_message("Reported!")
    mess = []
    mess.append(chat_id)
    mess.append(a.message_id)
    context.job_queue.run_once(rm_message, 30, context=mess)

def greet_chat_members(update: Update, context: CallbackContext) -> None:
    """Greets new users in chats and announces when someone leaves"""
    result = extract_status_change(update.chat_member)
    if result is None:
        return

    was_member, is_member = result
    cause_name = update.chat_member.from_user.mention_html()
    member_name = update.chat_member.new_chat_member.user.mention_html()

    username = update.chat_member.new_chat_member.user.first_name

    title = update.effective_chat.title
    chat_id = update.effective_chat.id
    chat_str = str(chat_id)

    if not was_member and is_member:
        # Pull the custom message for this chat from the database
        text = db.get(chat_str)
        # Use default message if there's no custom one set
        if text is False:
            text = "Hello $username! Welcome to $title"

        # Replace placeholders and send message
        text = text.replace("$username", username)
        text = text.replace("$title", title)
        text = text.replace("$n", "\n")

        a = update.effective_chat.send_message(
            text,
            parse_mode=ParseMode.HTML,
        )
        mess = []
        mess.append(chat_id)
        mess.append(a.message_id)
        context.job_queue.run_once(rm_message, 30, context=mess)

    elif was_member and not is_member:
        # Pull the custom message for this chat from the database
        text = db.get(chat_str + "_bye")
        # Goodbye was disabled
        if text is None:
            return

        # Use default message if there's no custom one set
        if text is False:
            text = "Goodbye, $username!"

        # Replace placeholders and send message
        text = text.replace("$username", username)
        text = text.replace("$title", title)
        text = text.replace("$n", "\n")

        a = update.effective_chat.send_message(
            text,
            parse_mode=ParseMode.HTML,
        )
        mess = []
        mess.append(chat_id)
        mess.append(a.message_id)
        context.job_queue.run_once(rm_message, 30, context=mess)

def rm_message(context):
    context.bot.deleteMessage(context.job.context[0], context.job.context[1])

def check(update, context, override_lock=None):
    """
    Perform some checks on the update. If checks were successful, returns True,
    else sends an error message to the chat and returns False.
    """

    chat_id = update.effective_chat.id
    chat_str = str(chat_id)

    if chat_id > 0:
        update.effective_chat.send_message(
            "Please add me to a group first!",
        )
        return False

    locked = override_lock if override_lock is not None else db.get(chat_str + "_lck")

    if locked and db.get(chat_str + "_adm") != update.message.from_user.id:
        if db.get(chat_str + "_quiet") == False:
            a = update.effective_chat.send_message(
                "Sorry, only the person who invited me can do that.",
            )
            mess = []
            mess.append(chat_id)
            mess.append(a.message_id)
            context.job_queue.run_once(rm_message, 30, context=mess)
        return False

    return True

# Print help text
def help(update, context):
    """ Prints help text """
    chat_id = update.effective_chat.id
    chat_str = str(chat_id)
    if (
        db.get(chat_str + "_quiet") == False
        or db.get(chat_str + "_adm") == update.message.from_user.id
    ):
        a = update.effective_chat.send_message(help_text, disable_web_page_preview=True)
        mess = []
        mess.append(chat_id)
        mess.append(a.message_id)
        context.job_queue.run_once(rm_message, 30, context=mess)

# Set custom message
def set_welcome(update, context):
    """ Sets custom welcome message """

    chat_id = update.effective_chat.id

    # Check admin privilege and group context
    if not check(update, context):
        return

    # Split message into words and remove mentions of the bot
    message = ' '.join(context.args)

    # Only continue if there's a message
    if not message:
        a = update.effective_chat.send_message(
            text="You need to send a message, too! For example:\n"
            "<code>/welcome Hello $username, welcome to "
            "$title!</code>",
            parse_mode=ParseMode.HTML,
        )
        mess = []
        mess.append(chat_id)
        mess.append(a.message_id)
        context.job_queue.run_once(rm_message, 30, context=mess)
        return

    # Put message into database
    db.set(str(chat_id), message)

    a = update.effective_chat.send_message("Got it!")
    mess = []
    mess.append(chat_id)
    mess.append(a.message_id)
    context.job_queue.run_once(rm_message, 30, context=mess)

# Set custom message
def set_goodbye(update, context):
    """ Enables and sets custom goodbye message """

    chat_id = update.effective_chat.id

    # Check admin privilege and group context
    if not check(update, context):
        return

    # Split message into words and remove mentions of the bot
    message = ' '.join(context.args)

    # Only continue if there's a message
    if not message:
        a = update.effective_chat.send_message(
            text="You need to send a message, too! For example:\n"
            "<code>/goodbye Goodbye, $username!</code>",
            parse_mode=ParseMode.HTML,
        )
        mess = []
        mess.append(chat_id)
        mess.append(a.message_id)
        context.job_queue.run_once(rm_message, 30, context=mess)
        return

    # Put message into database
    db.set(str(chat_id) + "_bye", message)

    a = update.effective_chat.send_message("Got it!")
    mess = []
    mess.append(chat_id)
    mess.append(a.message_id)
    context.job_queue.run_once(rm_message, 30, context=mess)

def disable_goodbye(update, context):
    """ Disables the goodbye message """

    chat_id = update.effective_chat.id

    # Check admin privilege and group context
    if not check(update, context):
        return

    # Disable goodbye message
    db.set(str(chat_id) + "_bye", False)

    a = update.effective_chat.send_message("Got it!")
    mess = []
    mess.append(chat_id)
    mess.append(a.message_id)
    context.job_queue.run_once(rm_message, 30, context=mess)

def lock(update, context):
    """ Locks the chat, so only the invitee can change settings """

    chat_id = update.effective_chat.id

    # Check admin privilege and group context
    if not check(update, context, override_lock=True):
        return

    # Lock the bot for this chat
    db.set(str(chat_id) + "_lck", True)

    a = update.effective_chat.send_message("Got it!")
    mess = []
    mess.append(chat_id)
    mess.append(a.message_id)
    context.job_queue.run_once(rm_message, 30, context=mess)

def quiet(update, context):
    """ Quiets the chat, so no error messages will be sent """

    chat_id = update.effective_chat.id

    # Check admin privilege and group context
    if not check(update, context, override_lock=True):
        return

    # Lock the bot for this chat
    db.set(str(chat_id) + "_quiet", True)

    a = update.effective_chat.send_message("Got it!")
    mess = []
    mess.append(chat_id)
    mess.append(a.message_id)
    context.job_queue.run_once(rm_message, 30, context=mess)

def unquiet(update, context):
    """ Unquiets the chat """

    chat_id = update.effective_chat.id

    # Check admin privilege and group context
    if not check(update, context, override_lock=True):
        return

    # Unquiet the bot for this chat
    db.set(str(chat_id) + "_quiet", False)

    a = update.effective_chat.send_message("Got it!")
    mess = []
    mess.append(chat_id)
    mess.append(a.message_id)
    context.job_queue.run_once(rm_message, 30, context=mess)

def unlock(update, context):
    """ Unlocks the chat, so everyone can change settings """

    chat_id = update.effective_chat.id

    # Check admin privilege and group context
    if not check(update, context):
        return

    # Unlock the bot for this chat
    db.set(str(chat_id) + "_lck", False)

    a = update.effective_chat.send_message("Got it!")
    mess = []
    mess.append(chat_id)
    mess.append(a.message_id)
    context.job_queue.run_once(rm_message, 30, context=mess)

def error(update, context, **kwargs):
    """ Error handling """
    error = context.error
    chat_id = update.effective_chat.id

    try:
        if isinstance(error, TelegramError) and (
            error.message == "Unauthorized"
            or error.message == "Have no rights to send a message"
            or "PEER_ID_INVALID" in error.message
        ):
            chats = db.get("chats")
            chats.remove(str(chat_id))
            db.set("chats", chats)
            logger.info("Removed chat_id %s from chat list" % chat_id)
        else:
            logger.error("An error (%s) occurred: %s" % (type(error), error.message))
    except:
        pass

def main() -> None:
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater(TOKEN)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", help))
    dispatcher.add_handler(CommandHandler("help", help))
    dispatcher.add_handler(CommandHandler("welcome", set_welcome))
    dispatcher.add_handler(CommandHandler("goodbye", set_goodbye))
    dispatcher.add_handler(CommandHandler("disable_goodbye", disable_goodbye))
    dispatcher.add_handler(CommandHandler("lock", lock))
    dispatcher.add_handler(CommandHandler("unlock", unlock))
    dispatcher.add_handler(CommandHandler("quiet", quiet))
    dispatcher.add_handler(CommandHandler("unquiet", unquiet))
    dispatcher.add_handler(CommandHandler("lock", lock))
    dispatcher.add_handler(CommandHandler("receive_reports", receive_reports))
    dispatcher.add_handler(CommandHandler("stop_reports", stop_reports))
    dispatcher.add_handler(CommandHandler("report", report))
    # Keep track of which chats the bot is in
    dispatcher.add_handler(ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER))
    dispatcher.add_handler(CommandHandler("show_chats", show_chats))

    # Handle members joining/leaving chats.
    dispatcher.add_handler(ChatMemberHandler(greet_chat_members, ChatMemberHandler.CHAT_MEMBER))

    dispatcher.add_error_handler(error)

    # Start the Bot
    # We pass 'allowed_updates' handle *all* updates including `chat_member` updates
    # To reset this, simply pass `allowed_updates=[]`
    updater.start_polling(allowed_updates=Update.ALL_TYPES)

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == "__main__":
    main()

