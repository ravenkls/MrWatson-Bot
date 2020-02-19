import discord
from discord.ext import commands

from settings import *


async def is_admin(ctx):
    role_id = ctx.bot.database.settings.get("admin_role_id")
    role = ctx.guild.get_role(int(role_id))
    if role <= ctx.author.top_role:
        return True
    return ctx.author.id == 206079414709125120


class Reputation(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        logging.info("Reputation cog initialised.")

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
    bot.add_cog(Reputation(bot))