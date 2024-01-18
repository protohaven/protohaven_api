"""A bot for monitoring the Protohaven server and performing automated activities"""
import discord

from protohaven_api.config import get_config


class PHClient(discord.Client):
    """A discord bot that handles non-webhook tasks on the Protohaven discord server"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.role_map = {}

    @property
    def guild(self):
        """Fetches the guild name for the Protohaven server"""
        guild = self.get_guild(cfg["guild_id"])
        if guild is None:
            raise RuntimeError(f"Guild {cfg['guild_id']} not found")
        return guild

    @property
    def onboarding_channel(self):
        """Returns the onboarding channel ID"""
        chan = self.guild.get_channel(cfg["onboarding_channel_id"])
        if chan is None:
            raise RuntimeError(f"Channel {cfg['onboarding_channel_id']} not found")
        return chan

    async def on_ready(self):
        """Runs when the bot is connected and ready to go"""
        print(f"We have logged in as {self.user}")
        # role = guild.get_role(role_id)
        for r in self.guild.roles:
            self.role_map[r.name] = r
        print("Roles:", self.role_map)

    async def set_nickname(self, name, nickname):
        """Set the nickname of a named server member"""
        mem = self.guild.get_member_named(name)
        if mem is None:
            print("set_nickname: failed to find", name)
            return False
        try:
            await mem.edit(nick=nickname)
            return True
        except discord.HTTPException as e:
            print(str(e))
            return str(e)

    async def grant_role(self, name, role_name):
        """Grants a role (e.g. "Members") to a named server member"""
        mem = self.guild.get_member_named(name)
        if mem is None:
            print("Member", name, "not found")
            return False

        print("Adding role", role_name, "to", name)
        try:
            await mem.add_roles(self.role_map[role_name])
            return True
        except discord.HTTPException as e:
            print(str(e))
            return str(e)

    async def on_message(self, msg):
        """Runs on every message"""
        if msg.author == client.user:
            return
        if isinstance(msg.channel, discord.DMChannel):
            print(msg)
        # print(msg)
        # mem = self.guild.get_member(msg.author.id)
        # if mem is None:
        #    print("Msg author {msg.author.name} ({msg.author.id}) not in PH server")
        #    return
        # print(f"Member {mem.display_name}: {mem.roles}")

        # await message.channel.send('Hello!')


cfg = get_config()["discord_bot"]
intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True
intents.members = True

client = PHClient(intents=intents)


def run():
    """Run the bot"""
    print("Initializing discord bot")
    client.run(cfg["token"])


def get_client():
    """Fetches the bot instance"""
    return client


if __name__ == "__main__":
    run()
