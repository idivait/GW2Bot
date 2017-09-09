import datetime

import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType

from .exceptions import APIError, APINotFound


class CharactersMixin:
    @commands.group()
    async def character(self, ctx):
        """Character related commands"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @character.command(name="info")
    @commands.cooldown(1, 5, BucketType.user)
    async def character_info(self, ctx, *, character: str):
        """Info about the given character
        You must be the owner of the character.

        Required permissions: characters
        """
        def format_age(age):
            hours, remainder = divmod(int(age), 3600)
            minutes, seconds = divmod(remainder, 60)
            days, hours = divmod(hours, 24)
            if days:
                fmt = '{d} days, {h} hours, {m} minutes, and {s} seconds'
            else:
                fmt = '{h} hours, {m} minutes, and {s} seconds'
            return fmt.format(d=days, h=hours, m=minutes, s=seconds)

        endpoint = "characters/" + character.title().replace(" ", "%20")
        try:
            results = await self.call_api(endpoint, ctx.author, ["characters"])
        except APINotFound:
            return await ctx.send("Invalid character name")
        except APIError as e:
            return await self.error_handler(ctx, e)
        age = format_age(results["age"])
        created = results["created"].split("T", 1)[0]
        deaths = results["deaths"]
        deathsperhour = round(deaths / (results["age"] / 3600), 1)
        if "title" in results:
            title = await self.get_title(results["title"])
        else:
            title = None
        gender = results["gender"]
        profession = results["profession"].lower()
        race = results["race"].lower()
        guild = results["guild"]
        color = self.gamedata["professions"][profession]["color"]
        color = int(color, 0)
        icon = self.gamedata["professions"][profession]["icon"]
        data = discord.Embed(description=title, colour=color)
        data.set_thumbnail(url=icon)
        data.add_field(name="Created at", value=created)
        data.add_field(name="Played for", value=age)
        if guild is not None:
            guild = await self.get_guild(results["guild"])
            gname = guild["name"]
            gtag = guild["tag"]
            data.add_field(name="Guild", value="[{}] {}".format(gtag, gname))
        data.add_field(name="Deaths", value=deaths)
        data.add_field(name="Deaths per hour", value=str(deathsperhour))
        data.set_author(name=character)
        data.set_footer(text="A {} {} {}".format(gender.lower(), race,
                                                 profession))
        try:
            await ctx.send(embed=data)
        except discord.Forbidden:
            await ctx.send("Need permission to embed links")

    @character.command(name="list")
    @commands.cooldown(1, 15, BucketType.user)
    async def character_list(self, ctx):
        """Lists all your characters
        
        Required permissions: characters
        """
        user = ctx.author
        scopes = ["characters"]
        endpoint = "characters?page=0"
        await ctx.trigger_typing()
        try:
            results = await self.call_api(endpoint, user, scopes)
        except APIError as e:
            return await self.error_handler(ctx, e)
        output = "{.mention}, your characters: ```"
        for x in results:
            output += "\n" + x["name"] + " (" + x["profession"] + ")"
        output += "```"
        await ctx.send(output.format(user))

    @character.command(name="gear")
    @commands.cooldown(1, 10, BucketType.user)
    async def character_gear(self, ctx, *, character: str):
        """Displays the gear of given character
        You must be the owner of the character.

        Required permissions: characters
        """

        def handle_duplicates(upgrades):
            formatted_list = []
            for x in upgrades:
                if upgrades.count(x) != 1:
                    formatted_list.append(x + " x" + str(upgrades.count(x)))
                    upgrades[:] = [i for i in upgrades if i != x]
                else:
                    formatted_list.append(x)
            return formatted_list

        endpoint = "characters/" + character.title().replace(" ", "%20")
        await ctx.trigger_typing()
        try:
            results = await self.call_api(endpoint, ctx.author, ["characters"])
        except APINotFound:
            return await ctx.send("Invalid character name")
        except APIError as e:
            return await self.error_handler(ctx, e)
        eq = results["equipment"]
        gear = {}
        pieces = [
            "Helm", "Shoulders", "Coat", "Gloves", "Leggings", "Boots",
            "Ring1", "Ring2", "Amulet", "Accessory1", "Accessory2", "Backpack",
            "WeaponA1", "WeaponA2", "WeaponB1", "WeaponB2"
        ]
        for piece in pieces:
            gear[piece] = {
                "id": None,
                "upgrades": [],
                "infusions": [],
                "stat": None,
                "name": None
            }
        for item in eq:
            for piece in pieces:
                if item["slot"] == piece:
                    gear[piece]["id"] = item["id"]
                    c = await self.fetch_item(item["id"])
                    gear[piece]["name"] = c["name"]
                    if "upgrades" in item:
                        for u in item["upgrades"]:
                            upgrade = await self.db.items.find_one({"_id": u})
                            gear[piece]["upgrades"].append(upgrade["name"])
                    if "infusions" in item:
                        for u in item["infusions"]:
                            infusion = await self.db.items.find_one({"_id": u})
                            gear[piece]["infusions"].append(infusion["name"])
                    if "stats" in item:
                        gear[piece]["stat"] = await self.fetch_statname(
                            item["stats"]["id"])
                    else:
                        thing = await self.db.items.find_one({
                            "_id": item["id"]
                        })
                        try:
                            statid = thing["details"]["infix_upgrade"]["id"]
                            gear[piece]["stat"] = await self.fetch_statname(
                                statid)
                        except:
                            gear[piece]["stat"] = ""
        profession = results["profession"].lower()
        level = results["level"]
        color = self.gamedata["professions"][profession]["color"]
        icon = self.gamedata["professions"][profession]["icon"]
        color = int(color, 0)
        data = discord.Embed(description="Gear", colour=color)
        for piece in pieces:
            if gear[piece]["id"] is not None:
                statname = gear[piece]["stat"]
                itemname = gear[piece]["name"]
                upgrade = handle_duplicates(gear[piece]["upgrades"])
                infusion = handle_duplicates(gear[piece]["infusions"])
                msg = "\n".join(upgrade + infusion)
                if not msg:
                    msg = "---"
                data.add_field(
                    name="{} {} [{}]".format(statname, itemname, piece),
                    value=msg,
                    inline=False)
        data.set_author(name=character)
        data.set_footer(
            text="A level {} {} ".format(level, profession), icon_url=icon)
        try:
            await ctx.send(embed=data)
        except discord.Forbidden as e:
            await ctx.send("Need permission to embed links")

    @character.command(name="birthdays")
    async def character_birthdays(self, ctx):
        """Lists days until the next birthday for each of your characters.

        Required permissions: characters
        """
        user = ctx.message.author
        endpoint = "characters?page=0"
        await ctx.trigger_typing()
        try:
            results = await self.call_api(endpoint, user, ["characters"])
        except APIError as e:
            return await self.error_handler(ctx, e)
        charlist = []
        for character in results:
            created = character["created"].split("T", 1)[0]
            dt = datetime.datetime.strptime(created, "%Y-%m-%d")
            age = datetime.datetime.utcnow() - dt
            days = age.days
            years = days / 365
            floor = int(days / 365)
            daystill = 365 - (days -
                              (365 * floor))  # finds days till next birthday
            charlist.append(character["name"] + " " + str(floor + 1) + " " +
                            str(daystill))
        sortedlist = sorted(charlist, key=lambda v: int(v.rsplit(' ', 1)[1]))
        output = "{.mention}, days until each of your characters birthdays:```"
        for character in sortedlist:
            name = character.rsplit(' ', 2)[0]
            days = character.rsplit(' ', 1)[1]
            years = character.rsplit(' ', 2)[1]
            if years == "1":
                suffix = 'st'
            elif years == "2":
                suffix = 'nd'
            elif years == "3":
                suffix = 'rd'
            else:
                suffix = 'th'
            output += "\n{} {} days until {}{} birthday".format(
                name, days, years, suffix)
        output += "```"
        await ctx.send(output.format(user))