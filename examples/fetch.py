from fbchat import Client

client = Client()


async def main():
    await client.start("<email>", "<password>")

    # Fetches a list of all users you're currently chatting with, as `User` objects
    users = await client.fetch_all_users()

    print(f"users' IDs: {[user.uid for user in users]}")
    print(f"users' names: {[user.name for user in users]}")

    # If we have a user id, we can use `fetch_user_info` to fetch a `User` object
    user = (await client.fetch_user_info("<user id>"))["<user id>"]
    # We can also query both mutiple users together, which returns list of `User` objects
    users = await client.fetch_user_info("<1st user id>", "<2nd user id>", "<3rd user id>")

    print(f"user's name: {user.name}")
    print(f"users' names: {[users[k].name for k in users]}")

    # `search_for_users` searches for the user and gives us a list of the results,
    # and then we just take the first one, aka. the most likely one:
    user = (await client.search_for_users("<name of user>"))[0]

    print(f"user ID: {user.uid}")
    print(f"user's name: {user.name}")
    print(f"user's photo: {user.photo}")
    print(f"Is user client's friend: {user.is_friend}")

    # Fetches a list of the 20 top threads you're currently chatting with
    threads = await client.fetch_thread_list()
    # Fetches the next 10 threads
    threads += await client.fetch_thread_list(limit=10, before=threads[-1].last_active)

    print(f"Threads: {threads}")

    # Gets the last 10 messages sent to the thread
    messages = await client.fetch_thread_messages(thread_id="<thread id>", limit=10)
    # Since the message come in reversed order, reverse them
    messages.reverse()

    # Prints the content of all the messages
    for message in messages:
        print(message.text)

    # If we have a thread id, we can use `fetch_thread_info` to fetch a `Thread` object
    thread = (await client.fetch_thread_info("<thread id>"))["<thread id>"]
    print(f"thread's name: {thread.name}")
    print(f"thread's type: {thread.type}")

    # `search_for_threads` searches works like `search_for_users`, but gives us a list of threads instead
    thread = (await client.search_for_threads("<name of thread>"))[0]
    print(f"thread's name: {thread.name}")
    print(f"thread's type: {thread.type}")

    # Here should be an example of `getUnread`

    # Print image url for recent images from thread.
    async for image in client.fetch_thread_images("<thread id>"):
        print(image.large_preview_url)


client.loop.run_until_complete(main())
