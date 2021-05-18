from music_cog.util import time_parse
import asyncio

class SongTask:
    def __init__(self):
        self.task: asyncio.Task = None
        self.event = asyncio.Event()

    async def wait_loader(self):
        return await self.task

class Song:
    def __init__(self, info):
        self._info = info
        self.songtask = None

    def add_task(self, task: SongTask):
        self.songtask = task

    def update_info(self, info):
        if not info:
            return
        for key in ["title", "artist", "duration", "url"]:
            self._info[key] = self._info.get(key) or info.get(key)

    @property
    async def info(self):
        if not self.songtask:
            return self._info
        info = await self.songtask.wait_loader()
        self.update_info(info)
        self.songtask = None
        return self._info

    @property
    def title(self):
        return self._info.get("title") or self._info.get("query")

    @property
    def artist(self):
        return self._info.get("artist") or "Unknown artist"

    @property
    def duration(self):
        duration = self._info.get("duration")
        if not duration:
            return "Unknown length"
        return time_parse(duration)
    
    def __str__(self) -> str:
        return f"{self.title} by {self.artist}  -  {self.duration}"