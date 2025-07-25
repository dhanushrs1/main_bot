import re
import time
import asyncio
from hydrogram import Client, filters, enums
from hydrogram.errors import FloodWait
from info import ADMINS, INDEX_EXTENSIONS, DUMP_CHANNEL
from database.ia_filterdb import save_file
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils import temp, get_readable_time

lock = asyncio.Lock()

@Client.on_callback_query(filters.regex(r'^index'))
async def index_files(bot, query):
    _, ident, chat, lst_msg_id, skip = query.data.split("#")
    if ident == 'yes':
        msg = query.message
        await msg.edit("Starting Indexing...")
        try:
            chat = int(chat)
        except:
            chat = chat
        await index_files_to_db(int(lst_msg_id), chat, msg, bot, int(skip))
    elif ident == 'cancel':
        temp.CANCEL = True
        await query.message.edit("Trying to cancel Indexing...")


@Client.on_message(filters.command('index') & filters.private & filters.user(ADMINS))
async def send_for_index(bot, message):
    if lock.locked():
        return await message.reply('Wait until previous process complete.')
    i = await message.reply("Forward last message or send last message link.")
    msg = await bot.listen(chat_id=message.chat.id, user_id=message.from_user.id)
    await i.delete()
    if msg.text and msg.text.startswith("https://t.me"):
        try:
            msg_link = msg.text.split("/")
            last_msg_id = int(msg_link[-1])
            chat_id = msg_link[-2]
            if chat_id.isnumeric():
                chat_id = int(("-100" + chat_id))
        except:
            await message.reply('Invalid message link!')
            return
    elif msg.forward_from_chat and msg.forward_from_chat.type == enums.ChatType.CHANNEL:
        last_msg_id = msg.forward_from_message_id
        chat_id = msg.forward_from_chat.username or msg.forward_from_chat.id
    else:
        await message.reply('This is not forwarded message or link.')
        return
    try:
        chat = await bot.get_chat(chat_id)
    except Exception as e:
        return await message.reply(f'Errors - {e}')

    if chat.type != enums.ChatType.CHANNEL:
        return await message.reply("I can index only channels.")

    s = await message.reply("Send skip message number.")
    msg = await bot.listen(chat_id=message.chat.id, user_id=message.from_user.id)
    await s.delete()
    try:
        skip = int(msg.text)
    except:
        return await message.reply("Number is invalid.")

    buttons = [[
        InlineKeyboardButton('YES', callback_data=f'index#yes#{chat_id}#{last_msg_id}#{skip}')
    ],[
        InlineKeyboardButton('CLOSE', callback_data='close_data'),
    ]]
    reply_markup = InlineKeyboardMarkup(buttons)
    await message.reply(f'Do you want to index {chat.title} channel?\nTotal Messages: <code>{last_msg_id}</code>', reply_markup=reply_markup)


async def index_files_to_db(lst_msg_id, chat, msg, bot, skip):
    start_time = time.time()
    total_files = 0
    duplicate = 0
    errors = 0
    deleted = 0
    no_media = 0
    unsupported = 0
    badfiles = 0
    current = skip

    try:
        chat_obj = await bot.get_chat(chat)
        chat_title = chat_obj.title
    except Exception as e:
        print(f"Could not get chat title for logging: {e}")
        chat_title = "Unknown Channel"

    async with lock:
        try:
            async for message in bot.iter_messages(chat, lst_msg_id, skip):
                time_taken = get_readable_time(time.time()-start_time)
                if temp.CANCEL:
                    temp.CANCEL = False
                    await msg.edit(f"Successfully Cancelled!\nCompleted in {time_taken}\n\nSaved <code>{total_files}</code> files to Database!\nDuplicate Files Skipped: <code>{duplicate}</code>\nDeleted Messages Skipped: <code>{deleted}</code>\nNon-Media messages skipped: <code>{no_media + unsupported}</code>\nUnsupported Media: <code>{unsupported}</code>\nErrors Occurred: <code>{errors}</code>\nBad Files Ignoref: <code>{badfiles}</code>")
                    return
                current += 1
                if current % 30 == 0:
                    btn = [[
                        InlineKeyboardButton('CANCEL', callback_data=f'index#cancel#{chat}#{lst_msg_id}#{skip}')
                    ]]
                    # Log progress to dump channel
                    if DUMP_CHANNEL:
                        log_message = f"#INDEX_LOG\n\n**Channel:** {chat_title} (`{chat}`)\n**Last Message ID Processed:** `{message.id}`"
                        asyncio.create_task(bot.send_message(chat_id=DUMP_CHANNEL, text=log_message))

                    try:
                        await msg.edit_text(text=f"Total messages received: <code>{current}</code>\nTotal messages saved: <code>{total_files}</code>\nDuplicate Files Skipped: <code>{duplicate}</code>\nDeleted Messages Skipped: <code>{deleted}</code>\nNon-Media messages skipped: <code>{no_media + unsupported}</code>\nUnsupported Media: <code>{unsupported}</code>\nErrors Occurred: <code>{errors}</code>\nBad Files Ignoref: <code>{badfiles}</code>", reply_markup=InlineKeyboardMarkup(btn))
                    except FloodWait as e:
                        await asyncio.sleep(e.value)
                if message.empty:
                    deleted += 1
                    continue
                elif not message.media:
                    no_media += 1
                    continue
                elif message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.DOCUMENT]:
                    unsupported += 1
                    continue
                media = getattr(message, message.media.value, None)
                if not media:
                    unsupported += 1
                    continue
                elif not (str(media.file_name).lower()).endswith(tuple(INDEX_EXTENSIONS)):
                    unsupported += 1
                    continue
                media.caption = message.caption
                sts = await save_file(media)

                if sts == 'suc' and DUMP_CHANNEL:
                    try:
                        caption_to_send = message.caption
                        if (
                            message.media == enums.MessageMediaType.DOCUMENT
                            and media.file_name
                            and media.file_name.lower().endswith(".mkv")
                        ):
                            caption_to_send = ""
                        asyncio.create_task(message.copy(
                            chat_id=DUMP_CHANNEL,
                            caption=caption_to_send
                        ))
                    except Exception as e:
                        print(f"Error creating copy task for dump channel during manual index: {e}")

                if sts == 'suc':
                    total_files += 1
                elif sts == 'dup':
                    duplicate += 1
                elif sts == 'err':
                    errors += 1
        except Exception as e:
            await msg.reply(f'Index canceled due to Error - {e}')
        else:
            time_taken = get_readable_time(time.time()-start_time)
            await msg.edit(f'Succesfully saved <code>{total_files}</code> to Database!\nCompleted in {time_taken}\n\nDuplicate Files Skipped: <code>{duplicate}</code>\nDeleted Messages Skipped: <code>{deleted}</code>\nNon-Media messages skipped: <code>{no_media + unsupported}</code>\nUnsupported Media: <code>{unsupported}</code>\nErrors Occurred: <code>{errors}</code>\nBad Files Ignoref: <code>{badfiles}</code>')
            
            # Send final completion log to dump channel
            if DUMP_CHANNEL:
                final_log_message = f"#INDEX_COMPLETE\n\n**Channel:** {chat_title} (`{chat}`)\n**Status:** Successfully completed indexing.\n**Total Files Indexed:** `{total_files}`"
                asyncio.create_task(bot.send_message(chat_id=DUMP_CHANNEL, text=final_log_message))
