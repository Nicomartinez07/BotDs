import discord
from discord import Intents

def setup_client():
    intents = Intents.default()
    intents.message_content = True
    intents.messages = True
    intents.dm_messages = True
    intents.members = True
    
    client = discord.Client(intents=intents)
    return client