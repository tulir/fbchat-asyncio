from fbchat import Client, ThreadColor
import asyncio

# Change this to your group id
old_thread_id = "1234567890"

# Change these to match your liking
old_color = ThreadColor.MESSENGER_BLUE
old_emoji = "👍"
old_title = "Old group chat name"
old_nicknames = {
    "12345678901": "User nr. 1's nickname",
    "12345678902": "User nr. 2's nickname",
    "12345678903": "User nr. 3's nickname",
    "12345678904": "User nr. 4's nickname",
}


class KeepBot(Client):
    async def on_color_change(self, author_id, new_color, thread_id, thread_type, **kwargs):
        if old_thread_id == thread_id and old_color != new_color:
            print(f"{author_id} changed the thread color. It will be changed back")
            await self.change_thread_color(old_color, thread_id=thread_id)

    async def on_emoji_change(self, author_id, new_emoji, thread_id, thread_type, **kwargs):
        if old_thread_id == thread_id and new_emoji != old_emoji:
            print(f"{author_id} changed the thread emoji. It will be changed back")
            await self.change_thread_emoji(old_emoji, thread_id=thread_id)

    async def on_people_added(self, added_ids, author_id, thread_id, **kwargs):
        if old_thread_id == thread_id and author_id != self.uid:
            print(f"{added_ids} got added. They will be removed")
            for added_id in added_ids:
                await self.remove_user_from_group(added_id, thread_id=thread_id)

    async def on_person_removed(self, removed_id, author_id, thread_id, **kwargs):
        # No point in trying to add ourself
        if old_thread_id == thread_id and removed_id != self.uid and author_id != self.uid:
            print(f"{removed_id} got removed. They will be re-added")
            await self.add_users_to_group(removed_id, thread_id=thread_id)

    async def on_title_change(self, author_id, new_title, thread_id, thread_type, **kwargs):
        if old_thread_id == thread_id and old_title != new_title:
            print(f"{author_id} changed the thread title. It will be changed back")
            await self.change_thread_title(old_title, thread_id=thread_id, thread_type=thread_type)

    async def on_nickname_change(self, author_id, changed_for, new_nickname, thread_id, thread_type,
                                 **kwargs):
        if (old_thread_id == thread_id
                and changed_for in old_nicknames
                and old_nicknames[changed_for] != new_nickname):
            print(f"{author_id} changed {changed_for}'s' nickname. It will be changed back")
            await self.change_nickname(old_nicknames[changed_for], changed_for,
                                       thread_id=thread_id, thread_type=thread_type,)


loop = asyncio.get_event_loop()


async def start():
    client = KeepBot(loop=loop)
    await client.start("<email>", "<password>")
    client.listen()


loop.run_until_complete(start())
loop.run_forever()
