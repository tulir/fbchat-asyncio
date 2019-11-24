# -*- coding: UTF-8 -*-
from fbchat import Client
import asyncio

# Subclass fbchat.Client and override required methods
class EchoBot(Client):
    async def on_message(self, author_id, message_object, thread_id, thread_type, **kwargs):
        await self.mark_as_delivered(thread_id, message_object.uid)
        await self.mark_as_read(thread_id)

        # If you're not the author, echo
        if author_id != self.uid:
            await self.send(message_object, thread_id=thread_id, thread_type=thread_type)

async def start():
    client = EchoBot()
    print("start..")
    await client.start("<email>", "<password>")
    client.listen()


asyncio.get_event_loop().run_until_complete(start())
asyncio.get_event_loop().run_forever()
