"""A bot for monitoring the Protohaven server and performing automated activities"""

import asyncio
import logging
from urllib.parse import urlparse

import discord

from protohaven_api.config import get_config

log = logging.getLogger("discord_bot")


class PHClient(discord.Client):
    """A discord bot that handles non-webhook tasks on the Protohaven discord server"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.role_map = {}
        self.user_map = {}
        self.member_join_hook_fn = lambda details: []
        self._stored_loop = None

    async def setup_hook(self):
        """Store the event loop when the client starts"""
        self._stored_loop = asyncio.get_running_loop()

    def get_stored_loop(self):
        """Get the stored event loop"""
        return self._stored_loop

    @property
    def guild(self):
        """Fetches the guild name for the Protohaven server"""
        guild = self.get_guild(get_config("discord_bot/guild_id"))
        if guild is None:
            raise RuntimeError(f"Guild {get_config('discord_bot/guild_id')} not found")
        return guild

    async def on_ready(self):
        """Runs when the bot is connected and ready to go"""
        log.info(f"Logged in as {self.user}")
        # role = guild.get_role(role_id)
        for r in self.guild.roles:
            self.role_map[r.name] = r
        log.info(f"Loaded {len(self.role_map)} roles")

        for m in self.guild.members:
            self.user_map[m.name] = m.id
            self.user_map[m.display_name] = m.id
        log.info(f"Loaded {len(self.user_map)} users")

    async def resolve_user_id(self, name):
        """Resolves a user ID from a name or display name"""
        return self.user_map.get(name)

    async def handle_hook_action(self, fn_name, *args):
        """Handle actions yielded back from calling a hook_fn (see `on_member_join`)"""
        fn = getattr(self, fn_name)
        log.info(f"handle_hook_action {fn} {args}")
        return await fn(*args)

    async def on_member_join(self, member):
        """Runs when a new member joins the server"""
        log.info(f"New member joined: {member.name}")
        if not self.hook_on_user_is_permitted(member.name):
            log.warning("Hook on member not permitted; skipping join hook action")
            return
        if member.guild != self.guild:
            log.info(f"Ignoring member joining unrelated guild {member.guild}")
            return
        for a in self.member_join_hook_fn(self._member_details(member)):
            await self.handle_hook_action(*a)

    async def set_nickname(self, name, nickname):
        """Set the nickname of a named server member"""
        mem = self.guild.get_member_named(name)
        if mem is None:
            log.info(f"set_nickname: failed to find {name}")
            return False
        try:
            await mem.edit(nick=nickname)
            return True
        except discord.HTTPException as e:
            log.error(str(e))
            return str(e)

    async def _role_edit(self, name, role_name, action):
        """Grants a role (e.g. "Members") to a named server member"""
        mem = self.guild.get_member_named(name)
        if mem is None:
            log.info("Discord user {name} not found")
            return False

        log.info(f"Adding role {role_name} to {name}")
        try:
            if action == "ADD":
                await mem.add_roles(self.role_map[role_name])
            elif action == "REMOVE":
                await mem.remove_roles(self.role_map[role_name])
            else:
                raise RuntimeError(f"Unknown role_edit action: {action}")
            return True
        except discord.HTTPException as e:
            log.error(str(e))
            return str(e)

    async def grant_role(self, name, role_name):
        """Grants a role (e.g. "Members") to a named server member"""
        rep = await self._role_edit(name, role_name, "ADD")
        return rep

    async def revoke_role(self, name, role_name):
        """Revokes a role (e.g. "Members") from a named server member"""
        rep = await self._role_edit(name, role_name, "REMOVE")
        return rep

    def _member_details(self, m):
        return (m.name, m.display_name, m.joined_at, [(r.name, r.id) for r in m.roles])

    async def get_all_members(self):
        """Retrieves all data on members and roles for the server"""
        return [self._member_details(m) for m in self.guild.members]

    async def get_member_channels(self):
        """Returns all channels in self.guild visible to the Members role.
        Category headers and non-member-visible channels are stripped out."""
        members_role = discord.utils.get(self.guild.roles, name="Members")
        if not members_role:
            return []
        return [
            (channel.id, channel.name)
            for channel in self.guild.channels
            if members_role in channel.overwrites and channel.category
        ]

    async def get_channel_history(self, channel_id, from_date, to_date, max_length):
        """Gets the history of a channel up to a maximum length, between two dates"""
        log.info(f"Fetching channel {channel_id}")
        channel = self.guild.get_channel(channel_id)
        num = 0
        total_length = 0
        if isinstance(channel, discord.TextChannel):
            async for message in channel.history(
                limit=None, after=from_date, before=to_date
            ):
                message_length = len(message.content)
                total_length += message_length
                if total_length > max_length:
                    break

                images = []
                videos = []
                for attachment in message.attachments:
                    log.info(attachment)
                    parsed_url = urlparse(attachment.url)
                    file_suffix = parsed_url.path.split("/")[-1].split("?")[0]
                    if file_suffix.endswith(("jpg", "jpeg", "png", "gif")):
                        images.append(attachment.url)
                    elif file_suffix.endswith(("mp4", "mov")):
                        videos.append(attachment.url)

                yield {
                    "ref": message.jump_url,
                    "created_at": message.created_at,
                    "author": message.author.display_name,
                    "content": message.content,
                    "images": images,
                    "videos": videos,
                }
                num += 1

        log.info(
            f"Retrieved {num} messages from channel {channel.name} (#{channel.id})"
        )

    async def get_member_details(self, discord_id):
        """Returns data in the same format as `get_all_members`
        just for a single member (if exists)"""
        m = self.guild.get_member_named(discord_id)
        if m is None:
            return None
        return self._member_details(m)

    async def send_dm(self, discord_id, msg):
        """Send a direct message"""
        mem = self.guild.get_member_named(discord_id)
        if mem is None:
            raise RuntimeError(
                f"Cannot DM discord member {discord_id}; not found in PH server"
            )
        await mem.send(msg)

    def _as_filter(self, f):
        if str(f) == "None" or f.strip() == "":
            return None

        if not isinstance(f, str):
            raise RuntimeError(f"Invalid type of filter config value {type(f)}")
        return {s.lower().strip() for s in f.split(",")}

    def hook_on_user_is_permitted(self, discord_id: str):
        """Returns True if configuration dictates that we should run hooks
        for this user."""
        if not get_config("discord_bot/event_hooks/enabled", as_bool=True):
            return False
        include_filter = self._as_filter(
            get_config("discord_bot/event_hooks/include_filter")
        )
        if include_filter is not None and discord_id not in include_filter:
            return False
        exclude_filter = self._as_filter(
            get_config("discord_bot/event_hooks/exclude_filter")
        )
        if exclude_filter is not None and discord_id in exclude_filter:
            return False
        return True

    async def on_message(self, msg):
        """Runs on every message"""
        if not self.hook_on_user_is_permitted(msg.author.name):
            return

        if msg.author == client.user:
            return
        if isinstance(msg.channel, discord.DMChannel):
            log.info(f"Received DM: {msg}")
        mem = self.guild.get_member(msg.author.id)
        if mem is None:
            log.info(
                f"Msg author {msg.author.name} ({msg.author.id}) not in PH server; ignoring"
            )
            return

        # print(f"Member {mem.display_name}: {mem.roles}")
        if msg.content.strip() == "TEST_MEMBER_JOIN":
            log.info("Running on_member_join hook function as requested")
            for a in self.member_join_hook_fn(self._member_details(mem)):
                await self.handle_hook_action(*a)


intents = discord.Intents.default()  # pylint: disable=invalid-name
intents.message_content = True
intents.dm_messages = True
intents.members = True
client = PHClient(intents=intents)  # pylint: disable=invalid-name


def run(member_join_hook_fn=None):
    """Run the bot"""
    log.info("Initializing discord bot")
    if member_join_hook_fn:
        client.member_join_hook_fn = member_join_hook_fn
    client.run(get_config("discord_bot/token"))


def get_client():
    """Fetches the bot instance"""
    return client


def invoke_sync(fn_name, *args, **kwargs):
    """Execute synchronous function on a running instance"""
    stored_loop = client.get_stored_loop()
    if stored_loop is None:
        raise RuntimeError("Discord bot client not initialized yet")
    return asyncio.run_coroutine_threadsafe(
        getattr(client, fn_name)(*args, **kwargs), stored_loop
    ).result()


def invoke_sync_generator(fn_name, *args, **kwargs):
    """Execute synchronous function yielding results from an async generator"""
    stored_loop = client.get_stored_loop()
    if stored_loop is None:
        raise RuntimeError("Discord bot client not initialized yet")

    async def wrapper():
        async for item in getattr(client, fn_name)(*args, **kwargs):
            yield item

    generator = wrapper()
    try:
        while True:
            yield asyncio.run_coroutine_threadsafe(
                generator.__anext__(), stored_loop
            ).result()
    except StopAsyncIteration:
        pass


if __name__ == "__main__":
    run()
