import asyncio
import fbchat

# If the script is running on Windows, change the default policy for the event loops to be compatible
if os.name == "nt":
    asyncio.DefaultEventLoopPolicy = asyncio.WindowsSelectorEventLoopPolicy


# Listen for new events and when that event is a new received message, reply to the author of the message
async def listen(listener, session):
    async for event in listener.listen():
        if isinstance(event, fbchat.MessageEvent):
            print(f"{event.message.text} from {event.author.id} in {event.thread.id}")
            # If you're not the author, echo
            if event.author.id != session.user.id:
                await event.thread.send_text(event.message.text)


async def main():
    session = await fbchat.Session.login("<email>", "<password>")

    client = fbchat.Client(session=session)
    listener = fbchat.Listener(session=session, chat_on=False, foreground=False)

    listen_task = asyncio.create_task(listen(listener, session))

    client.sequence_id_callback = listener.set_sequence_id

    # Call the fetch_threads API once to get the latest sequence ID
    await client.fetch_threads(limit=1).__anext__()

    # Let the listener run, otherwise the script will stop
    await listen_task


asyncio.run(main())
