import asyncio
from typing import Union
import discord
from discord.enums import MessageType

from . import util, static
from .static import *
from .util import *

class RichMessageSkeleton(RichMessage):
    """Class that represents a rich message after a bot restart. It preserves the data and static event handler attributes, and fetches the content at startup."""
    def __init__(self, content: str, embed: discord.Embed, eventHandler: str, channel: int, data: dict[Any, Any]):
        super().__init__()
        self.content = content
        self.embed = embed
        self.eventHandler = eventHandler
        self.channel = channel
        self.data = data

class MessageHandler:
    """Handles the input and output of messages related to the discord bot"""
    def __init__(self, bot): 
        self.ready = False
        self.bot = bot
        self.botID = bot.user.id # type: int
        self.pinsCache = {} # type: dict[int, set[int]]
        self.richMessages = {} # type: dict[int, RichMessage]

    async def sendMessage(self, message: Union[str, discord.Embed, RichMessage], channel: Union[discord.abc.PrivateChannel, discord.TextChannel, str, int]) -> discord.Message:
        """Sends the given message to the channel provided. If the channel is not a discord channel object, it will attempt to resolve it from the cache. The message can be a string, Embed, or RichMessage object, the last one being registered for event handling."""
        if not self.ready: await self.update()
        if channel is None: raise ValueError("Channel cannot be none")
        channel = self.bot.resolveChannel(channel)
        if channel is None: raise ValueError("Could not resolve channel when sending message")
        if isinstance(message, str): return await channel.send(content=message)
        elif isinstance(message, discord.Embed): return await channel.send(embed=message)
        elif isinstance(message, RichMessage):
            m = await channel.send(**(message.getMessage()))
            message.channel = channel.id
            self.richMessages[m.id] = message
            return m
        else: raise ValueError(f"Unknown message type {message}") 

    async def edit(self, message: Union[str, discord.Embed, RichMessage], messageObject: discord.Message) -> discord.Message:
        """Edits the message object with the given message, which can be either a str, Embed, or RichMesage. """
        if messageObject is None: raise ValueError("MessageObject cannot be None")

        if isinstance(message, str): await messageObject.edit(content=message, embed=None)
        elif isinstance(message, discord.Embed): await messageObject.edit(content=None, embed=message)
        elif isinstance(message, RichMessage):
            await messageObject.edit(**(message.getMessage()))
            message.channel = messageObject.channel.id
            self.richMessages[messageObject.id] = message
        else: raise ValueError(f"Unknown message type {message}") 
    
        if (not isinstance(message, RichMessage)) and messageObject.id in self.richMessages: del self.richMessages[messageObject.id]

        return messageObject

    async def update(self) -> None:
        """Update the message object with pins from all channels that can be seen and reconstructs the message cache from messages.json"""
        for c in self.bot.get_all_channels(): 
            if not isinstance(c, discord.TextChannel): continue
            y = await c.pins()
            if len(y) > 0: self.pinsCache[c.id] = set([x.id for x in y])
        for c in self.bot.private_channels: 
            y = await c.pins()
            if len(y) > 0: self.pinsCache[c.id] = set([x.id for x in y])

        a = loadJSON("messages.json")
        for x,y in a.items():
            m = await self.bot.resolveMessage(x, y["channel"], fetch=True)
            if m is None: 
                print(f'couldnt resolve {m}')
                continue
            y["content"] = m.content
            y["embed"] = m.embeds[0] if m.embeds else None
            y["channel"] = m.channel.id
            self.richMessages[int(str(x))] = RichMessageSkeleton(**y)
        
        self.ready = True

    async def onPinsUpdate(self, channel: Union[discord.abc.GuildChannel, discord.abc.PrivateChannel]) -> None: 
        """To be called when a channel updates its pins. Notifies any RichMessage objects if it was unpinned"""
        p = set([x.id for x in await channel.pins()])

        if channel.id not in self.pinsCache: 
            self.pinsCache[channel.id] = p
            return
        q = self.pinsCache[channel.id]

        for x in q.difference(p):
            if x in self.richMessages:
                if x in q: self.richMessages[x].onEvent(MessageUnpinEvent(), None)
        self.pinsCache[channel.id] = p

    async def onMessage(self, message: discord.Message) -> None: 
        """To be called when a message is sent. Notifies any RichMessage objects if replies occured or if it was pined."""
        if message.reference is None: return
        if message.reference.message_id not in self.richMessages: return
        if message.type == discord.MessageType.pins_add: 
            self.richMessages[message.reference.message_id].onEvent(MessagePinEvent(), message)
            if message.channel.id not in self.pinsCache: 
                self.pinsCache[message.channel.id] = set()
            self.pinsCache[message.channel.id].add(message.reference.message_id)
        else: self.richMessages[message.reference.message_id].onEvent(MessageReplyEvent(), message)

    def onMessageDelete(self, payload: Union[discord.RawMessageDeleteEvent, discord.RawBulkMessageDeleteEvent]) -> None: 
        """To be called when a message is deleted. Notifies any RichMessage objects if it was deleted."""
        l = []
        if isinstance(payload, discord.RawMessageDeleteEvent): l.append(payload.message_id)
        elif isinstance(payload, discord.RawBulkMessageDeleteEvent): l.extend(payload.message_ids)
        for x in l: 
            if x in self.richMessages: self.richMessages[x].onEvent(payload, None)

    def onReactionActionEvent(self, payload: discord.RawReactionActionEvent) -> None: 
        """To be called when reactions occur. Notifies any RichMessage objects if it was the target."""
        if payload.message_id in self.richMessages: self.richMessages[payload.message_id].onEvent(payload, None)

    def onReactionClearEmojiEvent(self, payload: discord.RawReactionClearEmojiEvent) -> None: 
        """To be called when a reaction emoji was cleared. Notifies any RichMessage objects if it was the target."""
        if payload.message_id in self.richMessages: self.richMessages[payload.message_id].onEvent(payload, None)

    def onReactionClearEvent(self, payload: discord.RawReactionClearEvent) -> None: 
        """To be called when reactions were cleared. Notifies any RichMessage objects if it was the target."""
        if payload.message_id in self.richMessages: self.richMessages[payload.message_id].onEvent(payload, None)

    def save(self) -> None: 
        """Saves the messages to messages.json so it can be reconstructed from the file"""
        d = {}
        for k,v in self.richMessages.items():
            if v.eventHandler == None: continue
            a = {}
            a["eventHandler"] = v.eventHandler
            a["channel"] = v.channel
            a["data"] = v.data
            d[k] = a
        saveJSON(d, "messages.json")
