from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands
import time
from io import BytesIO
import asyncio
import zipfile
import re
import aiohttp

try:
    from PIL import Image
except Exception:
    Image = None


class MiscCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = time.time()

    # ───────────────────────── PING (SLASH) ─────────────────────────

    @app_commands.command(name="ping", description="Check bot latency")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)

        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latency: {latency}ms",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed)

    # ───────────────────────── SERVER INFO ─────────────────────────

    @app_commands.command(name="server_info", description="Get server information")
    async def server_info(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"Server Information: {guild.name}",
            color=discord.Color.blue()
        )

        embed.add_field(name="Members", value=guild.member_count, inline=True)
        embed.add_field(
            name="Created",
            value=f"<t:{int(guild.created_at.timestamp())}:F>",
            inline=True
        )
        embed.add_field(
            name="Owner",
            value=guild.owner.mention if guild.owner else "Unknown",
            inline=True
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        await interaction.response.send_message(embed=embed)

    # ───────────────────────── PREFIX PING ─────────────────────────

    @commands.command(name="ping")
    async def ping_prefix(self, ctx):
        latency = round(self.bot.latency * 1000)

        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latency: {latency}ms",
            color=discord.Color.green()
        )

        await ctx.send(embed=embed)

    # ───────────────────────── UPTIME ─────────────────────────

    @commands.command(name="uptime")
    async def uptime(self, ctx):
        uptime_seconds = int(time.time() - self.start_time)

        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60

        uptime_str = ""
        if days:
            uptime_str += f"{days}d "
        if hours:
            uptime_str += f"{hours}h "
        if minutes:
            uptime_str += f"{minutes}m "
        uptime_str += f"{seconds}s"

        embed = discord.Embed(
            title="⏰ Bot Uptime",
            description=f"I've been running for **{uptime_str}**",
            color=discord.Color.blue()
        )

        await ctx.send(embed=embed)

    # ───────────────────────── COLOUR TOOL ─────────────────────────

    @commands.command(name="colour")
    async def colour(self, ctx, hex_color: str):
        c = hex_color.strip().lstrip("#")

        if len(c) == 3:
            c = "".join(ch * 2 for ch in c)

        if len(c) != 6:
            await ctx.send("Invalid hex colour.")
            return

        try:
            value = int(c, 16)
        except ValueError:
            await ctx.send("Invalid hex value.")
            return

        r = (value >> 16) & 0xFF
        g = (value >> 8) & 0xFF
        b = value & 0xFF

        # If Pillow not installed → fallback embed
        if Image is None:
            embed = discord.Embed(
                title=f"Colour #{c.upper()}",
                description=f"RGB: {r}, {g}, {b}",
                color=discord.Color(value)
            )
            await ctx.send(embed=embed)
            return

        # Create image
        try:
            img = Image.new("RGB", (256, 256), (r, g, b))
            bio = BytesIO()
            img.save(bio, "PNG")
            bio.seek(0)

            file = discord.File(bio, filename="colour.png")

            embed = discord.Embed(
                title=f"Colour #{c.upper()}",
                color=discord.Color(value)
            )
            embed.set_image(url="attachment://colour.png")
            embed.add_field(name="RGB", value=f"{r}, {g}, {b}")

            await ctx.send(embed=embed, file=file)

        except Exception as e:
            await ctx.send(f"Failed to generate image: {e}")

    # ───────────────────────── EMOJI ZIP ─────────────────────────

    @commands.command(name="emojis")
    async def emojis(self, ctx):
        guild = ctx.guild
        if not guild:
            await ctx.send("Use this in a server.")
            return

        if not guild.emojis:
            await ctx.send("No custom emojis.")
            return

        msg = await ctx.send("Creating emoji zip...")

        bio = BytesIO()

        try:
            async with aiohttp.ClientSession() as session:
                with zipfile.ZipFile(bio, "w") as zf:
                    used = set()

                    for e in guild.emojis:
                        url = str(e.url)
                        ext = "gif" if getattr(e, "animated", False) else "png"

                        name = re.sub(r'[^A-Za-z0-9_.-]+', '_', e.name or str(e.id))
                        filename = f"{name}.{ext}"

                        if filename in used:
                            i = 1
                            while f"{name}_{i}.{ext}" in used:
                                i += 1
                            filename = f"{name}_{i}.{ext}"

                        used.add(filename)

                        async with session.get(url) as r:
                            if r.status == 200:
                                zf.writestr(filename, await r.read())

            bio.seek(0)

            file = discord.File(bio, filename=f"{guild.name}_emojis.zip")

            await msg.edit(content="Here is your emoji pack:")
            await ctx.send(file=file)

        except Exception as e:
            await msg.edit(content="Failed to create emoji zip.")
            await ctx.send(str(e))

    # ───────────────────────── STATS ─────────────────────────

    @commands.command(name="stats")
    async def stats(self, ctx):
        uptime = int(time.time() - self.start_time)

        embed = discord.Embed(
            title="Bot Stats",
            color=discord.Color.green()
        )

        embed.add_field(name="Uptime", value=f"{uptime}s", inline=True)
        embed.add_field(name="Guilds", value=len(self.bot.guilds), inline=True)
        embed.add_field(name="Latency", value=f"{round(self.bot.latency*1000)}ms", inline=True)

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(MiscCog(bot))