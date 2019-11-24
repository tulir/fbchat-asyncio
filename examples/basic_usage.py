from fbchat import Client, ThreadType, Message

client = Client()


async def main():
    await client.start("<email>", "<password>")
    print(f"Own ID: {client.uid}")
    await client.send(Message(text="Hi me!"), thread_id=client.uid, thread_type=ThreadType.USER)
    await client.logout()


client.loop.run_until_complete(main())
