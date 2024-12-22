import discord
from discord.ext import tasks
import tmdbsimple as tmdb
import json
import os
import requests
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
from datetime import datetime
from urllib.parse import quote

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
                    averageScore
                    popularity
                    status
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

# Helper to format movie embeds
def format_movie_embed(movie):
    try:
        details = tmdb.Movies(movie["id"]).info()
        title = details.get("title", "Unknown Title")
        rating = f"{details.get('vote_average', 0):.1f}/10 ({details.get('vote_count', 0)} votes)"
        watchers = fetch_trakt_watching(generate_slug(title), "movies")
        tagline = details.get("tagline", "No tagline available.")
        genres = ", ".join([genre["name"] for genre in details.get("genres", [])[:2]])
        runtime = f"{details.get('runtime', 'N/A')} minutes"
        release_date = details.get("release_date", "N/A")
        trakt_link = f"https://trakt.tv/movies/{generate_slug(title)}"
        trailer = f"https://www.youtube.com/results?search_query={quote(title)}+trailer"
        poster_url = f"https://image.tmdb.org/t/p/w200{details.get('poster_path', '')}"

        embed = discord.Embed(
            title=title,
            description=f"⭐ **{rating}**\n"
                        f"👀 **{watchers}** people currently watching\n\n"
                        f"🎭 **Genres**: {genres}\n"
                        f"🕒 **Runtime**: {runtime}\n"
                        f"🎥 **Release Date**: {release_date}\n\n"
                        f"📜 **Tagline**: {tagline}\n"
                        f"🔗 [Watch Trailer!]({trailer})\n"
                        f"🔗 [Trakt]({trakt_link})",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=poster_url)
        return embed
    except Exception as e:
        print(f"Error creating movie embed: {e}")
        return None

# Helper to format TV show embeds
def format_tv_embed(show):
    try:
        details = tmdb.TV(show["id"]).info()
        title = details.get("name", "Unknown Title")
        rating = f"{details.get('vote_average', 0):.1f}/10 ({details.get('vote_count', 0)} votes)"
        watchers = fetch_trakt_watching(generate_slug(title), "shows")
        genres = ", ".join([genre["name"] for genre in details.get("genres", [])[:2]])
        episode_length = f"{details.get('episode_run_time', ['N/A'])[0]} minutes"
        status = details.get("status", "N/A")
        trakt_link = f"https://trakt.tv/shows/{generate_slug(title)}"
        poster_url = f"https://image.tmdb.org/t/p/w200{details.get('poster_path', '')}"

        embed = discord.Embed(
            title=title,
            description=f"⭐ **{rating}**\n"
                        f"👀 **{watchers}** people currently watching\n\n"
                        f"🎭 **Genres**: {genres}\n"
                        f"🕒 **Episode Length**: {episode_length}\n"
                        f"📅 **Status**: {status}\n\n"
                        f"🔗 [Trakt]({trakt_link})",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=poster_url)
        return embed
    except Exception as e:
        print(f"Error creating TV embed: {e}")
        return None

# Helper to format anime embeds
def format_anime_embed(anime):
    try:
        title = anime["title"]["romaji"]
        score = anime.get("averageScore", "N/A")
        popularity = anime.get("popularity", "N/A")
        status = anime.get("status", "N/A").capitalize()
        anilist_link = f"https://anilist.co/anime/{anime.get('id', '')}"
        poster_url = anime["coverImage"]["large"]

        embed = discord.Embed(
            title=title,
            description=f"⭐ **Score**: {score}/100\n"
                        f"👥 **Popularity**: {popularity}\n"
                        f"📅 **Status**: {status}\n\n"
                        f"🔗 [AniList]({anilist_link})",
            color=discord.Color.orange()
        )
        embed.set_thumbnail(url=poster_url)
        return embed
    except Exception as e:
        print(f"Error creating anime embed: {e}")
        return None

# Generate slug for Trakt
def generate_slug(title):
    return title.lower().replace(" ", "-").replace(":", "").replace(",", "")

# Fetch users currently watching from Trakt
def fetch_trakt_watching(slug, media_type):
    try:
        url = f"https://api.trakt.tv/{media_type}/{slug}/watching"
        response = requests.get(url, headers=trakt_headers)
        if response.status_code == 200:
            return len(response.json())  # Count of users watching
        return 0
    except Exception as e:
        print(f"Error fetching Trakt watching data for {slug}: {e}")
        return 0

async def post_trending_content():
    """Fetch and post trending content."""
    if not CHANNEL_ID:
        print("CHANNEL_ID is not set or invalid.")
        return

    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        print(f"Channel with ID {CHANNEL_ID} not found!")
        return

    try:
        # Fetch trending data
        tmdb_movies = fetch_tmdb_trending_movies()
        tmdb_shows = fetch_tmdb_trending_shows()
        anilist_anime = fetch_anilist_current_season()

        # Post movies
        if tmdb_movies:
            await channel.send("🎥 **Trending Movies**")
            for movie in tmdb_movies:
                embed = format_movie_embed(movie)
                if embed:
                    await channel.send(embed=embed)

        # Post TV shows
        if tmdb_shows:
            await channel.send("📺 **Trending TV Shows**")
            for show in tmdb_shows:
                embed = format_tv_embed(show)
                if embed:
                    await channel.send(embed=embed)

        # Post anime
        if anilist_anime:
            await channel.send("🍥 **Current Anime Season**")
            for anime in anilist_anime:
                embed = format_anime_embed(anime)
                if embed:
                    await channel.send(embed=embed)

    except Exception as e:
        print(f"Error posting trending content: {e}")

# Slash command to post trending content
@bot.tree.command(name="post_trending", description="Manually post trending content.")
async def post_trending_command(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        await post_trending_content()
        await interaction.followup.send("Trending content posted!")
    except Exception as e:
        await interaction.followup.send(f"Failed to post content: {e}")

# Sync slash commands on bot startup
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    await bot.tree.sync()

bot.run(DISCORD_BOT_TOKEN)
