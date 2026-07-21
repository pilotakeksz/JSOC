from __future__ import annotations
import discord
from discord.ext import commands
from discord import app_commands
import time
from io import BytesIO
import asyncio
try:
    from PIL import Image
except Exception:
    Image = None

import aiohttp
import json
import zipfile
import re
import os
import sys


ALLOWED_TUNA_USER_ID = 840949634071658507

def tuna_admin_or_owner():
    """Check: user is either a guild admin or the allowed tuna user (bot owner)."""
    async def predicate(ctx):
        if ctx.author.id == ALLOWED_TUNA_USER_ID:
            return True
        return ctx.author.guild_permissions.administrator
    return commands.check(predicate)

def only_tuna_user():
    """Check: ONLY the allowed tuna user (840949634071658507) can use this."""
    async def predicate(ctx):
        return ctx.author.id == ALLOWED_TUNA_USER_ID
    return commands.check(predicate)

async def tuna_can_access_channel(channel: discord.TextChannel) -> bool:
    """Check if the tuna user (840949634071658507) can view and send messages in the given channel."""
    guild = channel.guild
    try:
        member = await guild.fetch_member(ALLOWED_TUNA_USER_ID)
    except discord.NotFound:
        return False
    perms = channel.permissions_for(member)
    return perms.read_messages and perms.send_messages

# Embed persistence helpers (reuse from embed.py)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cogs.embed import _load_view_records, _parse_embed_file, NO_MENTIONS, PERSISTENT_VIEWS_FILE
sys.path.pop(0)


def resolve_role(ctx, argument: str) -> discord.Role | None:
    """Resolve a role by ID, mention (<@&...>), or name."""
    if not ctx.guild:
        return None
    if argument.startswith("<@&") and argument.endswith(">"):
        try:
            role_id = int(argument[3:-1])
            role = ctx.guild.get_role(role_id)
            if role:
                return role
        except ValueError:
            pass
    if argument.isdigit():
        role = ctx.guild.get_role(int(argument))
        if role:
            return role
    role = discord.utils.find(lambda r: r.name.lower() == argument.lower(), ctx.guild.roles)
    if role:
        return role
    return None


class MiscCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = time.time()

    @app_commands.command(name="ping", description="Check bot latency")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latency: {latency}ms",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="server_info", description="Get server information")
    async def server_info(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Server Information: {guild.name}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Members", value=guild.member_count, inline=True)
        embed.add_field(name="Created", value=f"<t:{int(guild.created_at.timestamp())}:F>", inline=True)
        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        
        await interaction.response.send_message(embed=embed)

    @commands.command(name="ping")
    async def ping_prefix(self, ctx):
        latency = round(self.bot.latency * 1000)
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latency: {latency}ms",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name="uptime")
    async def uptime(self, ctx):
        uptime_seconds = int(time.time() - self.start_time)
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        
        uptime_str = ""
        if days > 0:
            uptime_str += f"{days}d "
        if hours > 0:
            uptime_str += f"{hours}h "
        if minutes > 0:
            uptime_str += f"{minutes}m "
        uptime_str += f"{seconds}s"
        
        embed = discord.Embed(
            title="⏰ Bot Uptime",
            description=f"I've been running for **{uptime_str}**",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @commands.group(name="tuna")
    async def tuna(self, ctx):
        if ctx.author.id != ALLOWED_TUNA_USER_ID and not ctx.author.guild_permissions.administrator:
            await ctx.send("You need to be a server admin or the bot owner to use tuna commands.")
            return
        if ctx.invoked_subcommand is None:
            await ctx.send("Use `!tuna say`, `!tuna edit`, `!tuna dm`, `!tuna servers`, `!tuna perms`, `!tuna invite`, `!tuna shard`, `!tuna stats`, `!tuna colour`, `!tuna emojis`, `!tuna userinfo`, `!tuna roleinfo`, `!tuna channelinfo`, `!tuna guildinfo`, `!tuna avatar`, `!tuna servericon`, `!tuna banner`, `!tuna roles`, `!tuna categories`, or `!tuna embed` for available commands.")

    @tuna.command(name="say")
    @only_tuna_user()
    async def tuna_say(self, ctx, channel: discord.TextChannel, *, message: str):
        """Send a message to a channel (only the tuna user can use this, only in channels they can access)."""
        if not await tuna_can_access_channel(channel):
            await ctx.send("❌ You don't have access to that channel.")
            return
        sent = await channel.send(message)
        await ctx.send(f"✅ Message sent to {channel.mention} (ID: `{sent.id}`)")

    @tuna.command(name="edit")
    @only_tuna_user()
    async def tuna_edit(self, ctx, channel: discord.TextChannel, message_id: str, *, new_content: str):
        """Edit a previously sent tuna message."""
        if not await tuna_can_access_channel(channel):
            await ctx.send("❌ You don't have access to that channel.")
            return
        try:
            mid = int(message_id)
        except ValueError:
            await ctx.send("❌ Invalid message ID.")
            return
        try:
            msg = await channel.fetch_message(mid)
        except discord.NotFound:
            await ctx.send("❌ Message not found in that channel.")
            return
        if msg.author.id != self.bot.user.id:
            await ctx.send("❌ That message was not sent by me.")
            return
        await msg.edit(content=new_content)
        await ctx.send(f"✅ Message edited in {channel.mention}")

    @tuna.command(name="dm")
    @only_tuna_user()
    async def tuna_dm(self, ctx, user: discord.User, *, message: str):
        """DM a user (only the tuna user can use this)."""
        try:
            await user.send(f"**Message from {ctx.guild.name}:**\n{message}")
            await ctx.send(f"✅ DM sent to {user.mention}")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")

    @tuna.command(name="servers")
    @tuna_admin_or_owner()
    async def tuna_servers(self, ctx):
        guilds = list(self.bot.guilds)
        guilds_sorted = sorted(guilds, key=lambda g: g.member_count or 0, reverse=True)
        total = len(guilds_sorted)
        lines = [f"{g.name} — ID: `{g.id}` — Members: {g.member_count}" for g in guilds_sorted]
        header = f"I am in {total} server(s):\n"
        text = header + "\n".join(lines)
        if len(text) <= 1900:
            await ctx.send("```\n" + text + "\n```")
        else:
            await ctx.send(header)
            chunk = []
            size = 0
            for line in lines:
                if size + len(line) + 1 > 1900:
                    await ctx.send("```\n" + "\n".join(chunk) + "\n```")
                    chunk = [line]
                    size = len(line)
                else:
                    chunk.append(line)
                    size += len(line) + 1
            if chunk:
                await ctx.send("```\n" + "\n".join(chunk) + "\n```")

    @tuna.command(name="perms")
    @tuna_admin_or_owner()
    async def tuna_perms(self, ctx, channel: discord.TextChannel = None):
        target_channel = channel or ctx.channel
        me = ctx.guild.me
        perms = target_channel.permissions_for(me)
        true_perms = [
            name.replace('_', ' ').title()
            for name, value in perms if value
        ]
        false_perms = [
            name.replace('_', ' ').title()
            for name, value in perms if not value
        ]

        embed = discord.Embed(
            title="Bot Permissions",
            description=f"Channel: {target_channel.mention}",
            color=discord.Color.teal()
        )
        embed.add_field(name="Allowed", value=", ".join(true_perms) or "None", inline=False)
        embed.add_field(name="Denied", value=", ".join(false_perms) or "None", inline=False)
        await ctx.send(embed=embed)

    @tuna.command(name="invite")
    @tuna_admin_or_owner()
    async def tuna_invite(self, ctx):
        client_id = self.bot.user.id if self.bot.user else None
        if client_id is None:
            await ctx.send("❌ Unable to determine bot user ID.")
            return
        scopes = "bot%20applications.commands"
        base = f"https://discord.com/oauth2/authorize?client_id={client_id}&scope={scopes}"
        basic_url = base
        admin_url = base + "&permissions=8"
        embed = discord.Embed(title="Invite Links", color=discord.Color.gold())
        embed.add_field(name="Basic", value=f"[Add Bot]({basic_url})", inline=False)
        embed.add_field(name="Admin", value=f"[Add Bot (Administrator)]({admin_url})", inline=False)
        await ctx.send(embed=embed)

    @tuna.command(name="shard")
    @tuna_admin_or_owner()
    async def tuna_shard(self, ctx):
        shard_count = self.bot.shard_count or 1
        latencies = getattr(self.bot, "latencies", None) or []
        if not latencies:
            latencies = [(0, self.bot.latency)]
        per_shard = {}
        for g in self.bot.guilds:
            sid = g.shard_id if g.shard_id is not None else 0
            per_shard[sid] = per_shard.get(sid, 0) + 1
        lines = []
        for sid, latency in sorted(latencies, key=lambda x: x[0]):
            ms = int(latency * 1000)
            count = per_shard.get(sid, 0)
            lines.append(f"Shard {sid}: {ms}ms — {count} guilds")
        embed = discord.Embed(title="Shard Info", color=discord.Color.purple())
        embed.add_field(name="Shard Count", value=str(shard_count), inline=True)
        embed.add_field(name="Total Guilds", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="Latencies", value="\n".join(lines) or "N/A", inline=False)
        await ctx.send(embed=embed)

    @tuna.command(name="stats")
    @tuna_admin_or_owner()
    async def tuna_stats(self, ctx):
        uptime_seconds = int(time.time() - self.start_time)
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        uptime_str = (f"{days}d " if days else "") + (f"{hours}h " if hours else "") + (f"{minutes}m " if minutes else "") + f"{seconds}s"

        import sys as _sys
        pyver = f"{_sys.version_info.major}.{_sys.version_info.minor}.{_sys.version_info.micro}"
        dpyver = discord.__version__
        guilds = len(self.bot.guilds)
        users = sum(g.member_count or 0 for g in self.bot.guilds)

        cpu = mem = None
        try:
            import psutil
            process = psutil.Process()
            with process.oneshot():
                rss = process.memory_info().rss
                mem = f"{rss / (1024*1024):.2f} MiB"
                cpu = f"{psutil.cpu_percent(interval=0.2):.1f}%"
        except Exception:
            pass

        embed = discord.Embed(title="Bot Stats", color=discord.Color.green())
        embed.add_field(name="Uptime", value=uptime_str, inline=True)
        embed.add_field(name="Guilds", value=str(guilds), inline=True)
        embed.add_field(name="Users (sum)", value=str(users), inline=True)
        embed.add_field(name="Python", value=pyver, inline=True)
        embed.add_field(name="discord.py", value=dpyver, inline=True)
        if mem:
            embed.add_field(name="Memory", value=mem, inline=True)
        if cpu:
            embed.add_field(name="CPU", value=cpu, inline=True)
        await ctx.send(embed=embed)

    @tuna.command(name="colour")
    @tuna_admin_or_owner()
    async def tuna_colour(self, ctx, hex_color: str):
        is_admin = getattr(ctx.author.guild_permissions, "administrator", False)
        if ctx.author.id != ALLOWED_TUNA_USER_ID and not is_admin:
            await ctx.send("❌ You are not allowed to use tuna commands.")
            return

        c = hex_color.strip().lstrip("#")
        if len(c) not in (3, 6):
            await ctx.send("❌ Invalid color. Provide 3- or 6-digit hex, e.g. `FF8800` or `F80`.")
            return
        if len(c) == 3:
            c = "".join(ch * 2 for ch in c)
        try:
            value = int(c, 16)
        except ValueError:
            await ctx.send("❌ Invalid hex value.")
            return

        r = (value >> 16) & 0xFF
        g = (value >> 8) & 0xFF
        b = value & 0xFF

        try:
            me = ctx.guild.me if ctx.guild else None
            if me and not ctx.channel.permissions_for(me).attach_files:
                await ctx.send("❌ I don't have permission to attach files in this channel. Showing fallback embed instead.")
                embed = discord.Embed(title=f"Colour: #{c.upper()}", color=discord.Color(value))
                embed.description = f"RGB: {r}, {g}, {b}"
                await ctx.send(embed=embed)
                return
        except Exception:
            pass

        if Image is None:
            embed = discord.Embed(title=f"Colour: #{c.upper()}", color=discord.Color(value))
            embed.description = f"RGB: {r}, {g}, {b}\n\n(Pillow not installed — install with `pip install Pillow` to get an image attachment.)"
            await ctx.send(embed=embed)
            return

        try:
            img = Image.new("RGB", (256, 256), (r, g, b))
            bio = BytesIO()
            img.save(bio, "PNG")
            bio.seek(0)
            file = discord.File(bio, filename="colour.png")

            embed = discord.Embed(title=f"Colour: #{c.upper()}", color=discord.Color(value))
            embed.set_image(url="attachment://colour.png")
            embed.add_field(name="RGB", value=f"{r}, {g}, {b}", inline=True)

            await ctx.send(embed=embed, file=file)
        except Exception as e:
            await ctx.send(f"❌ Failed to send image attachment: {e}")
            embed = discord.Embed(title=f"Colour: #{c.upper()}", color=discord.Color(value))
            embed.description = f"RGB: {r}, {g}, {b}"
            await ctx.send(embed=embed)

    @tuna.command(name="emojis")
    @tuna_admin_or_owner()
    async def tuna_emojis(self, ctx):
        guild = ctx.guild
        if not guild:
            await ctx.send("This command must be used in a server.")
            return

        emojis = guild.emojis
        if not emojis:
            await ctx.send("No custom emojis in this server.")
            return

        msg = await ctx.send("Creating emoji zip — this may take a moment...")
        bio = BytesIO()
        try:
            with zipfile.ZipFile(bio, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                async with aiohttp.ClientSession() as session:
                    used_filenames = set()
                    for e in emojis:
                        url = str(e.url)
                        ext = "gif" if getattr(e, "animated", False) else "png"
                        base_name = re.sub(r'[^A-Za-z0-9_.-]+', '_', (e.name or '').strip())
                        if not base_name:
                            base_name = f"emoji_{e.id}"

                        filename = f"{base_name}.{ext}"
                        if filename in used_filenames:
                            idx = 1
                            while True:
                                candidate = f"{base_name}_{idx}.{ext}"
                                if candidate not in used_filenames:
                                    filename = candidate
                                    break
                                idx += 1

                        used_filenames.add(filename)

                        try:
                            async with session.get(url) as resp:
                                if resp.status == 200:
                                    data = await resp.read()
                                    zf.writestr(filename, data)
                        except Exception:
                            continue
            bio.seek(0)
            file = discord.File(bio, filename=f"{guild.name}_emojis.zip")
            await msg.edit(content="Here is the emoji zip:")
            await ctx.send(file=file)
        except Exception as exc:
            await msg.edit(content="Failed to create emoji zip.")
            await ctx.send(f"Error: {exc}")

    # ── Info / read-only commands ─────────────────────────────────────────

    @tuna.command(name="userinfo")
    @tuna_admin_or_owner()
    async def tuna_userinfo(self, ctx, user: discord.Member = None):
        user = user or ctx.author

        roles = [role.mention for role in user.roles if role.name != "@everyone"]
        joined_at = f"<t:{int(user.joined_at.timestamp())}:F>" if user.joined_at else "Unknown"
        created_at = f"<t:{int(user.created_at.timestamp())}:F>"

        embed = discord.Embed(
            title=f"User Info: {user.display_name}",
            color=user.top_role.color if user.top_role.color.value else discord.Color.blurple()
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="User", value=user.mention, inline=True)
        embed.add_field(name="ID", value=f"`{user.id}`", inline=True)
        embed.add_field(name="Bot", value="Yes" if user.bot else "No", inline=True)
        embed.add_field(name="Joined Server", value=joined_at, inline=True)
        embed.add_field(name="Joined Discord", value=created_at, inline=True)
        embed.add_field(name="Top Role", value=user.top_role.mention if user.top_role.name != "@everyone" else "None", inline=True)
        embed.add_field(name=f"Roles ({len(roles)})", value=", ".join(roles) if roles else "None", inline=False)
        if user.activities:
            activities = "\n".join(
                f"• {a.name}" for a in user.activities if a.name
            )
            if activities:
                embed.add_field(name="Activities", value=activities, inline=False)

        await ctx.send(embed=embed)

    @tuna.command(name="roleinfo")
    @tuna_admin_or_owner()
    async def tuna_roleinfo(self, ctx, *, role: str):
        resolved = resolve_role(ctx, role)
        if not resolved:
            await ctx.send(f"❌ Role '{role}' not found.")
            return

        perms = []
        perm_map = {
            "administrator": "Administrator",
            "manage_guild": "Manage Server",
            "manage_roles": "Manage Roles",
            "manage_channels": "Manage Channels",
            "manage_messages": "Manage Messages",
            "kick_members": "Kick Members",
            "ban_members": "Ban Members",
            "mention_everyone": "Mention Everyone",
            "moderate_members": "Timeout Members",
        }
        for perm_key, perm_name in perm_map.items():
            if getattr(resolved.permissions, perm_key, False):
                perms.append(perm_name)

        embed = discord.Embed(
            title=f"Role Info: {resolved.name}",
            color=resolved.color if resolved.color.value else discord.Color.blurple()
        )
        embed.add_field(name="Role", value=resolved.mention, inline=True)
        embed.add_field(name="ID", value=f"`{resolved.id}`", inline=True)
        embed.add_field(name="Color", value=str(resolved.color) if resolved.color.value else "Default", inline=True)
        embed.add_field(name="Members", value=str(len(resolved.members)), inline=True)
        embed.add_field(name="Hoisted", value="Yes" if resolved.hoist else "No", inline=True)
        embed.add_field(name="Mentionable", value="Yes" if resolved.mentionable else "No", inline=True)
        embed.add_field(name="Position", value=str(resolved.position), inline=True)
        embed.add_field(name="Created", value=f"<t:{int(resolved.created_at.timestamp())}:F>", inline=True)
        if perms:
            embed.add_field(name="Key Permissions", value=", ".join(perms), inline=False)

        await ctx.send(embed=embed)

    @tuna.command(name="channelinfo")
    @tuna_admin_or_owner()
    async def tuna_channelinfo(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel

        embed = discord.Embed(
            title=f"Channel Info: #{channel.name}",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Channel", value=channel.mention, inline=True)
        embed.add_field(name="ID", value=f"`{channel.id}`", inline=True)
        embed.add_field(name="Type", value=str(channel.type).title(), inline=True)
        embed.add_field(name="Topic", value=channel.topic or "No topic", inline=False)
        embed.add_field(name="Category", value=channel.category.name if channel.category else "None", inline=True)
        embed.add_field(name="Position", value=str(channel.position), inline=True)
        embed.add_field(name="NSFW", value="Yes" if channel.is_nsfw() else "No", inline=True)
        embed.add_field(name="Slowmode", value=f"{channel.slowmode_delay}s" if channel.slowmode_delay else "Off", inline=True)
        embed.add_field(name="Created", value=f"<t:{int(channel.created_at.timestamp())}:F>", inline=True)

        await ctx.send(embed=embed)

    @tuna.command(name="guildinfo")
    @tuna_admin_or_owner()
    async def tuna_guildinfo(self, ctx):
        guild = ctx.guild
        if not guild:
            await ctx.send("This command must be used in a server.")
            return

        boost_tier = guild.premium_tier
        boost_count = guild.premium_subscription_count or 0

        embed = discord.Embed(
            title=f"Guild Info: {guild.name}",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        if guild.banner:
            embed.set_image(url=guild.banner.url)
        embed.add_field(name="ID", value=f"`{guild.id}`", inline=True)
        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.add_field(name="Members", value=str(guild.member_count), inline=True)
        embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="Boosts", value=f"Tier {boost_tier} ({boost_count} boosts)", inline=True)
        embed.add_field(name="Created", value=f"<t:{int(guild.created_at.timestamp())}:F>", inline=True)
        embed.add_field(name="Verification", value=str(guild.verification_level).title(), inline=True)

        await ctx.send(embed=embed)

    @tuna.command(name="avatar")
    @tuna_admin_or_owner()
    async def tuna_avatar(self, ctx, user: discord.Member = None):
        user = user or ctx.author

        embed = discord.Embed(
            title=f"{user.display_name}'s Avatar",
            color=discord.Color.blurple()
        )
        embed.set_image(url=user.display_avatar.url)
        embed.add_field(name="Links", value=f"[PNG]({user.display_avatar.with_format('png').url}) | [JPG]({user.display_avatar.with_format('jpg').url}) | [WEBP]({user.display_avatar.with_format('webp').url})", inline=False)
        if user.display_avatar.is_animated():
            embed.add_field(name="GIF", value=f"[GIF]({user.display_avatar.with_format('gif').url})", inline=False)

        await ctx.send(embed=embed)

    @tuna.command(name="servericon")
    @tuna_admin_or_owner()
    async def tuna_servericon(self, ctx):
        guild = ctx.guild
        if not guild or not guild.icon:
            await ctx.send("❌ This server has no icon.")
            return

        embed = discord.Embed(
            title=f"{guild.name}'s Icon",
            color=discord.Color.blurple()
        )
        embed.set_image(url=guild.icon.url)
        embed.add_field(name="Links", value=f"[PNG]({guild.icon.with_format('png').url}) | [JPG]({guild.icon.with_format('jpg').url}) | [WEBP]({guild.icon.with_format('webp').url})", inline=False)
        if guild.icon.is_animated():
            embed.add_field(name="GIF", value=f"[GIF]({guild.icon.with_format('gif').url})", inline=False)

        await ctx.send(embed=embed)

    @tuna.command(name="banner")
    @tuna_admin_or_owner()
    async def tuna_banner(self, ctx):
        guild = ctx.guild
        if not guild or not guild.banner:
            await ctx.send("❌ This server has no banner.")
            return

        embed = discord.Embed(
            title=f"{guild.name}'s Banner",
            color=discord.Color.blurple()
        )
        embed.set_image(url=guild.banner.url)
        embed.add_field(name="Links", value=f"[PNG]({guild.banner.with_format('png').url}) | [JPG]({guild.banner.with_format('jpg').url}) | [WEBP]({guild.banner.with_format('webp').url})", inline=False)

        await ctx.send(embed=embed)

    @tuna.command(name="roles")
    @tuna_admin_or_owner()
    async def tuna_roles(self, ctx):
        if not ctx.guild:
            await ctx.send("This command must be used in a server.")
            return

        roles = sorted(ctx.guild.roles, key=lambda r: r.position, reverse=True)
        role_list = []
        for r in roles:
            if r.name == "@everyone":
                continue
            role_list.append(f"{r.mention} — ID: `{r.id}` — Members: {len(r.members)}")

        if not role_list:
            await ctx.send("No roles in this server.")
            return

        text = "\n".join(role_list)
        if len(text) <= 1900:
            embed = discord.Embed(
                title=f"Roles in {ctx.guild.name} ({len(role_list)})",
                description=text,
                color=discord.Color.blurple()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"**Roles in {ctx.guild.name} ({len(role_list)}):**")
            chunk = []
            size = 0
            for line in role_list:
                if size + len(line) + 1 > 1900:
                    await ctx.send("\n".join(chunk))
                    chunk = [line]
                    size = len(line)
                else:
                    chunk.append(line)
                    size += len(line) + 1
            if chunk:
                await ctx.send("\n".join(chunk))

    @tuna.command(name="categories")
    @tuna_admin_or_owner()
    async def tuna_categories(self, ctx):
        if not ctx.guild:
            await ctx.send("This command must be used in a server.")
            return

        categories = ctx.guild.by_category
        lines = []
        for cat, channels in categories:
            cat_name = cat.name if cat else "No Category"
            ch_names = [f"  - {ch.mention} (`{ch.id}`)" for ch in channels if isinstance(ch, discord.TextChannel) or isinstance(ch, discord.VoiceChannel)]
            if ch_names:
                lines.append(f"**{cat_name}**")
                lines.extend(ch_names)

        if not lines:
            await ctx.send("No channels found.")
            return

        text = "\n".join(lines)
        if len(text) <= 1900:
            await ctx.send(text)
        else:
            chunk = []
            size = 0
            for line in lines:
                if size + len(line) + 1 > 1900:
                    await ctx.send("\n".join(chunk))
                    chunk = [line]
                    size = len(line)
                else:
                    chunk.append(line)
                    size += len(line) + 1
            if chunk:
                await ctx.send("\n".join(chunk))

    @tuna.group(name="embed")
    @tuna_admin_or_owner()
    async def tuna_embed(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("Use `!tuna embed status`, `!tuna embed restore`, or `!tuna embed export`")

    @tuna_embed.command(name="status")
    @tuna_admin_or_owner()
    async def tuna_embed_status(self, ctx):
        records = _load_view_records()
        if not records:
            await ctx.send("📂 No persistent embed records found.")
            return

        total = len(records)
        per_channel: dict[int, list[int]] = {}
        for r in records:
            cid = r.get("channel_id")
            mid = r.get("message_id")
            if cid is not None:
                per_channel.setdefault(cid, []).append(mid)

        embed = discord.Embed(
            title="📂 Stored Embed Records",
            description=f"**{total}** persistent embed(s) stored across **{len(per_channel)}** channel(s).",
            color=discord.Color.blurple()
        )

        shown = 0
        for cid, mids in per_channel.items():
            if shown >= 10:
                embed.add_field(name="...", value=f"And {len(per_channel) - 10} more channel(s)", inline=False)
                break
            channel = self.bot.get_channel(cid)
            ch_name = f"#{channel.name}" if channel else f"`{cid}` (unknown)"
            embed.add_field(name=ch_name, value=f"{len(mids)} embed(s)", inline=True)
            shown += 1

        footer_parts = []
        alive = sum(1 for r in records if r.get("message_id"))
        if alive:
            footer_parts.append(f"{alive} have message IDs registered")
        if not alive:
            footer_parts.append("No message IDs registered (orphaned)")
        embed.set_footer(text=" | ".join(footer_parts))

        await ctx.send(embed=embed)

    @tuna_embed.command(name="restore")
    @tuna_admin_or_owner()
    async def tuna_embed_restore(self, ctx, channel: discord.TextChannel = None):
        records = _load_view_records()
        if not records:
            await ctx.send("📂 No persistent embed records found to restore.")
            return

        target_channel = channel
        restored = 0
        failed = 0
        status_msg = await ctx.send(f"🔄 Restoring {len(records)} embed(s)...")

        for i, record in enumerate(records):
            source = record.get("source", "")
            ch_id = record.get("channel_id")
            if not source or not ch_id:
                failed += 1
                continue

            ch = target_channel or self.bot.get_channel(ch_id)
            if not ch:
                failed += 1
                continue

            try:
                view = _parse_embed_file(source)
                await ch.send(view=view, allowed_mentions=NO_MENTIONS)
                restored += 1
            except Exception:
                failed += 1

            if i > 0 and i % 5 == 0:
                await status_msg.edit(
                    content=f"🔄 Restoring embeds... ({restored} done, {failed} failed, {len(records) - i - 1} remaining)"
                )

            await asyncio.sleep(0.5)

        embed = discord.Embed(
            title="✅ Restore Complete",
            color=discord.Color.green()
        )
        embed.add_field(name="Restored", value=str(restored), inline=True)
        embed.add_field(name="Failed", value=str(failed), inline=True)
        embed.add_field(name="Total Records", value=str(len(records)), inline=True)
        if target_channel:
            embed.add_field(name="Target Channel", value=target_channel.mention, inline=False)
        else:
            embed.add_field(name="Note", value="Embeds were restored to their original channels.", inline=False)

        await status_msg.edit(content=None, embed=embed)

    @tuna_embed.command(name="export")
    @tuna_admin_or_owner()
    async def tuna_embed_export(self, ctx):
        if not os.path.exists(PERSISTENT_VIEWS_FILE):
            await ctx.send("📂 No persistent view records file found.")
            return

        try:
            with open(PERSISTENT_VIEWS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not data:
                await ctx.send("📂 The persistent views file is empty.")
                return

            bio = BytesIO()
            bio.write(json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8"))
            bio.seek(0)

            file = discord.File(bio, filename="embeds_export.json")
            await ctx.send(
                f"📂 Here are all {len(data)} stored embed record(s):",
                file=file
            )
        except Exception as e:
            await ctx.send(f"❌ Failed to export embed records: {str(e)}")


async def setup(bot: commands.Bot):
    await bot.add_cog(MiscCog(bot))