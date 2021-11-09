import discord

from . import util, static
from .util import *
from .static import *

class DiscordEvents:
    """A static class that contains all events that the discord module provides."""

    # The following events are not passed on to this class, and instead should be handled by the bot class
    async def on_connect(bot): pass
    async def on_shard_connect(bot, shard_id): pass
    async def on_disconnect(bot): pass
    async def on_shard_disconnect(bot, shard_id): pass
    async def on_ready(bot): pass
    async def on_shard_ready(bot, shard_id): pass
    async def on_resumed(bot): pass
    async def on_shard_resumed(bot, shard_id): pass
    async def on_error(bot, event, *args, **kwargs): pass    

    # Events that are passed to this class
    async def on_message(bot, message: discord.Message):
        """Discord event. Checks if the given message is a valid command to respond to."""

        # First, notify the message handler of the message
        await bot.messageHandler.onMessage(message)

        handleCommand = False
        if message.author == bot.user or message.type != discord.MessageType.default:
            return

        # If the message was sent through a DM, always attempt to handle the command
        if message.channel.type == discord.ChannelType.private: 
            handleCommand = True

        # Check the server context rules to see if the bot should handle the command
        if handleCommand is False and message.channel.id in bot.getContext(message.guild).settings['channellist']: handleCommand = bot.getContext(message.guild).settings['channellistiswhitelist']
        elif handleCommand is False and (message.content.startswith(bot.user.mention) or message.content.startswith(bot.getContext(message.guild).settings['commandprefix'])): handleCommand = True

        # If applicable, send the command to the command handler
        if not handleCommand: return
        await bot.on_command(message)

    async def on_guild_join(bot, guild: discord.Guild):
        """Discord event. Creates a context for the given guild"""
        bot.guildIDs.add(guild.id)
        await bot.getContext(guild).update(guild)

    async def on_guild_leave(bot, guild: discord.Guild): 
        """Discord event. Removes the guild from the list to handle from and removes any contexts that exists in DM."""
        bot.guildIDs.discard(guild.id)
        for k,v in bot.getDMContexts:
            if v.guildID == guild.id:
                bot.resolveChannel(k).send(f"I have left the server `{guild.name}`. You are no longer able to send server commands there.")
                bot.setDMContext(k, None)

    async def on_invite_create(bot, invite: discord.Invite):
        """Discord event. Used to track who invited whom"""
        bot.getContext(invite.guild).inviteCache[invite.code] = 0

    async def on_invite_delete(bot, invite: discord.Invite):
        """Discord event. Used to track who invited whom"""
        del bot.getContext(invite.guild).inviteCache[invite.code]

    async def on_member_join(bot, member: discord.Member):
        """Discord event. Uses cached invites to check who the user was invited by"""
        channel = bot.getContext(member.guild.id).settings["invitedlog"]
        newinvites = await member.guild.invites()
        for x in newinvites: 
            if x.uses > bot.getContext(member.guild).inviteCache[x.code]:
                usedinvite = x
                bot.getContext(member.guild).inviteCache[x.code] = x.uses
        if channel is None: return
        await member.guild.get_channel(channel).send(f"Welcome {member.mention}, invited using <{usedinvite.url}> by {usedinvite.inviter.mention}")

    async def on_member_update(bot, before: discord.Member, after: discord.Member): 
        if after.id in bot.dmContexts:
            if bot.getDMContext(after) is None:
                bot.resolveChannel(after).send(f"You no longer have permission to send server commands to `{after.guild.name}`")
                bot.setDMContext(after, None)

    async def on_guild_role_update(bot, before: discord.Guild, after: discord.Guild): 
        for x in after.members:
            await DiscordEvents.on_member_update(bot, x, x)

    # Events that only notify the message handler
    async def on_raw_message_delete(bot, payload: discord.RawMessageDeleteEvent): bot.messageHandler.onMessageDelete(payload)
    async def on_raw_bulk_message_delete(bot, payload: discord.RawBulkMessageDeleteEvent): bot.messageHandler.onMessageDelete(payload)
    async def on_raw_reaction_add(bot, payload: discord.RawReactionActionEvent): bot.messageHandler.onReactionActionEvent(payload)
    async def on_raw_reaction_remove(bot, payload: discord.RawReactionActionEvent): bot.messageHandler.onReactionActionEvent(payload)
    async def on_raw_reaction_clear(bot, payload: discord.RawReactionClearEvent): bot.messageHandler.onReactionClearEmojiEvent(payload)
    async def on_raw_reaction_clear_emoji(bot, payload: discord.RawReactionClearEmojiEvent): bot.messageHandler.onReactionClearEvent(payload)
    async def on_private_channel_pins_update(bot, channel: discord.abc.PrivateChannel, last_pin: Optional[datetime.datetime]): await bot.messageHandler.onPinsUpdate(channel)
    async def on_guild_channel_pins_update(bot, channel: discord.abc.GuildChannel, last_pin: Optional[datetime.datetime]): await bot.messageHandler.onPinsUpdate(channel)

    # Events that are generally passed to this class but are not implemented
    async def on_typing(bot, channel, user, when): pass
    async def on_message_delete(bot, message): pass
    async def on_bulk_message_delete(bot, messages): pass
    async def on_message_edit(bot, before, after): pass
    async def on_raw_message_edit(bot, payload): pass
    async def on_reaction_add(bot, reaction, user): pass
    async def on_reaction_remove(bot, reaction, user): pass
    async def on_reaction_clear(bot, message, reactions): pass
    async def on_reaction_clear_emoji(bot, reaction): pass
    async def on_private_channel_delete(bot, channel): pass
    async def on_private_channel_create(bot, channel): pass
    async def on_private_channel_update(bot, before, after): pass
    async def on_guild_channel_delete(bot, channel): pass
    async def on_guild_channel_create(bot, channel): pass
    async def on_guild_channel_update(bot, before, after): pass
    async def on_guild_integrations_update(bot, guild): pass
    async def on_webhooks_update(bot, channel): pass
    async def on_member_remove(bot, member): pass
    async def on_user_update(bot, before, after): pass
    async def on_guild_update(bot, before, after): pass
    async def on_guild_role_create(bot, role): pass
    async def on_guild_role_delete(bot, role): pass
    async def on_guild_emojis_update(bot, guild, before, after): pass
    async def on_guild_available(bot, guild): pass
    async def on_guild_unavailable(bot, guild): pass
    async def on_voice_state_update(bot, member, before, after): pass
    async def on_member_ban(bot, guild, user): pass
    async def on_member_unban(bot, guild, user): pass