import asyncio
import fbchat


async def main():
    # Log the user in
    session = await fbchat.Session.login("<email>", "<password>")

    print("Own id: {}".format(session.user.id))

    # Send a message to yourself
    await session.user.send_text("Hi me!")

    # Log the user out
    await session.logout()


asyncio.run(main())
