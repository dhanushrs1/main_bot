# In plugins/channel.py
import asyncio
from hydrogram import Client, filters, enums
from info import INDEX_CHANNELS, INDEX_EXTENSIONS, DUMP_CHANNEL
from database.ia_filterdb import save_file

media_filter = filters.document | filters.video


@Client.on_message(filters.chat(INDEX_CHANNELS) & media_filter)
async def media(bot, message):
    """Media Handler"""
    media_obj = getattr(message, message.media.value, None)
    if (str(media_obj.file_name).lower()).endswith(tuple(INDEX_EXTENSIONS)):
        media_obj.caption = message.caption
        sts = await save_file(media_obj)

        # Schedule the copy operation as a background task
        if sts == 'suc' and DUMP_CHANNEL:
            try:
                # Set the caption to be sent
                caption_to_send = message.caption

                # Check if it's a document and an MKV file to remove caption
                if (
                    message.media == enums.MessageMediaType.DOCUMENT
                    and media_obj.file_name
                    and media_obj.file_name.lower().endswith(".mkv")
                ):
                    caption_to_send = ""  # Set caption to empty to remove it

                asyncio.create_task(message.copy(
                    chat_id=DUMP_CHANNEL,
                    caption=caption_to_send
                ))
            except Exception as e:
                print(f"Error creating copy task for dump channel: {e}")
