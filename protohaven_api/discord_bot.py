"""A bot for monitoring the Protohaven server and performing automated activities"""
import logging

import discord

from protohaven_api.config import get_config

log = logging.getLogger("discord_bot")


class PHClient(discord.Client):
    """A discord bot that handles non-webhook tasks on the Protohaven discord server"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.role_map = {}

    @property
    def cfg(self):
        """Fetches the bot config"""
        return get_config()["discord_bot"]

    @property
    def guild(self):
        """Fetches the guild name for the Protohaven server"""
        guild = self.get_guild(self.cfg["guild_id"])
        if guild is None:
            raise RuntimeError(f"Guild {self.cfg['guild_id']} not found")
        return guild

    @property
    def onboarding_channel(self):
        """Returns the onboarding channel ID"""
        chan = self.guild.get_channel(self.cfg["onboarding_channel_id"])
        if chan is None:
            raise RuntimeError(f"Channel {self.cfg['onboarding_channel_id']} not found")
        return chan

    async def on_ready(self):
        """Runs when the bot is connected and ready to go"""
        log.info(f"We have logged in as {self.user}")
        # role = guild.get_role(role_id)
        for r in self.guild.roles:
            self.role_map[r.name] = r
        log.info(f"Roles: {self.role_map}")

    async def on_member_join(self, member):
        """Runs when a new member joins the server"""
        # channel = get(member.guild.channels, id=768670193379049483)
        # await channel.send(f'{member} welcome')

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

    async def grant_role(self, name, role_name):
        """Grants a role (e.g. "Members") to a named server member"""
        mem = self.guild.get_member_named(name)
        if mem is None:
            log.info("Discord user {name} not found")
            return False

        log.info(f"Adding role {role_name} to {name}")
        try:
            await mem.add_roles(self.role_map[role_name])
            return True
        except discord.HTTPException as e:
            log.error(str(e))
            return str(e)

    async def get_all_members_and_roles(self):
        """Retrieves all data on members and roles for the server"""
        return {
            "members": [
                (m.name, m.display_name, [(r.name, r.id) for r in m.roles])
                for m in self.guild.members
            ],
            "role_map": self.role_map,
        }

    async def on_message(self, msg):
        """Runs on every message"""
        if msg.author == client.user:
            return
        if isinstance(msg.channel, discord.DMChannel):
            log.info(f"Received DM: {msg}")
        # print(msg)
        # mem = self.guild.get_member(msg.author.id)
        # if mem is None:
        #    print("Msg author {msg.author.name} ({msg.author.id}) not in PH server")
        #    return
        # print(f"Member {mem.display_name}: {mem.roles}")

        # await message.channel.send('Hello!')


client = None  # pylint: disable=invalid-name


def run():
    """Run the bot"""
    global client  # pylint: disable=global-statement

    log.info("Initializing discord bot")
    intents = discord.Intents.default()
    intents.message_content = True
    intents.dm_messages = True
    intents.members = True
    client = PHClient(intents=intents)
    client.run(get_config()["discord_bot"]["token"])


def get_client():
    """Fetches the bot instance"""
    return client


if __name__ == "__main__":
    run()
