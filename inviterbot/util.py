import discord
import os
import json
import datetime
import traceback

from typing import Any, Optional, Union

# from . import static
# from .static import *

from static import *

def loadJSON(file: str) -> dict:
    file = "discordbot/" + file
    if os.path.isfile(file):
        try:
            with open(file) as f:
                x = json.load(f)
                return x
        except Exception:
            print("\n")
            traceback.print_exc()
            print("\n")
    return {}

def saveJSON(object: Any, file) -> None:
    with open("discordbot/" + file,"w") as f: json.dump(object, f, indent=2)

def ensureSize(message: Union[str, discord.Embed]) -> Union[str, discord.Embed]:
    if message is None: return message
    elif isinstance(message, str): return (message[:1995] + "...") if len(message) > 1998 else message
    elif isinstance(message, discord.Embed):
        embed = message
        if len(embed.author.name) > 256: embed.set_author(name=(embed.author.name[:250] + "..."), url=embed.author.url, icon_url=embed.author.icon_url)
        if len(embed.title) > 253: embed.title = embed.title[250] + "..."
        if len(embed.footer.text) > 1000: embed.title = embed.set_footer(text=embed.footer.text[:999], icon_url=discord.footer.icon_url)
        if len(embed) > 5995: 
            s = 5900 - (len(embed) - len(embed.description))
            embed.description = embed.description[:s]
        return embed
    return message

class ServerContext:
    """Data class for a specific server"""
    def __init__(self, bot, guild: discord.Guild):
        """Initializes a data class for a given guild, which must not be None. It will attempt to retrieve settings from settings/{id}.json"""
        if guild is None: raise ValueError("Guild must not be None")
        self.bot = bot
        self.guildID = guild.id
        self.serverOwner = str(guild.owner_id)
        self.inviteCache = {} # type: dict[str, Any]
        self.settings = {} # type: dict[str, Any]
        self.settings["commandprefix"] = "//"
        self.settings["channellist"] = []
        self.settings["channellistiswhitelist"] = False
        self.settings["modchannellist"] = []
        self.settings["modlog"] = None
        self.settings["invitelog"] = None
        self.settings["invitedlog"] = None

        x = loadJSON(f"settings/{guild.id}.json")
        for k in x:
            self.settings[k] = x[k]    
    
    async def update(self, guild: discord.Guild) -> None:
        """Updates the data object with the guild object provided, which must not be None"""
        if guild is None: raise ValueError("Guild must not be None")
        self.serverOwner = str(guild.owner_id)
        invites = await guild.invites()
        self.inviteCache.clear()
        for i in invites:
            self.inviteCache[i.code] = i.uses
            # update role heirarchy

    def isModerator(self, user: Any) -> bool:
        """Checks if the given user has moderator privileges in the given server""" 
        return self.bot.isBotOwner(user)
        # kick man move etc

    def isAdministrator(self, user: Any) -> bool:
        """Checks if the given user has administrator privileges in the given server""" 
        return self.bot.isBotOwner(user)
        # settings change

    def isOwner(self, user: Any) -> bool:
        return str(user.id) == self.serverOwner

    def canModerate(self, user: Any, target: Any) -> bool:
        """Checks if the given user has moderator privileges over a certain user (is higher up on the heirarchy)"""
        if self.isModerator(user) or str(user.id) == self.serverOwner: return True
        # incomplete
        pass

# make this a message builder with onreact handles
class EmbedBuilder:
    """A helper class designed to build an embed"""
    def __init__(self): self.embed = discord.Embed()

    def setColour(self, colour): return self.setColor(colour)
    def setColor(self, color): 
        self.embed.color = color
        return self

    def setHeaderUser(self, user):
        if isinstance(user, int) or isinstance(user, str): user = self.embed.get_user(int(str(user)))
        if user is None: self.embed.remove_author()
        self.embed.set_author(name=f"{user.name}#{user.discriminator}", icon_url=user.avatar_url_as())
        return self

    def setHeader(self, *, url=discord.Embed.Empty, name=discord.Embed.Empty, text=discord.Embed.Empty, icon_url=discord.Embed.Empty, ): 
        if name is discord.Embed.Empty: name = text
        self.embed.set_author(name=name, url=url, icon_url=icon_url)
        return self

    def setTitle(self, title):
        self.embed.title = title
        return self

    def setDescription(self, desc):
        self.embed.description = desc
        return self

    def setFooterUser(self, user):
        if isinstance(user, int) or isinstance(user, str): user = self.embed.get_user(int(str(user)))
        if user is None: self.embed.set_footer()
        self.embed.set_footer(text=f"{user.name}#{user.discriminator}", icon_url=user.avatar_url_as())

    def setFooter(self, *, text=discord.Embed.Empty, icon_url=discord.Embed.Empty): return self.embed.set_footer(text=text, icon_url=icon_url)

    def setTimeNow(self): 
        self.embed.timestamp = datetime.datetime.now()
        return self

    def setTime(self, time):
        self.embed.timestamp = time
        return self

    def build(self): return self.embed

class MessagePinEvent: pass
class MessageUnpinEvent: pass
class MessageReplyEvent: pass
class RichMessage:
    """A class that contains a message with content and embed, and defines behaviour on reactions"""

    def __init__(self):
        self.content = None # type: str
        self.embed = None # type: discord.Embed
        self.eventHandler = None # type: str

        self.data = {} # type: dict[Any, Any]

        self.channel = None # type: int

    def getContent(self) -> str: 
        """Returns the string content of the message"""
        return self.content
    def getEmbed(self) -> discord.Embed: 
        """Returns the embed content of the message"""
        return self.embed

    def getMessage(self) -> dict[str, Union[str, discord.Embed]]: 
        """Returns a dictionary representation of the content and embed"""
        return {"content": self.content, "embed": self.embed}

    def setContent(self, content: str) -> "RichMessage": 
        """Sets the content of the message"""
        self.content = content
        return self
    def setEmbed(self, embed: discord.Embed) -> "RichMessage":
        """Sets the embed of the message"""
        self.embed = embed
        return self

    def setEmbedColour(self, colour: int) -> "RichMessage": return self.setEmbedColor(colour)
    def setEmbedColor(self, color: int) -> "RichMessage": 
        """Sets the embed color to the given hex"""
        if self.embed is None: self.embed = discord.Embed()
        self.embed.color = color
        return self

    def setEmbedHeaderUser(self, user: discord.abc.User) -> "RichMessage":
        """Sets the embed header/author to the name and avatar of a given discord.abc.User"""
        if self.embed is None: self.embed = discord.Embed()
        if isinstance(user, int) or isinstance(user, str): user = self.embed.get_user(int(str(user)))
        if user is None: self.embed.remove_author()
        self.embed.set_author(name=f"{user.name}#{user.discriminator}", icon_url=user.avatar_url_as())
        return self

    def setEmbedHeader(self, *, url: str=discord.Embed.Empty, name: str=discord.Embed.Empty, text: str=discord.Embed.Empty, icon_url: str=discord.Embed.Empty) -> "RichMessage": 
        """Sets the embed header/author to the text, url and icon"""
        if self.embed is None: self.embed = discord.Embed()
        if name is discord.Embed.Empty: name = text
        self.embed.set_author(name=name, url=url, icon_url=icon_url)
        return self

    def setEmbedTitle(self, title: str) -> "RichMessage":
        """Sets the embed title"""
        if self.embed is None: self.embed = discord.Embed()
        self.embed.title = title
        return self

    def setEmbedDescription(self, desc: str) -> "RichMessage":
        """Sets the embed descrption"""
        if self.embed is None: self.embed = discord.Embed()
        self.embed.description = desc
        return self

    def setEmbedFooterUser(self, user: discord.abc.User) -> "RichMessage":
        """Sets the embed footer to the name and avatar of a given discord.abc.User"""
        if self.embed is None: self.embed = discord.Embed()
        if isinstance(user, int) or isinstance(user, str): user = self.embed.get_user(int(str(user)))
        if user is None: self.embed.set_footer()
        self.embed.set_footer(text=f"{user.name}#{user.discriminator}", icon_url=user.avatar_url_as())
        return self

    def setEmbedFooter(self, *, text=discord.Embed.Empty, icon_url=discord.Embed.Empty) -> "RichMessage": 
        """Sets the embed footer to the text, url and icon"""
        if self.embed is None: self.embed = discord.Embed()
        self.embed.set_footer(text=text, icon_url=icon_url)
        return self

    def setEmbedTimeNow(self) -> "RichMessage": 
        """Sets the embed timestamp to the current time"""
        if self.embed is None: self.embed = discord.Embed()
        self.embed.timestamp = datetime.datetime.now()
        return self

    def setEmbedTime(self, time: datetime.datetime) -> "RichMessage":
        """Sets the embed timestamp to the one provided"""
        if self.embed is None: self.embed = discord.Embed()
        self.embed.timestamp = time
        return self

    def onEvent(self, event: Union[MessagePinEvent, MessageUnpinEvent, MessageReplyEvent, discord.RawReactionActionEvent, discord.RawReactionClearEmojiEvent, discord.RawReactionClearEvent, discord.RawMessageDeleteEvent, discord.RawBulkMessageDeleteEvent], message: Optional[discord.Message]) -> None:
        """Handles a message event that may occur with this particular message. Could be either a pin, unpin, reply, reaction (action, clear emoji, clear), or deletion"""
        getattr(DiscordBotStatic, self.eventHandler)(self, event, message)

    def setEventHandler(self, handler: str) -> None:
        """Sets the handler of a message pin event to a given method. The handler must be a method name in the DiscordBotStatic class and take 3 parameters (RichMessage, eventType, discord.Message). Setting handler to None defaults the handler back to this message. This persists across bot restarts"""
        self.eventHandler = handler

class CommandEvent:
    """Data class that is created during a command event. Holds the original message, target user, command name and parameters"""

    def __init__(self, bot, context: ServerContext, user: discord.abc.User, message: discord.Message, name: str, parameters: str): 
        self.bot = bot
        self.context = context
        self.user = user
        self.message = message
        self.name = name
        self.parameters = parameters
        self.lastResponseMessage = None # type: discord.Message
        self.lastResponse = None # type: RichMessage
        self.lastResponseFinished = True

    async def sendResponse(self, message: Union[str, discord.Embed, RichMessage], finished: bool=True) -> None:
        """Sends a response to the command with the given content and embed. Sets the appropriate fields in the object."""

        if isinstance(message, str): message = ensureSize(message)
        elif isinstance(message, discord.Embed): message = ensureSize(message)
        elif isinstance(message, RichMessage): 
            message.setContent(ensureSize(message.getContent()))
            message.setEmbed(ensureSize(message.getEmbed()))
        
        if self.lastResponseFinished: await self.sendNewResponse(message)
        else: await self.editOldResponse(message)
        self.lastResponse = message
        self.lastResponseFinished = finished
        
    async def sendNewResponse(self, message: Union[str, discord.Embed, RichMessage]) -> None:
        """Sends a new response to the command. Can be overriden to define new behaviour with the command"""
        self.lastResponseMessage = await self.bot.messageHandler.sendMessage(message, self.message.channel)

    async def editOldResponse(self, message: Union[str, discord.Embed, RichMessage]) -> None:
        """Edits an old response to the command. Can be overriden to define new behaviour with the command"""
        await self.bot.messageHandler.editMessage(message, self.lastResponseMessage)

class CommandPrototype:
    pass
