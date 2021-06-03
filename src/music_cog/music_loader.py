import youtube_dl
import asyncio
import discord
from discord.ext import commands
import functools
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from music_cog import config
from music_cog.song import SongTask

YTDL = youtube_dl.YoutubeDL(config.YTDL_OPTIONS)

Client = Spotify(client_credentials_manager=SpotifyClientCredentials(client_id='5f573c9620494bae87890c0f08a60293',client_secret='212476d9b0f3472eaa762d90b19b0ba8'))

class MusicSource(discord.PCMVolumeTransformer):
    pass

async def query_load_info(query: str, loop: asyncio.BaseEventLoop):
    info = await YTDL_load_info
    pass

async def YTDL_load_info(query: str, loop: asyncio.BaseEventLoop):
    method = functools.partial(YTDL.extract_info, query, download=False)
    info = await loop.run_in_executor(None, method)
    return info

async def load_source(url: str, volume: float):
    source = discord.FFmpegPCMAudio(url, **config.FFMPEG_OPTIONS)
    return discord.PCMVolumeTransformer(source, volume=volume)

class MusicLoaderQueue(asyncio.Queue):
    def clear(self):
        self._queue.clear()

class MusicLoader:
    def __init__(self, bot:commands.Bot):
        self._workqueue = MusicLoaderQueue()
        self._sem = asyncio.Semaphore(config.MAX_LOAD_COUNT)
        self._bot = bot
        self._load_next_task = bot.loop.create_task(self._load_next())

    async def put_songtask(self, task: SongTask):
        await self._workqueue.put(task)

    async def get_songtask(self) -> SongTask:
        return await self._workqueue.get()

    # note: does not cancel active tasks, that is done through Playlist
    def clear_tasks(self):
        self._workqueue.clear()

    async def _load_next(self):
        while True:
            songtask = await self.get_songtask()
            if songtask.started:
                continue
            await self._sem.acquire() 
            songtask.event.set()
            songtask.started = True

    async def add_task(self, query: str) -> asyncio.Task:
        song_task = SongTask()
        song_task.task = self._bot.loop.create_task(self._load_song(query, song_task.event)) 
        return song_task

    async def _load_song(self, query: str, event: asyncio.Event):
        await event.wait()
        info = await self._YTDL_search_song(query)
        self._sem.release()
        return info

    async def _YTDL_search_song(self, query: str):
        async def YTDL_load_info(query: str):
            ytdl = youtube_dl.YoutubeDL(config.YTDL_OPTIONS)
            try:
                method = functools.partial(ytdl.extract_info, query, download=False)
                info = await self._bot.loop.run_in_executor(None, method)
            except Exception as e:
                print(f"error: {e}")
                info = dict()
            return info
        info = await self._bot.loop.create_task(YTDL_load_info(query))
        url = info.get("url")
        if not url:
            entries = info.get("entries")
            if not entries:
                print(f"song not found: {query}")
                return
            webpage_url = entries[0].get("webpage_url")
            if not webpage_url:
                print(f"song not found: {query}")
                return
            info = await self._bot.loop.create_task(YTDL_load_info(webpage_url))
            url = info.get("url")
            if not url:
                print(f"song not found: {query}")
                return
        return info

    def cleanup(self):
        self._load_next_task.cancel()
    
    def _del_(self):
        self._load_next_task.cancel()

async def load_youtube_playlist(url: str, loop: asyncio.BaseEventLoop):
    async def YTDL_load_info(query: str):
        ytdl = youtube_dl.YoutubeDL(config.YTDL_OPTIONS)
        method = functools.partial(ytdl.extract_info, query, download=False)
        info = await loop.run_in_executor(None, method)
        return info
    info = await loop.create_task(YTDL_load_info(url))
    entries = info.get("entries")
    return entries
