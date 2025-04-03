from bot.client import setup_client
from dotenv import load_dotenv
import os

load_dotenv()

if __name__ == "__main__":
    client = setup_client()
    client.run(os.getenv('DISCORD_TOKEN'))