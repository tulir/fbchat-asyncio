from fbchat import Client, ThreadType
import asyncio


# Subclass fbchat.Client and override required methods
class EchoBot(Client):
    async def on_message(self, mid=None, author_id=None, message_object=None, thread_id=None,
                         thread_type=ThreadType.USER, at=None, metadata=None, msg=None):
        await self.mark_as_delivered(thread_id, message_object.uid)
        await self.mark_as_read(thread_id)

        # If you're not the author, echo
        if author_id != self.uid:
            await self.send(message_object, thread_id=thread_id, thread_type=thread_type)


loop = asyncio.get_event_loop()


async def start():
    client = EchoBot(loop=loop)
    print("Logging in...")
    await client.start("<email>", "<password>")
    client.listen()


loop.run_until_complete(start())
loop.run_forever()
