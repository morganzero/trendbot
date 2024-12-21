import discord
from discord.ext import tasks
import tmdbsimple as tmdb
import json
import os
import requests
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
from datetime import datetime

# Load configuration
CONFIG_FILE = "config.json"

if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'r') as file:
        config = json.load(file)
else:
    config = {
        "DISCORD_BOT_TOKEN": os.getenv("DISCORD_BOT_TOKEN"),
        "TMDB_API_KEY": os.getenv("TMDB_API_KEY"),
        "TRAKT_API_KEY": os.getenv("TRAKT_API_KEY"),
        "POST_TIME": os.getenv("POST_TIME", "12:00")
    }

DISCORD_BOT_TOKEN = config.get("DISCORD_BOT_TOKEN")
TMDB_API_KEY = config.get("TMDB_API_KEY")
TRAKT_API_KEY = config.get("TRAKT_API_KEY")
POST_TIME = config.get("POST_TIME")

# Configure APIs
tmdb.API_KEY = TMDB_API_KEY
trakt_headers = {"Content-Type": "application/json", "trakt-api-version": "2", "trakt-api-key": TRAKT_API_KEY}

anilist_transport = RequestsHTTPTransport(url="https://graphql.anilist.co", use_json=True)
anilist_client = Client(transport=anilist_transport, fetch_schema_from_transport=True)

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

# Fetch current anime season from AniList
def fetch_anilist_current_season():
    query = gql("""
    query {
        Page(page: 1, perPage: 10) {
            media(season: WINTER, seasonYear: 2024, type: ANIME, format_in: [TV]) {
                title {
                    romaji
                }
                description
                averageScore
                coverImage {
                    large
                }
            }
        }
    }
    """)
    result = anilist_client.execute(query)
    return result["Page"]["media"]

# Create an embed for content
def create_embed(item, media_type):
    if media_type == "anime":
        title = item["title"]["romaji"]
        description = item.get("description", "No description available.")
        rating = f"{item.get('averageScore', 'N/A')}/100"
        poster_url = item["coverImage"]["large"]
    else:
        title = item.get("title", item.get("name"))
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
    guild = discord.utils.get(bot.guilds)  # Get the first guild the bot is connected to
    if not guild:
        print("No guilds found!")
        return

    # Create channels if necessary
    movie_channel = discord.utils.get(guild.text_channels, name="movies")
    show_channel = discord.utils.get(guild.text_channels, name="shows")
    anime_channel = discord.utils.get(guild.text_channels, name="anime")

    if not movie_channel:
        movie_channel = await guild.create_text_channel("movies")
    if not show_channel:
        show_channel = await guild.create_text_channel("shows")
    if not anime_channel:
        anime_channel = await guild.create_text_channel("anime")

    # Post movies
    tmdb_movies = fetch_tmdb_trending_movies()[:5]
    trakt_movies = fetch_trakt_trending_movies()[:5]
    await movie_channel.send("🎥 **Trending Movies**:")
    for movie in tmdb_movies + trakt_movies:
        embed = create_embed(movie, "movie")
        await movie_channel.send(embed=embed)

    # Post TV shows
    tmdb_shows = fetch_tmdb_trending_shows()[:5]
    trakt_shows = fetch_trakt_trending_shows()[:5]
    await show_channel.send("📺 **Trending TV Shows**:")
    for show in tmdb_shows + trakt_shows:
        embed = create_embed(show, "tv")
        await show_channel.send(embed=embed)

    # Post anime
    anilist_anime = fetch_anilist_current_season()
    await anime_channel.send("🍥 **Current Anime Season**:")
    for anime in anilist_anime:
        embed = create_embed(anime, "anime")
        await anime_channel.send(embed=embed)

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
