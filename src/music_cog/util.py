import discord

def embed_text(description: str, color: discord.Color = discord.Color.orange()):
    return discord.Embed(description=description, color=color)

def time_parse(s: int):
    minutes = s // 60
    seconds = s - minutes * 60

    return f"{minutes}:{seconds:02}"