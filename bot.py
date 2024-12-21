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

# Command Tree for slash commands
bot.tree = discord.app_commands.CommandTree(bot)

# Fetch trending movies from TMDb
def fetch_tmdb_trending_movies():
    trending = tmdb.Trending('movie', 'week')
    return trending.info().get('results', [])

# Fetch trending TV shows from TMDb
def fetch_tmdb_trending_shows():
    trending = tmdb.Trending('tv', 'week')
    return trending.info().get('results', [])

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

# Create an embed field for content
def create_embed_field(item, media_type):
    if media_type == "movie":
        title = item.get("title")
        trailer = f"https://www.youtube.com/results?search_query={title}+trailer" if title else "No trailer available"
        return f"**{title}**\nRating: {item.get('vote_average', 'N/A')} ({item.get('vote_count', 'N/A')} votes)\n[Trailer]({trailer})"
    elif media_type == "tv":
        return f"**{item.get('name')}**\nRating: {item.get('vote_average', 'N/A')} ({item.get('vote_count', 'N/A')} votes)"
    elif media_type == "anime":
        return f"**{item['title']['romaji']}**\nScore: {item.get('averageScore', 'N/A')}/100"

# Post trending content in a single message
async def post_trending_content():
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        print(f"Channel with ID {CHANNEL_ID} not found!")
        return

    tmdb_movies = fetch_tmdb_trending_movies()[:5]
    tmdb_shows = fetch_tmdb_trending_shows()[:5]
    anilist_anime = fetch_anilist_current_season()

    embed = discord.Embed(
        title="🎥📺🍥 Trending Content This Week",
        description="Here are the top movies, TV shows, and anime for this week!",
        color=discord.Color.blue()
    )

    # Add movies
    movie_fields = [create_embed_field(movie, "movie") for movie in tmdb_movies]
    embed.add_field(name="🎥 Trending Movies", value="\n\n".join(movie_fields), inline=False)

    # Add TV shows
    tv_fields = [create_embed_field(show, "tv") for show in tmdb_shows]
    embed.add_field(name="📺 Trending TV Shows", value="\n\n".join(tv_fields), inline=False)

    # Add anime
    anime_fields = [create_embed_field(anime, "anime") for anime in anilist_anime]
    embed.add_field(name="🍥 Current Anime Season", value="\n\n".join(anime_fields), inline=False)

    # Add thumbnail
    embed.set_thumbnail(url="https://image.tmdb.org/t/p/w200" + tmdb_movies[0].get("poster_path", ""))

    await channel.send(embed=embed)

# Slash command to post trending content
@bot.tree.command(name="post_trending", description="Manually post trending content.")
async def post_trending_command(interaction: discord.Interaction):
    await post_trending_content()
    await interaction.response.send_message("Trending content posted!", ephemeral=True)

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

# Run the bot
bot.run(DISCORD_BOT_TOKEN)
