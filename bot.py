import discord
from discord.ext import tasks
import tmdbsimple as tmdb
import json
import os
import requests
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
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

# Configure APIs
tmdb.API_KEY = TMDB_API_KEY
trakt_headers = {
    "Content-Type": "application/json",
    "trakt-api-version": "2",
    "trakt-api-key": TRAKT_API_KEY
}
anilist_transport = RequestsHTTPTransport(url="https://graphql.anilist.co", use_json=True)
anilist_client = Client(transport=anilist_transport, fetch_schema_from_transport=True)

# Bot setup
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
bot = discord.Client(intents=intents)
bot.tree = discord.app_commands.CommandTree(bot)

# Fetch trending movies from TMDb
def fetch_tmdb_trending_movies():
    trending = tmdb.Trending('movie', 'week')
    return trending.info().get('results', [])[:10]

# Fetch trending TV shows from TMDb
def fetch_tmdb_trending_shows():
    trending = tmdb.Trending('tv', 'week')
    return trending.info().get('results', [])[:10]

# Fetch current anime season from AniList
def fetch_anilist_current_season():
    try:
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
    except Exception as e:
        print(f"Error fetching AniList data: {e}")
        return []

# Create an embed for an item
def create_embed(item, media_type):
    if media_type == "movie":
        title = item.get("title")
        trailer = f"https://www.youtube.com/results?search_query={title}+trailer" if title else "No trailer available"
        rating = item.get("vote_average", "N/A")
        votes = item.get("vote_count", "N/A")
        poster_url = f"https://image.tmdb.org/t/p/w500{item.get('poster_path', '')}"
        embed = discord.Embed(
            title=title,
            description=f"⭐ **{rating}/10** ({votes} votes)\n[Trailer]({trailer})",
            color=discord.Color.blue()
        )
        embed.set_image(url=poster_url)
        return embed
    elif media_type == "tv":
        title = item.get("name")
        rating = item.get("vote_average", "N/A")
        votes = item.get("vote_count", "N/A")
        poster_url = f"https://image.tmdb.org/t/p/w500{item.get('poster_path', '')}"
        embed = discord.Embed(
            title=title,
            description=f"⭐ **{rating}/10** ({votes} votes)",
            color=discord.Color.green()
        )
        embed.set_image(url=poster_url)
        return embed
    elif media_type == "anime":
        title = item["title"]["romaji"]
        score = item.get("averageScore", "N/A")
        poster_url = item["coverImage"]["large"]
        embed = discord.Embed(
            title=title,
            description=f"Score: **{score}/100**",
            color=discord.Color.orange()
        )
        embed.set_image(url=poster_url)
        return embed

# Post trending content in multiple embeds
async def post_trending_content():
    if not CHANNEL_ID:
        print("CHANNEL_ID is not set or invalid.")
        return

    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        print(f"Channel with ID {CHANNEL_ID} not found!")
        return

    try:
        tmdb_movies = fetch_tmdb_trending_movies()
        tmdb_shows = fetch_tmdb_trending_shows()
        anilist_anime = fetch_anilist_current_season()

        # Post movies
        movie_embeds = []
        for movie in tmdb_movies:
            embed = create_embed(movie, "movie")
            movie_embeds.append(embed)
        await channel.send("🎥 **Trending Movies**", embeds=movie_embeds)

        # Post TV shows
        tv_embeds = []
        for show in tmdb_shows:
            embed = create_embed(show, "tv")
            tv_embeds.append(embed)
        await channel.send("📺 **Trending TV Shows**", embeds=tv_embeds)

        # Post anime
        anime_embeds = []
        for anime in anilist_anime:
            embed = create_embed(anime, "anime")
            anime_embeds.append(embed)
        await channel.send("🍥 **Current Anime Season**", embeds=anime_embeds)

    except Exception as e:
        print(f"Error posting trending content: {e}")

# Slash command to post trending content
@bot.tree.command(name="post_trending", description="Manually post trending content.")
async def post_trending_command(interaction: discord.Interaction):
    await interaction.response.defer()  # Acknowledge the interaction immediately
    try:
        await post_trending_content()
        await interaction.followup.send("Trending content posted!")
    except Exception as e:
        await interaction.followup.send(f"Failed to post content: {e}")

# Scheduled task for posting
@tasks.loop(minutes=1)
async def scheduled_post():
    now = datetime.now().strftime("%H:%M")
    if now == POST_TIME:
        await post_trending_content()

# Sync slash commands on bot startup
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        await bot.tree.sync()
        print("Slash commands synced successfully!")
    except Exception as e:
        print(f"Error syncing slash commands: {e}")
    scheduled_post.start()

bot.run(DISCORD_BOT_TOKEN)
