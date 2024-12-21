import discord
from discord.ext import tasks
import tmdbsimple as tmdb
import json
import os
import requests
from datetime import datetime

# Load configuration from config.json or environment variables
CONFIG_FILE = "config.json"

if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r") as file:
        config = json.load(file)
else:
    config = {
        "DISCORD_BOT_TOKEN": os.getenv("DISCORD_BOT_TOKEN", ""),
        "TMDB_API_KEY": os.getenv("TMDB_API_KEY", ""),
        "TRAKT_API_KEY": os.getenv("TRAKT_API_KEY", ""),
        "CHANNEL_ID": int(os.getenv("CHANNEL_ID", 0)),
        "POST_TIME": os.getenv("POST_TIME", "12:00")
    }

# Assign variables
DISCORD_BOT_TOKEN = config["DISCORD_BOT_TOKEN"]
TMDB_API_KEY = config["TMDB_API_KEY"]
TRAKT_API_KEY = config["TRAKT_API_KEY"]
CHANNEL_ID = config["CHANNEL_ID"]
POST_TIME = config["POST_TIME"]

# Configure TMDb API
tmdb.API_KEY = TMDB_API_KEY

# Configure Trakt API headers
trakt_headers = {
    "Content-Type": "application/json",
    "trakt-api-version": "2",
    "trakt-api-key": TRAKT_API_KEY
}

# Bot setup
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
bot = discord.Client(intents=intents)

# Fetch trending movies from TMDb
def fetch_tmdb_trending_movies():
    trending = tmdb.Trending('movie', 'week')
    return trending.info().get('results', [])

# Fetch trending TV shows from TMDb
def fetch_tmdb_trending_shows():
    trending = tmdb.Trending('tv', 'week')
    return trending.info().get('results', [])

# Fetch trending movies from Trakt
def fetch_trakt_trending_movies():
    response = requests.get("https://api.trakt.tv/movies/trending", headers=trakt_headers)
    return response.json() if response.status_code == 200 else []

# Fetch trending TV shows from Trakt
def fetch_trakt_trending_shows():
    response = requests.get("https://api.trakt.tv/shows/trending", headers=trakt_headers)
    return response.json() if response.status_code == 200 else []

# Create an embed for content
def create_embed(item, media_type):
    title = item.get("title") or item.get("name")
    description = item.get("overview", "No description available.")
    rating = f"{item.get('vote_average', 'N/A')} ({item.get('vote_count', 'N/A')} votes)"
    poster_url = f"https://image.tmdb.org/t/p/w500{item.get('poster_path')}" if item.get("poster_path") else None

    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blue()
    )
    embed.add_field(name="Rating", value=rating, inline=False)
    if poster_url:
        embed.set_image(url=poster_url)
    return embed

# Post trending content
async def post_trending_content():
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        print(f"Channel with ID {CHANNEL_ID} not found!")
        return

    # Post movies
    tmdb_movies = fetch_tmdb_trending_movies()[:5]
    trakt_movies = fetch_trakt_trending_movies()[:5]
    await channel.send("🎥 **Trending Movies**:")
    for movie in tmdb_movies + trakt_movies:
        embed = create_embed(movie, "movie")
        await channel.send(embed=embed)

    # Post TV shows
    tmdb_shows = fetch_tmdb_trending_shows()[:5]
    trakt_shows = fetch_trakt_trending_shows()[:5]
    await channel.send("📺 **Trending TV Shows**:")
    for show in tmdb_shows + trakt_shows:
        embed = create_embed(show, "tv")
        await channel.send(embed=embed)

# Scheduled task for posting
@tasks.loop(minutes=1)
async def scheduled_post():
    now = datetime.now().strftime("%H:%M")
    if now == POST_TIME:
        await post_trending_content()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    scheduled_post.start()

# Run the bot
bot.run(DISCORD_BOT_TOKEN)
