import asyncio
import fbchat


async def main():
    session = await fbchat.Session.login("<email>", "<password>")
    listener = fbchat.Listener(session=session, chat_on=False, foreground=False)

    async for event in listener.listen():
        if isinstance(event, fbchat.MessageEvent):
            print(f"{event.message.text} from {event.author.id} in {event.thread.id}")
            # If you're not the author, echo
            if event.author.id != session.user.id:
                await event.thread.send_text(event.message.text)


asyncio.run(main())
