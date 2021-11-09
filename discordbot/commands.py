import discord
import traceback
import random
import subprocess

from discord.embeds import Embed

from . import util, static
from .static import *
from .util import *

class GeneralCommands:
    """A static class that contains all commands normally around server configuration and behaviour. Commands executed here do not necessarily mean that the user has been authenticated, and permissions must be checked during command execution. These commands may or may not have None contexts."""
    async def command_random(event: CommandEvent):
        """Generates a random number. """
        if len(event.parameters) == 0: return "Specify what type of randomness you want"
        parameters = event.parameters.split(" ")
        a = 1
        if len(parameters) > 1 and parameters[1].isdecimal(): a = int(parameters[1])
        if a < 1: return f"{a} is not a valid amount."
        if parameters[0] == "dice": return f"Here {'are' if a > 1 else 'is'} your random dice roll{'s' if a > 1 else ''}: `{'`, `'.join([str(random.randint(1,6)) for x in range(a)])}`"
        elif parameters[0] == "coin": return f"Here {'are' if a > 1 else 'is'} your random coin flip{'s' if a > 1 else ''}: `{'`, `'.join(['heads' if bool(random.getrandbits(1)) else 'tails' for x in range(a)])}`"
        elif parameters[0].isdecimal(): return f"Here {'are' if a > 1 else 'is'} random number{'s' if a > 1 else ''} between `{0}` and `{int(parameters[0])}`: `{'`, `'.join([str(random.randint(0, int(parameters[0]))) for x in range(a)])}`"
        else: return f"Here {'are' if a > 1 else 'is'} your random number{'s' if a > 1 else ''} between `{0}` and `{int(100)}`: `{'`, `'.join([str(random.randint(0, 100)) for x in range(a)])}`"
        
    async def command_auth(event: CommandEvent):
        if event.parameters == "": 
            if event.context: return f"You are currently sending messages in `{event.bot.resolveGuild(event.context.guildID)}`. To switch servers, specify a server name or server ID."
            context = []
            for guild in event.user.mutual_guilds:
                x = event.bot.getContext(guild)
                a = event.bot.setDMContext(event.user, event.bot.getContext(guild))
                if a: context.append(guild)
            if len(context) > 1: 
                event.bot.setDMContext(event.user, None)
                return f"You are not currently sending server commands in DMs. You have permissions to send commands in the following servers: {', '.join([f'`{guild.name}`' for guild in context])}. Specify which to authenticate for."
            elif context: return f"You are now sending commands for `{guild.name}.`"
            else: return "You currently do not have access to a server to send server commands in DMs."
        if event.parameters.lower() == "none":
            if event.context: 
                event.bot.setDMContext(event.user, None)
                return "You are no longer sending server commands in DMs."
            else: return "You are not currently sending server commands in DMs."
        guild = event.bot.resolveGuildByName(event.parameters)
        if not guild: return f"`{event.parameters}` is not a valid server."
        l = event.bot.getDMContext(event.user)
        u = None
        for x in guild:
            if event.bot.setDMContext(event.user, x):
                if u: 
                    event.bot.setDMContext(event.user, l)
                    return f"`{event.parameters}` is ambiguous. Be more specific with the server name or specify its ID."
                else: u = x
        if u: return f"You are now sending comamnds in `{u.name}`"
        else: return "You do not have permission to send server commands there in DMs."

class ServerCommands:
    """A static class that contains all commands normally around server configuration and behaviour. Commands executed here do not necessarily mean that the user has been authenticated, and permissions must be checked during command execution. These commands will always have valid contexts."""
    def command_settings(event: CommandEvent): pass

class PrivilegedCommands:
    """A static class that contains all commands normally around bot management. Commands executed here mean that the user has already been authenticated as a custodian or the bot owner. These commands may or may not have None contexts."""

    async def command_custodians(event: CommandEvent):
        """Manages the custodians of the bot. Target users may be given as ids or mentions (discord.User)"""
        ret = EmbedBuilder().setColor(0xd4af37).setHeaderUser(event.bot.user).setTimeNow()

        # List the current custodians
        if event.parameters == "" or event.parameters == "list": 
            ret.setTitle("Current Custodians")
            ret.setDescription(f"👑<@{event.bot.owner}>" + (' ' if event.bot.admin else '') + ' '.join([f" <@{x}>" for x in event.bot.admin]))
            return ret.build()

        # Check the subcommand and if the user is authorized
        parameters = event.parameters.split(" ")
        if not (parameters[0] == "add" or parameters[0] == "remove"): return "Unknown subcommand"
        if not event.bot.isBotOwner(event.message.author): return "Only the bot owner may add or remove custodians"
        if len(parameters) == 1: return "Specify users to add or remove as a custodian"
        ret.setTitle("Custodians")

        # Parse the target users
        desc = []
        invalid = set()
        notchanged = set()
        success = set()
        changed = set()
        for x in event.message.mentions:
            if str(x.id) == event.bot.owner: desc.append("You cannot change the custodial status of the owner")
            else: changed.add(x.id)
        for x in parameters[1:]:
            if x.isdecimal(): 
                if str(x) == event.bot.owner: desc.append("You cannot change the custodial status of the owner")
                elif event.bot.get_user(int(x)) is not None: changed.add(x)
                else: invalid.add(x)

        # Change the list of custodians
        if parameters[0] == "add":
            mode = True
            for x in changed:
                if str(x) in event.bot.admin: notchanged.add(x)
                else:
                    event.bot.admin.add(x)
                    success.add(x)
        elif parameters[0] == "remove":
            mode = False
            for x in changed:
                if str(x) not in event.bot.admin: notchanged.add(x)
                else: 
                    event.bot.admin.remove(x)
                    success.add(x)
        else: return

        # Return the result of the command
        if len(success) > 1: desc.append(' '.join([f"<@{x}>" for x in success]) + f" are {'already' if mode else 'no longer'} custodians")
        elif success: desc.append(f"<@{success.pop()}> is {'now' if mode else 'no longer'} a custodian")
        if len(notchanged) > 1: desc.append(' '.join([f"<@{x}>" for x in notchanged]) + f" are {'already' if mode else 'not'} custodians")
        elif notchanged: desc.append(f"<@{notchanged.pop()}> is {'already' if mode else 'not'} a custodian")
        if invalid: desc.append(f"{', '.join(invalid)} {'are' if len(notchanged) > 1 else 'is'} invalid")
        ret.setDescription("\n".join(desc))
        return ret.build()

    async def command_execute(event: CommandEvent):
        """Executes a python command. Useful for changing bot configurations or prototyping code."""
        ldict = {}
        gdict = {
            "event": event,
            "bot": event.bot,
            "me": event.message.author,
            "user": event.user,
            "message": event.message,
            "channel": event.message.channel,
            "guild": event.message.guild,
            "context": event.context,
            "discord": discord
        }
        parameters = event.parameters.split(';')
        r = []
        rs = []
        for command in parameters:
            ctemp = command.split('=', 1)
            try:
                if len(ctemp) > 1 and "(" not in ctemp[0]:
                    exec(f"async def __exec__(): return ({ctemp[1].strip()})", gdict, ldict)
                    x = await ldict['__exec__']()
                    gdict[ctemp[0]] = x
                    r.append(str(x))
                    rs.append(type(x).__name__)
                else:
                    exec(f"async def __exec__(): return ({command})", gdict, ldict)
                    x = await ldict['__exec__']()
                    r.append(str(x))
                    rs.append(type(x).__name__)
            except Exception as e:
                r.append(f"-----\n{traceback.format_exc()}-----")
        r = "```\n" + ',\n'.join(r) + "```"
        rs = "Message too long. Showing types only:\n```\n" + ',\n'.join(rs) + "```"
        if len(r) > 1900: return rs
        return r

    async def command_run(event: CommandEvent):
        """Executes another command as another user."""
        eb = EmbedBuilder().setColor(0xffff00).setFooterUser(event.message.author).setTimeNow().setDescription("PDesc").setTitle("PT")
        return eb.build()
        # TODO
        # ce = CommandEvent(event.bot, targetUser, event.message, name, parameters)
        # eb.setHeaderUser(targetUser)
        # pass

    async def command_update(event: CommandEvent):
        """Fetches and update for the discord bot."""
        x = subprocess.run("git pull", capture_output=True, shell=True)
        if "Already up to date" not in x.stdout.decode("utf-8"): return "Fetched an update for this bot. Use `reload {module}` or `restart` to apply the update."
        return "No update was found for this bot."

    async def command_reload(event: CommandEvent):
        """Reloads all or parts of the discord bot."""
        t = event.parameters.lower()
        if t == "bot" or t == "all":
            event.bot.manager.queueFullUpdate()
            return "A full reload has been queued. Use `restart` to restart the bot."
        else:
            x = event.bot.manager.reload(event.bot, t)
            if x: return f"Successfully reloaded the `{t}` module."
            else: return f"`{t}` is not a valid module to reload."

    async def command_restart(event: CommandEvent):
        """Restarts the bot"""
        await event.sendResponse("Restarting the bot.")
        event.bot.manager.queueRestart()
        await event.bot.shutdown()

    async def command_shutdown(event: CommandEvent):
        """Shuts down the bot"""
        await event.sendResponse("Shutting down the bot.")
        await event.bot.shutdown()