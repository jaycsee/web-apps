import discord
import os
import json
import importlib
from typing import Any, Union, List, NoReturn, Optional

from . import util, commands, events, messages, static
from .static import *
from .util import *

tokens = {}

# todos
# new commands: voice split/lock/hide/move
# permissions (caching) -> finish infrastructure -> granular permissions
# disable on 403
# slash commands
# send to mod log if mod sends a command on the server and the mod is not a custodian
# better logging

owner = "331093435282882562"
admin = set(loadJSON("custodians.json")) # type: set[str]
context = {}

def isBotCustodian(user: Any) -> bool:
    """Returns if the given user is a custodian (admin) of the application"""
    if isinstance(user, discord.abc.User): user = user.id
    return isBotOwner(user) or str(user) in admin

def isBotOwner(user: Any) -> bool:
    """Returns if the given user is the owner of the application"""
    if isinstance(user, discord.abc.User): user = user.id
    return str(user) == owner

class Deployment(discord.Client):
    owner = owner
    admin = admin
    isBotOwner = lambda a,b=None: isBotOwner(a) or isBotOwner(b)
    isBotCustodian = lambda a,b=None: isBotCustodian(a) or isBotCustodian(b)

    def __init__(self, manager, token: str):
        super().__init__(intents=discord.Intents.all())
        self.manager = manager 
        if token in tokens: token = tokens[token]
        self.token = token

    def deploy(self) -> None:
        """Blocking call that deploys the bot with the given token. Returns after shutdown is called. """
        self.run(self.token)

    async def on_ready(self) -> None:
        """Discord event. Prepares all aspects of the bot after connect and login"""
        print(f"Successful login as {self.user}")
        self.manager.signalRunning()
        self.prepareCommands()
        print("Initializing guilds and contexts:")
        self.guildIDs = set()
        if "settings" not in os.listdir(): os.mkdir("settings")
        for x in self.guilds:
            print(f" - {x.name} ({x.id}) owned by {x.owner_id}")
            await self.on_guild_join(x)
        self.dmContexts = {}
        for k,v in loadJSON("dmcontexts.json").items():
            self.setDMContext(k, v)

        self.messageHandler = messages.MessageHandler(self)
        await self.messageHandler.update()

    def reload(self, module: str, raw: bool=False) -> bool:
        """Reloads and updates a module of the bot. Could be either 'commands', 'events' or 'all'. Returns whether the update was successful. Can be called after bot shutdown."""
        if module.lower() == "commands": 
            importlib.reload(commands)
            if not raw: self.prepareCommands()
            return True
        elif module.lower() == "events": return bool(importlib.reload(events))
        elif module.lower() == "messages": 
            x = bool(importlib.reload(messages))
            if x is False: return False
            a = self.messageHandler.pinsCache
            b = self.messageHandler.richMessages
            self.messageHandler = messages.MessageHandler(self)
            self.messageHandler.pinsCache = a
            self.messageHandler.richMessages = b
            return True
        elif module.lower() == "all":
            importlib.reload(util)
            self.reload("commands", raw)
            self.reload("events", raw)
            self.reload("messages", raw)
        else: return False

    def prepareCommands(self) -> None:
        """Initializes commands to use in the discord bot. Calling this command again finds new commands that the bot can handle."""
        print("Initializing commands:")
        self.generalCommandList = set() # type: set[str]
        self.serverCommandList = set() # type: set[str]
        self.privilegedCommandList = set() # type: set[str]
        for x in dir(commands.GeneralCommands):
            if x.startswith("command_") and len(x) > 8: 
                self.generalCommandList.add(x)
                print(" - Found general command: " + x[8:])
        for x in dir(commands.ServerCommands):
            if x.startswith("command_") and len(x) > 8: 
                self.serverCommandList.add(x)
                print(" - Found server command: " + x[8:])
        for x in dir(commands.PrivilegedCommands):
            if x.startswith("command_") and len(x) > 8: 
                self.privilegedCommandList.add(x)
                print(" - Found privileged command: " + x[8:])

    async def shutdown(self) -> None:
        """Shuts down the bot and writes all necessary objects to disk"""
        await self.close()
        saveJSON(self.dmContexts, "dmcontexts.json")
        saveJSON(list(admin), "custodians.json")
        if "settings" not in os.listdir(): os.mkdir("settings")
        for k,v in context.items(): saveJSON(v.settings, f"settings/{k}.json")
        self.messageHandler.save()

    def getContexts(self) -> dict[int, ServerContext]:
        """Returns all server contexts"""
        return context

    def getContext(self, guild: Any) -> ServerContext:
        """Returns a specific server context, creating it if it does not exist. The given guild may be either Guild, or an id (int or str). Raises ValueError if the guild cannot be resolved or when the bot is not a member of the requested guild."""
        if isinstance(guild, str) or isinstance(guild, int): guild = self.resolveGuild(int(str(guild)))
        if guild is None or guild.id not in self.guildIDs: raise ValueError('Could not resolve guild')
        if guild.id not in context: context[guild.id] = ServerContext(bot=self, guild=guild)
        return context[guild.id]

    def getDMContexts(self) -> dict[int, ServerContext]:
        """Returns all DM contexts""" 
        return self.dmContexts
    
    def getDMContext(self, user: Any) -> Optional[ServerContext]:
        """Returns a specific server context in a specific user's DM. The given guild may be either Guild, or an id (int or str)."""
        if isinstance(user, str) or isinstance(user, int): guild = self.get_user(int(str(user)))
        if user is None or user.id not in self.dmContexts or self.dmContexts[user.id] is None: return None
        r = self.getContext(self.dmContexts[user.id])
        if not r.isModerator(user): return None
        return r

    def setDMContext(self, user: Any, context: Any) -> bool:
        """Sets the user's DM to a server context. Returns whether the user is authorized and the context is set."""
        user = self.resolveUser(user)
        if user is None: return False
        if not isinstance(context, ServerContext): 
            try: context = self.getContext(context)
            except Exception: pass
        if context is None: 
            if user.id not in self.dmContexts: return False
            del self.dmContexts[user.id]
            return True
        if not context.isModerator(user): return False
        self.dmContexts[user.id] = context.guildID
        return True

    def resolveGuild(self, guild: Any) -> Optional[discord.Guild]:
        """Returns a guild based on the hint provided by guild. Returns None if it cannot be resolved"""
        if isinstance(guild, discord.Guild): return guild
        if isinstance(guild, discord.Member) or isinstance(guild, discord.abc.GuildChannel) or isinstance(guild, discord.Message): return guild.guild

        if isinstance(guild, int) or (isinstance(guild, str) and guild.isdecimal()): 
            x = self.get_guild(int(str(guild)))
            if x is not None: return x

        x = self.resolveChannel(guild)
        if x is not None: return x.guild
        return None

    def resolveGuildByName(self, guild: Any) -> List[discord.Guild]:
        """Returns a list of guilds based on the hint or name provided by guild. Returns an empty list if it cannot be resolved"""
        x = self.resolveGuild(guild)
        if x is not None: return [x]
        guild = str(guild).lower()
        return [g for g in self.guilds if g.name.lower() == guild]

    def resolveChannel(self, channel: Any) -> Optional[Union[discord.abc.GuildChannel, discord.abc.PrivateChannel]]:
        """Returns a channel based on the hint provided by channel. Returns None if it cannot be resolved"""
        if isinstance(channel, discord.abc.GuildChannel) or isinstance(channel, discord.abc.PrivateChannel): return channel
        if isinstance(channel, discord.Message): return channel.channel
        if isinstance(channel, discord.User) or isinstance(channel, discord.Member): return channel.dm_channel

        if isinstance(channel, int) or (isinstance(channel, str) and channel.isdecimal()): 
            x = self.get_channel(int(str(channel)))
            if x is not None: return x

        x = self.resolveUser(channel)
        if x is not None: return x.dm_channel
        return None

    def resolveChannelByName(self, channel: Any) -> List[Union[discord.abc.GuildChannel, discord.abc.PrivateChannel]]:
        """Returns a discord.abc.GuildChannel or discord.abc.PrivateChannel based on the hint or name provided by channel. Returns an empty list if it cannot be resolved"""
        x = self.resolveChannel(channel)
        if x is not None: return [x]
        channel = str(channel).lower()
        return [c for g in self.guilds for c in g if c.name.lower() == channel]

    def resolveUser(self, user: Any) -> Optional[discord.abc.User]:
        """Returns a discord.User based on the hint provided by user. Returns None if it cannot be resolved"""
        if isinstance(user, discord.abc.User): return user
        if isinstance(user, discord.Message): return user.author

        if isinstance(user, int) or (isinstance(user, str) and user.isdecimal()): 
            x = self.get_user(int(str(user)))
            if x is not None: return x

        return None

    def resolveUserByName(self, user: Any) -> List[discord.abc.User]:
        """Returns a user based on the hint or name provided by user. Returns an empty list if it cannot be resolved"""
        x = self.resolveUser(user)
        if x is not None: return x
        user = str(user).lower()
        return [u for u in self.get_all_members() if str(u) == user or u.name == user]

    def resolveMember(self, user: Any, guild: Any) -> Optional[discord.Member]:
        """Returns a member based on the hint provided by user and guild. Returns None if it cannot be resolved"""
        user = self.resolveUser(user)
        guild = self.resolveGuild(guild)
        if user is None or guild is None: return None
        return guild.get_member(user.id)

    async def resolveMemberByName(self, user: Any, guild: Any) -> List[discord.Member]:
        """Returns members based on the hints or names provided by user and guild. Returns an empty list if it cannot be resolved"""
        guild = self.resolveGuildByName(guild)
        x = self.resolveUser(user)
        user = str(user)
        if guild is None: return None
        if x: return guild.get_member(x.id)
        elif "#" in x: return guild.get_member_named(user)
        else: return await guild.query_members(query=user)

    async def resolveMessage(self, message: Any, channel: Any, fetch: bool=False) -> Optional[discord.Message]:
        """Returns a discord.Message based on the id provided by message and the hint provided by channel. Returns None if it cannot be resolved."""
        if isinstance(message, discord.Message): return message
        c = self.resolveChannel(channel)
        if c is None and fetch and (isinstance(channel, int) or (isinstance(channel, str) and channel.isdecimal())): 
            channel = await self.fetch_channel(int(str(channel)))
        else: channel = c
        if channel is None: return None
        message = str(message)
        if not message.isdecimal(): return None
        return await channel.fetch_message(int(str(message)))

    def resolveObject(self, object: Any) -> Optional[discord.abc.Snowflake]:
        """Returns a discord.abc.Snowflake based on the hint provided by object. Returns None if it cannot be resolved. Should not be used under normal circumstances; use a more specific resolution function"""
        if isinstance(object, discord.abc.Snowflake): return object
        x = self.resolveUser(object)
        if x is not None: return x
        x = self.resolveGuild(object)
        if x is not None: return x
        x = self.resolveChannel(object)
        if x is not None: return x
        return None

    async def on_command(self, message: discord.Message) -> None:
        """Attempt to handle a command from the message."""
        
        content = message.content.lstrip(self.user.mention)
        if message.channel.type != discord.ChannelType.private: content = content.lstrip(self.getContext(message.guild).settings["commandprefix"])
        content = content.strip().split(" ", maxsplit=1)

        user = message.author
        name = content[0].strip().lower()
        parameters = content[1].strip() if len(content) > 1 else ""

        # Attempt to get the specific context, either from the server or a DM
        if message.channel.type == discord.ChannelType.private: currentContext = self.getDMContext(user)
        else: currentContext = self.getContext(message.guild) 

        # Call the command
        await self.call_command(CommandEvent(self, currentContext, user, message, name, parameters))
        # TODO: if valid command and dm, modlog?
        return

    async def call_command(self, event: CommandEvent, triggerTyping: bool=True) -> bool:
        """Attempts to handle a command with the given event. trigerTyping is used to indicate if typing should be triggered in the channel that sent the event. Returns if a valid command was handled."""
        if event is None: return
        
        # Helper function, called to run a specific commnad
        async def call(cls, qualname: str, event: CommandEvent):
            if triggerTyping: await event.message.channel.trigger_typing()
            ret = await getattr(cls, qualname)(event)
            if ret is not None: await event.sendResponse(ret, finished=True)

        qualname = "command_" + event.name 
        # Attempt to run a prvileged command, checking if the user is authorized
        if self.isBotCustodian(event.message.author) and qualname in self.privilegedCommandList: 
            await call(commands.PrivilegedCommands, qualname, event)
            return True
        # Attempt to run a general command
        if qualname in self.generalCommandList: 
            await call(commands.GeneralCommands, qualname, event)
            return True

        # Running server commands requires context to be set. If it cannot find the context, treat it as an unknown command.
        if event.context is None and event.message.channel.type == discord.ChannelType.private: 
            await event.sendResponse("Unknown command. To send server commands in DMs, use `auth` and specify a server.")
            return False
        elif event.context is None: return False

        # Attempt to run a server command
        if qualname in self.serverCommandList: 
            await call(commands.ServerCommands, qualname, event)
            return True

        # Unknown command
        if event.message.channel.type == discord.ChannelType.private: await event.sendResponse("Unknown command. Commands in DMs must not be prefixed.")
        return False
    
    # Pass relevant discord events
    async def on_typing(self, channel, user, when): return await events.DiscordEvents.on_typing(self, channel, user, when)
    async def on_message(self, message): return await events.DiscordEvents.on_message(self, message)
    async def on_message_delete(self, message): return await events.DiscordEvents.on_message_delete(self, message)
    async def on_bulk_message_delete(self, messages): return await events.DiscordEvents.on_bulk_message_delete(self, messages)
    async def on_raw_message_delete(self, payload): return await events.DiscordEvents.on_raw_message_delete(self, payload)
    async def on_raw_bulk_message_delete(self, payload): return await events.DiscordEvents.on_raw_bulk_message_delete(self, payload)
    async def on_message_edit(self, before, after): return await events.DiscordEvents.on_message_edit(self, before, after)
    async def on_raw_message_edit(self, payload): return await events.DiscordEvents.on_raw_message_edit(self, payload)
    async def on_reaction_add(self, reaction, user): return await events.DiscordEvents.on_reaction_add(self, reaction, user)
    async def on_raw_reaction_add(self, payload): return await events.DiscordEvents.on_raw_reaction_add(self, payload)
    async def on_reaction_remove(self, reaction, user): return await events.DiscordEvents.on_reaction_remove(self, reaction, user)
    async def on_raw_reaction_remove(self, payload): return await events.DiscordEvents.on_raw_reaction_remove(self, payload)
    async def on_reaction_clear(self, message, reactions): return await events.DiscordEvents.on_reaction_clear(self, message, reactions)
    async def on_raw_reaction_clear(self, payload): return await events.DiscordEvents.on_raw_reaction_clear(self, payload)
    async def on_reaction_clear_emoji(self, reaction): return await events.DiscordEvents.on_reaction_clear_emoji(self, reaction)
    async def on_raw_reaction_clear_emoji(self, payload): return await events.DiscordEvents.on_raw_reaction_clear_emoji(self, payload)
    async def on_private_channel_delete(self, channel): return await events.DiscordEvents.on_private_channel_delete(self, channel)
    async def on_private_channel_create(self, channel): return await events.DiscordEvents.on_private_channel_create(self, channel)
    async def on_private_channel_update(self, before, after): return await events.DiscordEvents.on_private_channel_update(self, before, after)
    async def on_private_channel_pins_update(self, channel, last_pin): return await events.DiscordEvents.on_private_channel_pins_update(self, channel, last_pin)
    async def on_guild_channel_delete(self, channel): return await events.DiscordEvents.on_guild_channel_delete(self, channel)
    async def on_guild_channel_create(self, channel): return await events.DiscordEvents.on_guild_channel_create(self, channel)
    async def on_guild_channel_update(self, before, after): return await events.DiscordEvents.on_guild_channel_update(self, before, after)
    async def on_guild_channel_pins_update(self, channel, last_pin): return await events.DiscordEvents.on_guild_channel_pins_update(self, channel, last_pin)
    async def on_guild_integrations_update(self, guild): return await events.DiscordEvents.on_guild_integrations_update(self, guild)
    async def on_webhooks_update(self, channel): return await events.DiscordEvents.on_webhooks_update(self, channel)
    async def on_member_join(self, member): return await events.DiscordEvents.on_member_join(self, member)
    async def on_member_remove(self, member): return await events.DiscordEvents.on_member_remove(self, member)
    async def on_member_update(self, before, after): return await events.DiscordEvents.on_member_update(self, before, after)
    async def on_user_update(self, before, after): return await events.DiscordEvents.on_user_update(self, before, after)
    async def on_guild_join(self, guild): return await events.DiscordEvents.on_guild_join(self, guild)
    async def on_guild_remove(self, guild): return await events.DiscordEvents.on_guild_remove(self, guild)
    async def on_guild_update(self, before, after): return await events.DiscordEvents.on_guild_update(self, before, after)
    async def on_guild_role_create(self, role): return await events.DiscordEvents.on_guild_role_create(self, role)
    async def on_guild_role_delete(self, role): return await events.DiscordEvents.on_guild_role_delete(self, role)
    async def on_guild_role_update(self, before, after): return await events.DiscordEvents.on_guild_role_update(self, before, after)
    async def on_guild_emojis_update(self, guild, before, after): return await events.DiscordEvents.on_guild_emojis_update(self, guild, before, after)
    async def on_guild_available(self, guild): return await events.DiscordEvents.on_guild_available(self, guild)
    async def on_guild_unavailable(self, guild): return await events.DiscordEvents.on_guild_unavailable(self, guild)
    async def on_voice_state_update(self, member, before, after): return await events.DiscordEvents.on_voice_state_update(self, member, before, after)
    async def on_member_ban(self, guild, user): return await events.DiscordEvents.on_member_ban(self, guild, user)
    async def on_member_unban(self, guild, user): return await events.DiscordEvents.on_member_unban(self, guild, user)
    async def on_invite_create(self, invite): return await events.DiscordEvents.on_invite_create(self, invite)
    async def on_invite_delete(self, invite): return await events.DiscordEvents.on_invite_delete(self, invite)