import youtube_dl
import json
import os
from dotenv import load_dotenv
import asyncio
import discord
from discord.ext import commands
from discord.utils import get

bot = commands.Bot(command_prefix="-")

load_dotenv()
TOKEN = os.getenv("TOKEN")

_queue = []
player = None

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.command(brief="Makes the bot join your channel", aliases=['j', 'jo'])
async def join(ctx):
    channel = ctx.message.author.voice.channel
    if not channel:
        await ctx.send("You are not connected to a voice channel")
        return
    voice = get(bot.voice_clients, guild=ctx.guild)
    if voice and voice.is_connected():
        await voice.move_to(channel)
    else:
        voice = await channel.connect()
    await voice.disconnect()
    if voice and voice.is_connected():
        await voice.move_to(channel)
    else:
        voice = await channel.connect()
    await ctx.send(f"Joined {channel}")

@bot.command()
async def queue(ctx,*,song_name=...):
    global _queue
    _queue.append(song_name)
    embed = discord.Embed(color=discord.Color.blue(),description=f'Queued: [`{player.title}`]({player.url}) [{ctx.author.mention}]')
    await ctx.send(embed=embed)


@bot.command(aliases=["p"])
async def play(ctx, *, url):
    """Plays from a url (almost anything youtube_dl supports)"""
    global player
    global _queue
    try:
        async with ctx.channel.typing():
            player = await YTDLSource.from_url(url, loop=bot.loop,stream=True)
            ctx.voice_client.play(player, after=lambda e: print('Player error: %s' % e) if e else None)

        embed = discord.Embed(color=discord.Color.blue(),description=f'Now Playing: [`{player.title}`]({player.url}) [{ctx.author.mention}]')
        await ctx.send(embed=embed)
        with open("data","w") as f:
            json.dump(player.data,f)
        length = player.data['duration']
        await asyncio.sleep(length)
    except discord.ClientException:
        _queue.append(url)
        embed = discord.Embed(color=discord.Color.blue(),description=f'Queued [`{player.title}`]({player.url}) [{ctx.author.mention}]')
        return await ctx.send(embed=embed)
    for item in _queue:
        async with ctx.channel.typing():
            player = await YTDLSource.from_url(item, loop=bot.loop,stream=True)
            ctx.voice_client.play(player, after=lambda e: print('Player error: %s' % e) if e else None)

        embed = discord.Embed(color=discord.Color.blue(),description=f'Now Playing: [`{player.title}`]({player.url}) [{ctx.author.mention}]')
        await ctx.send(embed=embed)
        length = player.data['duration']
        await asyncio.sleep(length)
        

bot.run(TOKEN)
