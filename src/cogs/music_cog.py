import discord
from discord.ext import commands
from music_cog.music_loader import load_source, MusicSource, YTDL_load_info, MusicLoader, load_youtube_playlist
from music_cog.util import embed_text
from random import shuffle
from async_timeout import timeout
from music_cog.song import Song, SongTask
from music_cog.spotify_loader import SpotifyLoader
from music_cog import config
import asyncio

class Playlist(asyncio.Queue):
    def __init__(self, loader: MusicLoader):
        super().__init__()
        self.loader = loader

    def clear(self):
        self._queue.clear()

    async def shuffle(self):
        shuffle(self._queue)

        # reset the workqueue
        self.loader.clear_tasks()
        for song in self._queue:
            await self.loader.put_songtask(song.songtask)

    @property
    def is_empty(self):
        return len(self._queue) == 0

    def __str__(self) -> str:
        ret = "" if len(self._queue) <= config.QUEUE_EMBED_MAX_LEN else f"**Showing first {config.QUEUE_EMBED_MAX_LEN} items:**\n"

        for i, song in list(enumerate(self._queue))[:config.QUEUE_EMBED_MAX_LEN]:
            ret = ret + f"**{i+1}.** {str(song)}\n"
        
        if not len(self._queue):
            ret = "*empty*"

        return ret

class MusicState:
    def __init__(self, bot: commands.Bot):
        self.vc: discord.VoiceClient = None
        self.channel = None
        self.bot = bot
        self.current_song = None
        self.song_ended = asyncio.Event()
        self.task = self.bot.loop.create_task(self._play_song())
        self._is_looping = False
        self._is_paused = False
        self._is_inactive = False
        self._is_perma = False
        self.loader = MusicLoader(self.bot)
        self.playlist = Playlist(self.loader)
        self._volume = config.DEFAULT_VOLUME

    @property
    def volume(self):
        return self._volume
    
    @volume.setter
    def volume(self, val: float):
        self._volume = val

    def reset_volume(self):
        self.volume = config.DEFAULT_VOLUME

    @property
    def is_looping(self):
        return self._is_looping
    
    @property
    def is_paused(self):
        return self._is_paused

    @is_paused.setter
    def is_paused(self, val: bool):
        self._is_paused = val
        self.refresh_pause_state()

    @property
    def is_inactive(self):
        return self._is_inactive

    @is_inactive.setter
    def is_inactive(self, val: bool):
        self._is_inactive = val
        self.refresh_pause_state()

    @property
    def is_perma(self):
        return self._is_perma

    @is_perma.setter
    def is_perma(self, val: bool):
        self._is_perma = val
        self.refresh_pause_state()

    @is_looping.setter
    def is_looping(self, val: bool):
        self._is_looping = val

    @property
    def is_playing(self):
        if self.current_song and self.vc:
            return True
        return False

    @property
    def is_empty(self):
        return not self.current_song and self.playlist.is_empty

    def __del__(self):
        self.task.cancel()

    async def connect(self, channel: discord.VoiceChannel):
        self.channel = channel
        if self.vc:
            await self.vc.move_to(channel)
        else: 
            self.vc = await channel.connect()
        await self.voice_state_update()

    async def _play_song(self):
        if not self.is_looping:
            try:
                async with timeout(config.INACTIVITY_TIMEOUT):
                    self.current_song = await self.playlist.get()
            except asyncio.TimeoutError:
                self.bot.loop.create_task(self.cleanup())
                return
        info = await self.current_song.info
        source_url = info.get("url")
        if not source_url:
            self._next_song()
            print("_play_song song not found: skipping")
            return
        audio_source = await load_source(source_url, self.volume)
        self.vc.play(audio_source, after=self._next_song)
        
    def _next_song(self, error=None):
        if error:
            print(str(error))
            return
        self.task = self.bot.loop.create_task(self._play_song())

    def skip_song(self):
        self.vc.stop()

    async def add_song(self, ctx: commands.Context, query: str):
        if "spotify.com/playlist" in query:
            songs = await SpotifyLoader.load_spotify_playlist(query, self.bot.loop)
            if not songs:
                await ctx.send(embed=embed_text("Error: Empty or invalid Spotify playlist"))
                return
            shuffle(songs)
            for song in songs:
                info = await song.info
                query = info.get("title") + " " + info.get("artist") + " lyrics"
                songtask = await self.loader.add_task(query)
                await self.loader.put_songtask(songtask)
                song.add_task(songtask)
                await self.playlist.put(song)
            await ctx.message.add_reaction("🎵")
        elif "youtube" in query and "list=" in query:
            entries = await load_youtube_playlist(query, self.bot.loop)
            if not entries:
                await ctx.send(embed=embed_text("Error: Empty or invalid YouTube playlist"))
                return
            shuffle(entries)
            for entry in entries:
                song = Song(entry)
                await self.playlist.put(song)
            await ctx.message.add_reaction("🎵")
        else:
            songtask = await self.loader.add_task(query)
            await self.loader.put_songtask(songtask)
            info = {
                "query": query
            }
            song = Song(info)
            song.add_task(songtask)
            await self.playlist.put(song)
            await ctx.message.add_reaction("🎵")
        """
        url, info = await YTDL_load_info(url, self.bot.loop)
        song = Song(url, info)
        await self.playlist.put(song)
        """
    async def shuffle_playlist(self):
        await self.playlist.shuffle()

    def __str__(self) -> str:
        return f"**Current song:**\n{str(self.current_song)}\n\n**Queue**:\n{str(self.playlist)}"

    async def cleanup(self):
        self.playlist.clear()
        if self.vc:
            await self.vc.disconnect()
            self.vc = None
    
    async def voice_state_update(self):
        if not self.channel:
            return
        active = False
        for member in self.channel.members:
            if member.bot:
                continue
            if not member.voice.mute and not member.voice.self_mute:
                active = True
                break
        self.is_inactive = not active

    def refresh_pause_state(self):
        if not self.vc:
            return
        if self.is_paused or (not self.is_perma and self.is_inactive):
            self.vc.pause()
        else:
            self.vc.resume()

    def clear(self):
        self.playlist.clear()
        self.skip_song()

class MusicCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.states = dict()

    @commands.command(name="a")
    async def _a(self, ctx: commands.Context):
        await ctx.send(embed=embed_text(f"hi {ctx.author.id}"))

    @commands.command(name="idk")
    async def _idk(self, ctx: commands.Context):
        embed = discord.Embed(description="hi", colour=discord.Color.orange())
        await ctx.send(embed=embed)
    
    @commands.command(name="join")
    async def _join(self, ctx: commands.Context):
        dest = ctx.author.voice.channel
        state = await self.get_state(ctx.guild)
        await state.connect(dest)
        await ctx.message.add_reaction("👍")

    @commands.command(name="leave")
    async def _leave(self, ctx: commands.Context):
        await self.remove_state(ctx)
        await ctx.message.add_reaction("👋")

    @commands.command(name="play")
    async def _play(self, ctx: commands.Context,* , url: str):
        state = await self.get_state(ctx.guild)
        await state.add_song(ctx, url)

    @commands.command(name="skip")
    async def _skip(self, ctx: commands.Context):
        state = await self.get_state(ctx.guild)
        if not state.is_playing:
            await ctx.send(embed=embed_text("Error: No song is currently playing"))
            return
        state.skip_song()
        await ctx.message.add_reaction("↪")

    @commands.command(name="loop")
    async def _loop(self, ctx: commands.Context):
        state = await self.get_state(ctx.guild)
        if not state.is_playing:
            await ctx.send(embed=embed_text("Error: No song is currently playing"))
            return
        state.is_looping = not state.is_looping
        await ctx.message.add_reaction("🔄")

    @commands.command(name="shuffle")
    async def _shuffle(self, ctx: commands.Context):
        state = await self.get_state(ctx.guild)
        await state.shuffle_playlist()
        await ctx.message.add_reaction("🔀")

    @commands.command(name="queue")
    async def _queue(self, ctx: commands.Context):
        state = await self.get_state(ctx.guild)
        await ctx.send(embed=embed_text(str(state)))

    @commands.command(name="pause")
    async def _pause(self, ctx: commands.Context):
        state = await self.get_state(ctx.guild)
        if not state.is_playing or state.is_paused:
            await ctx.send(embed=embed_text("Error: music player is empty or already paused"))
            return
        state.is_paused = True
        await ctx.message.add_reaction("⏸")

    @commands.command(name="resume")
    async def _resume(self, ctx: commands.Context):
        state = await self.get_state(ctx.guild)
        if not state.is_paused:
            await ctx.send(embed=embed_text("Error: music player is currently playing"))
            return
        state.is_paused = False
        await ctx.message.add_reaction("▶")
    
    @commands.command(name="perma")
    async def _perma(self, ctx: commands.Context):
        state = await self.get_state(ctx.guild)
        state.is_perma = not state.is_perma
        await ctx.message.add_reaction("👍")

    @commands.command(name="clear")
    async def _clear(self, ctx: commands.Context):
        state = await self.get_state(ctx.guild)
        if state.is_empty:
            await ctx.send(embed=embed_text("Error: no songs are currently queued/playing"))
            return
        state.clear()
        await ctx.message.add_reaction("🗑")

    @commands.Cog.listener(name="on_voice_state_update")
    async def _on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        
        state = await self.get_state(member.guild)
        if before.channel != state.channel or after.channel != state.channel:
            return
        await state.voice_state_update()

    async def get_state(self, guild: discord.Guild) -> MusicState:
        if guild.id in self.states:
            return self.states[guild.id]
        state = MusicState(self.bot)
        self.states[guild.id] = state
        return state
    
    async def remove_state(self, ctx: commands.Context):
        if not ctx.guild.id in self.states:
            await ctx.send("Attemped to leave invalid or non-existent voice channel")
            return
        await self.states[ctx.guild.id].cleanup()
        del self.states[ctx.guild.id]