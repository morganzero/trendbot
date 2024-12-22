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
                    description
                    averageScore
                    popularity
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

# Fetch users currently watching from Trakt
def fetch_trakt_watching(slug, media_type):
    try:
        url = f"https://api.trakt.tv/{media_type}/{slug}/watching"
        response = requests.get(url, headers=trakt_headers)
        if response.status_code == 200:
            watching_data = response.json()
            return len(watching_data)  # Count of users watching
        else:
            print(f"Failed to fetch Trakt watching data for {slug}: {response.status_code}")
            return 0
    except Exception as e:
        print(f"Error fetching Trakt watching data for {slug}: {e}")
        return 0

# Generate slug for Trakt
def generate_slug(title):
    return title.lower().replace(" ", "-").replace(":", "").replace(",", "")

def fetch_tmdb_movie_details(movie_id):
    """Fetch detailed movie info including runtime, genres, and tagline."""
    details = tmdb.Movies(movie_id)
    return details.info()


def fetch_tmdb_show_details(show_id):
    """Fetch detailed TV show info including genres, episode runtime, and seasons."""
    details = tmdb.TV(show_id)
    return details.info()


def create_embed(item, media_type):
    trakt_base_url = "https://trakt.tv"

    if media_type == "movie":
        # Fetch detailed information for the movie
        details = fetch_tmdb_movie_details(item["id"])
        title = details.get("title", "Unknown Title")
        release_date = details.get("release_date", "N/A")
        runtime = details.get("runtime", "N/A")
        genres = ", ".join([genre["name"] for genre in details.get("genres", [])[:2]])
        tagline = details.get("tagline", "No tagline available.")
        slug = generate_slug(title)
        watchers = fetch_trakt_watching(slug, "movies")
        trakt_link = f"{trakt_base_url}/movies/{slug}"
        poster_url = f"https://image.tmdb.org/t/p/w200{details.get('poster_path', '')}"

        embed = discord.Embed(
            title=title,
            description=f"⭐ **{details.get('vote_average', 0):.1f}/10** ({details.get('vote_count', 0)} votes)\n"
                        f"🎥 **Release Date**: {release_date}\n"
                        f"🕒 **Runtime**: {runtime} minutes\n"
                        f"🎭 **Genres**: {genres}\n"
                        f"👀 **{watchers}** people currently watching\n"
                        f"📜 **Tagline**: {tagline}\n"
                        f"🔗 [More Info on Trakt]({trakt_link})",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=poster_url)
        return embed

    elif media_type == "tv":
        # Fetch detailed information for the TV show
        details = fetch_tmdb_show_details(item["id"])
        title = details.get("name", "Unknown Title")
        genres = ", ".join([genre["name"] for genre in details.get("genres", [])[:2]])
        episode_length = details.get("episode_run_time", ["N/A"])[0]
        status = details.get("status", "N/A")
        seasons = details.get("number_of_seasons", "N/A")
        slug = generate_slug(title)
        watchers = fetch_trakt_watching(slug, "shows")
        trakt_link = f"{trakt_base_url}/shows/{slug}"
        poster_url = f"https://image.tmdb.org/t/p/w200{details.get('poster_path', '')}"

        embed = discord.Embed(
            title=title,
            description=f"⭐ **{details.get('vote_average', 0):.1f}/10** ({details.get('vote_count', 0)} votes)\n"
                        f"🎭 **Genres**: {genres}\n"
                        f"🕒 **Episode Length**: {episode_length} minutes\n"
                        f"📅 **Status**: {status}\n"
                        f"📺 **Seasons**: {seasons}\n"
                        f"👀 **{watchers}** people currently watching\n"
                        f"🔗 [More Info on Trakt]({trakt_link})",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=poster_url)
        return embed

    elif media_type == "anime":
        title = item["title"]["romaji"]
        score = item.get("averageScore", "N/A")
        episodes = item.get("episodes", "N/A")
        status = "Airing" if item.get("status", "N/A").lower() == "releasing" else "Completed"
        genres = ", ".join(item.get("genres", [])[:2])
        popularity = item.get("popularity", "N/A")
        trakt_link = f"{trakt_base_url}/search?query={quote(title)}"
        poster_url = item["coverImage"]["large"]

        embed = discord.Embed(
            title=title,
            description=f"⭐ **Score**: {score}/100\n"
                        f"📺 **Episodes**: {episodes}\n"
                        f"📅 **Status**: {status}\n"
                        f"🎭 **Genres**: {genres}\n"
                        f"👥 **Popularity**: {popularity}\n"
                        f"🔗 [More Info on Trakt]({trakt_link})",
            color=discord.Color.orange()
        )
        embed.set_thumbnail(url=poster_url)
        return embed


async def send_batched_embeds(channel, embeds, title):
    batch_size = 10
    for i in range(0, len(embeds), batch_size):
        await channel.send(f"**{title}**", embeds=embeds[i:i + batch_size])

async def post_trending_content():
    """Fetch and post trending content with an appealing, emoji-enhanced format."""
    if not CHANNEL_ID:
        print("CHANNEL_ID is not set or invalid.")
        return

    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        print(f"Channel with ID {CHANNEL_ID} not found!")
        return

    try:
        # Fetch trending data
        print("Fetching trending movies...")
        tmdb_movies = fetch_tmdb_trending_movies()
        print(f"Fetched {len(tmdb_movies)} movies.")

        print("Fetching trending TV shows...")
        tmdb_shows = fetch_tmdb_trending_shows()
        print(f"Fetched {len(tmdb_shows)} TV shows.")

        print("Fetching current anime season...")
        anilist_anime = fetch_anilist_current_season()
        print(f"Fetched {len(anilist_anime)} anime titles.")

        # Generate and post embeds
        if tmdb_movies:
            print(f"Posting {len(tmdb_movies)} movie embeds...")
            await channel.send("🎥 **Trending Movies**")
            for movie in tmdb_movies:
                embed = format_movie_embed(movie)
                if embed:
                    await channel.send(embed=embed)

        if tmdb_shows:
            print(f"Posting {len(tmdb_shows)} TV show embeds...")
            await channel.send("📺 **Trending TV Shows**")
            for show in tmdb_shows:
                embed = format_tv_embed(show)
                if embed:
                    await channel.send(embed=embed)

        if anilist_anime:
            print(f"Posting {len(anilist_anime)} anime embeds...")
            await channel.send("🍥 **Current Anime Season**")
            for anime in anilist_anime:
                embed = format_anime_embed(anime)
                if embed:
                    await channel.send(embed=embed)

    except Exception as e:
        print(f"Error posting trending content: {e}")

# Helper to format movie embeds
def format_movie_embed(movie):
    try:
        details = fetch_tmdb_movie_details(movie["id"])
        title = details.get("title", "Unknown Title")
        rating = f"{details.get('vote_average', 0):.1f}/10 ({details.get('vote_count', 0)} votes)"
        watchers = fetch_trakt_watching(generate_slug(title), "movies")
        tagline = details.get("tagline", "No tagline available.")
        genres = ", ".join([genre["name"] for genre in details.get("genres", [])[:2]])
        runtime = f"{details.get('runtime', 'N/A')} minutes"
        release_date = details.get("release_date", "N/A")
        trakt_link = f"https://trakt.tv/movies/{generate_slug(title)}"
        poster_url = f"https://image.tmdb.org/t/p/w200{details.get('poster_path', '')}"

        embed = discord.Embed(
            title=title,
            description=f"⭐ **{rating}**\n"
                        f"👀 **{watchers}** people currently watching\n\n"
                        f"🎭 **Genres**: {genres}\n"
                        f"🕒 **Runtime**: {runtime}\n"
                        f"🎥 **Release Date**: {release_date}\n\n"
                        f"📜 **Tagline**: {tagline}\n"
                        f"🔗 [More Info on Trakt]({trakt_link})",
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
        details = fetch_tmdb_show_details(show["id"])
        title = details.get("name", "Unknown Title")
        rating = f"{details.get('vote_average', 0):.1f}/10 ({details.get('vote_count', 0)} votes)"
        watchers = fetch_trakt_watching(generate_slug(title), "shows")
        tagline = details.get("tagline", "No tagline available.")
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
                        f"📜 **Tagline**: {tagline}\n"
                        f"🔗 [More Info on Trakt]({trakt_link})",
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
        watchers = fetch_trakt_watching(title.replace(" ", "-").lower(), "shows")
        genres = ", ".join(anime.get("genres", [])[:2])
        episodes = anime.get("episodes", "N/A")
        status = "Airing" if anime.get("status", "").lower() == "releasing" else "Completed"
        trakt_link = f"https://trakt.tv/search?query={quote(title)}"
        poster_url = anime["coverImage"]["large"]

        embed = discord.Embed(
            title=title,
            description=f"⭐ **{score}/100**\n"
                        f"👀 **{watchers}** people currently watching\n\n"
                        f"🎭 **Genres**: {genres}\n"
                        f"📺 **Episodes**: {episodes}\n"
                        f"📅 **Status**: {status}\n\n"
                        f"🔗 [More Info on Trakt]({trakt_link})",
            color=discord.Color.orange()
        )
        embed.set_thumbnail(url=poster_url)
        return embed
    except Exception as e:
        print(f"Error creating anime embed: {e}")
        return None

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
