from fbchat import (Client, ThreadType, Message, EmojiSize, Sticker, TypingStatus, MessageReaction,
                    ThreadColor, Mention)

client = Client()


async def main():
    await client.start("<email>", "<password>")

    thread_id = "1234567890"
    thread_type = ThreadType.GROUP

    # Will send a message to the thread
    await client.send(Message(text="<message>"), thread_id=thread_id, thread_type=thread_type)

    # Will send the default `like` emoji
    await client.send(
        Message(emoji_size=EmojiSize.LARGE), thread_id=thread_id, thread_type=thread_type
    )

    # Will send the emoji `👍`
    await client.send(
        Message(text="👍", emoji_size=EmojiSize.LARGE),
        thread_id=thread_id,
        thread_type=thread_type,
    )

    # Will send the sticker with ID `767334476626295`
    await client.send(
        Message(sticker=Sticker("767334476626295")),
        thread_id=thread_id,
        thread_type=thread_type,
    )

    # Will send a message with a mention
    await client.send(
        Message(
            text="This is a @mention", mentions=[Mention(thread_id, offset=10, length=8)]
        ),
        thread_id=thread_id,
        thread_type=thread_type,
    )

    # Will send the image located at `<image path>`
    await client.send_local_files(
        ["<image path>"],
        message=Message(text="This is a local image"),
        thread_id=thread_id,
        thread_type=thread_type,
    )

    # Will download the image at the URL `<image url>`, and then send it
    await client.send_remote_files(
        ["<image url>"],
        message=Message(text="This is a remote image"),
        thread_id=thread_id,
        thread_type=thread_type,
    )

    # Only do these actions if the thread is a group
    if thread_type == ThreadType.GROUP:
        # Will remove the user with ID `<user id>` from the thread
        await client.remove_user_from_group("<user id>", thread_id=thread_id)

        # Will add the user with ID `<user id>` to the thread
        await client.add_users_to_group(["<user id>"], thread_id=thread_id)

        # Will add the users with IDs `<1st user id>`, `<2nd user id>` and `<3th user id>` to the thread
        await client.add_users_to_group(
            ["<1st user id>", "<2nd user id>", "<3rd user id>"], thread_id=thread_id
        )

    # Will change the nickname of the user `<user_id>` to `<new nickname>`
    await client.change_nickname(
        "<new nickname>", "<user id>", thread_id=thread_id, thread_type=thread_type
    )

    # Will change the title of the thread to `<title>`
    await client.change_thread_title("<title>", thread_id=thread_id, thread_type=thread_type)

    # Will set the typing status of the thread to `TYPING`
    await client.set_typing_status(
        TypingStatus.TYPING, thread_id=thread_id, thread_type=thread_type
    )

    # Will change the thread color to `MESSENGER_BLUE`
    await client.change_thread_color(ThreadColor.MESSENGER_BLUE, thread_id=thread_id)

    # Will change the thread emoji to `👍`
    await client.change_thread_emoji("👍", thread_id=thread_id)

    # Will react to a message with a 😍 emoji
    await client.react_to_message("<message id>", MessageReaction.LOVE)


client.loop.run_until_complete(main())
