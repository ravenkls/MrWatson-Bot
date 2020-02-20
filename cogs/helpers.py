import logging

import discord
from discord.ext import commands

from settings import *


async def is_admin(ctx):
    role_id = ctx.bot.database.settings.get("admin_role_id")
    role = ctx.guild.get_role(int(role_id))
    if role <= ctx.author.top_role:
        return True
    return ctx.author.id == 206079414709125120


class Helpers(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.logger.info("Reputation cog initialised.")

    @commands.command()
    @commands.guild_only()
    async def rep(self, ctx, *, member: discord.Member):
        """Add a reputation point to a member."""
        if member.bot:
            raise Exception("You can't rep a bot!")
        elif member == ctx.author:
            raise Exception("You can't rep yourself!")

        reps = self.bot.database.add_rep(member)
        await ctx.send(f"✅ **{member.mention}** now has `{reps}` reputation points!")

    @commands.command()
    @commands.guild_only()
    async def repcount(self, ctx, *, member: discord.Member=None):
        """View how many reputation points a user has."""
        if member is None:
            member = ctx.author
        rep_count = self.bot.database.get_reps(member)
        await ctx.send(f"{member} has `{rep_count}` reputation points.")

    @commands.command()
    async def leaderboard(self, ctx):
        """View the reputation points leaderboard."""
        leaderboard = self.bot.database.get_top_reps()
        embed = discord.Embed(colour=EMBED_ACCENT_COLOUR)
        embed.set_author(name="Reputation Leaderboard", icon_url="https://images.emojiterra.com/mozilla/512px/1f3c6.png")
        for member_id, points in leaderboard:
            member = ctx.guild.get_member(member_id)
            if member:
                embed.add_field(name=str(member), value=points, inline=False)
        await ctx.send(embed=embed)
    
    @commands.command(hidden=True)
    @commands.check(is_admin)
    @commands.guild_only()
    async def setglobalhelperrole(self, ctx, *, role: discord.Role):
        """Sets the global helper role."""
        self.bot.database.set_setting("helper_role_guild_id", str(ctx.guild.id))
        self.bot.database.set_setting("helper_role_id", str(role.id))
        await ctx.send(f"✅ {role.mention} is now set as the admin role.")

    @commands.command()
    @commands.check(is_admin)
    @commands.guild_only()
    async def addhelperrole(self, ctx, *, role: discord.Role):
        """Add a helper role to a channel."""
        self.bot.database.add_helper_role(ctx.channel, role)
        await ctx.send(f"{role.mention} is now a helper role for this channel.")
    
    @commands.command()
    @commands.check(is_admin)
    @commands.guild_only()
    async def removehelperrole(self, ctx, *, role: discord.Role):
        """Remove a helper role from a channel."""
        self.bot.database.remove_helper_role(ctx.channel, role.id)
        await ctx.send(f"{role.mention} is no longer a helper role for this channel.")

    @commands.command()
    @commands.guild_only()
    async def helperroles(self, ctx):
        """Get all helper roles for a channel."""
        string = ""
        helper_roles = self.bot.database.get_helper_roles(ctx.channel)
        for r in helper_roles:
            role = ctx.guild.get_role(r)
            if role:
                string += role.name + "\n"
            else:
                self.bot.database.remove_helper_role(ctx.channel, r)
            
        embed = discord.Embed(colour=EMBED_ACCENT_COLOUR, title=f"Helpers for {ctx.channel}",
                              description=string)
        await ctx.send(embed=embed)

    @commands.command(aliases=["helpme"])
    @commands.guild_only()
    async def helper(self, ctx):
        """Calls a helper if you need help, this command only works in subject channels."""
        role_ids = self.bot.database.get_helper_roles(ctx.channel)
        roles = [ctx.guild.get_role(r) for r in role_ids]
        role_mentions = []
        role_previous_setting = []
        
        for role in roles:
            if role is None:
                self.bot.database.remove_helper_role(ctx.channel, r)
                continue
            previous_setting = role.mentionable
            if not role.mentionable:
                await role.edit(mentionable=True)
            role_mentions.append(role.mention)
            role_previous_setting.append(previous_setting)    
        
        if not role_ids:
            await ctx.send("There are no helpers for this channel.")
        else:
            await ctx.send(' '.join(role_mentions))
            for role in roles:
                if role is None:
                    continue
                if previous_setting != role.mentionable:
                    await role.edit(mentionable=previous_setting)

    @commands.command(aliases=["reps"])
    @commands.check(is_admin)
    @commands.guild_only()
    async def setreps(self, ctx, *, query: str=None):
        """Configure the reputation points. (Admin only)
        
        Command options:
        -setreps set <member> <amount>
        -setreps remove <member> <amount>
        -setreps add <member> <amount>
        -setreps clear"""
        if query is not None:
            args = [a.strip() for a in query.split()]
            if args[0].lower() in ["set", "remove", "add"]:
                if len(args) != 3:
                    raise Exception("Invalid options.")
                member = ctx.guild.get_member_named(args[1])
                if not member and not ctx.message.mentions:
                    raise Exception("Member not found")
                elif not member:
                    member = ctx.message.mentions[0]
                amount = args[2]
                if not amount.isdigit():
                    raise Exception("Amount must be an integer")
                amount = int(amount)

                if args[0].lower() == "set":
                    new_points = self.bot.database.set_reps(member, amount)
                    embed = discord.Embed(colour=EMBED_ACCENT_COLOUR, 
                                          description=f"🏅 {ctx.author.mention} set {member.mention}'s reputation points to {new_points}")
                elif args[0].lower() == "remove":
                    new_points = self.bot.database.add_rep(member, amount=-amount)
                    embed = discord.Embed(colour=EMBED_ACCENT_COLOUR, 
                                          description=f"🏅 {ctx.author.mention} removed {amount} reputation points from {member.mention}")
                elif args[0].lower() == "add":
                    new_points = self.bot.database.add_rep(member, amount=amount)
                    embed = discord.Embed(colour=EMBED_ACCENT_COLOUR, 
                                          description=f"🏅 {ctx.author.mention} added {amount} reputation points from {member.mention}")
                await self.log(embed)
                await ctx.send(f"✅ **{member}** now has `{new_points}` reputation points!")
            elif args[0].lower() == "clear":
                await self.remove_all_reps(ctx)

    async def remove_all_reps(self, ctx):
        temp = await ctx.send("⛔ **You are about to completely remove all reputation points from everyone in the server**\n"
                              "\nTo confirm this action, please type `confirm` within the next 10 seconds.")
        
        def check(m):
            return m.content == "confirm" and m.author == ctx.author and m.channel == ctx.channel
        
        try:
            response = await self.bot.wait_for("message", check=check, timeout=10)
        except asyncio.TimeoutError:
            return
        else:
            self.bot.database.clear_reputations()
            embed = discord.Embed(colour=EMBED_ACCENT_COLOUR, 
                                  description=f"🏅 {ctx.author.mention} removed ALL reputation points")
            await self.log(embed)
            await response.delete()
            await ctx.send("✅ All reputation points have been cleared.")
            if ctx.author != ctx.guild.owner:
                await ctx.guild.owner.send("**Notice:** All reputation points have been cleared from the server\n"
                                           f"\nThis action was carried out by {ctx.author} (`{ctx.author.id}`)")
        finally:
            await temp.delete()

def setup(bot):
    bot.add_cog(Helpers(bot))
