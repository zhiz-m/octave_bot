import discord
from discord.ext import commands
from cogs.music_cog import MusicCog

if __name__ == "__main__":
    bot = commands.Bot("a.",description="Octave")
    bot.add_cog(MusicCog(bot))

    bot.run("token")