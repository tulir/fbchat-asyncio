from fbchat import Client, ThreadType
import asyncio


class RemoveBot(Client):
    async def on_message(self, author_id, message_object, thread_id, thread_type, **kwargs):
        # We can only kick people from group chats, so no need to try if it's a user chat
        if message_object.text == "Remove me!" and thread_type == ThreadType.GROUP:
            print(f"{author_id} will be removed from {thread_id}")
            await self.remove_user_from_group(author_id, thread_id=thread_id)
        else:
            # Sends the data to the inherited on_message, so that we can still
            # see when a message is recieved
            await super().on_message(author_id=author_id, message_object=message_object,
                                     thread_id=thread_id, thread_type=thread_type, **kwargs)


loop = asyncio.get_event_loop()


async def start():
    client = RemoveBot(loop=loop)
    await client.start("<email>", "<password>")
    client.listen()


loop.run_until_complete(start())
loop.run_forever()
