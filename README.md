Run the bot:
```
docker run -d \
  --name trendbot \
  -e DISCORD_BOT_TOKEN=your_discord_token_here \
  -e TMDB_API_KEY=your_tmdb_api_key_here \
  -e TRAKT_API_KEY=your_trakt_api_key_here \
  -e POST_TIME=12:00 \
  sushibox/trendbot

```
Steps to Invite the Bot

    Go to the Discord Developer Portal:
        Navigate to the Discord Developer Portal.

    Open Your Application:
        Select your bot application.

    Set Up OAuth2 URL for Bot Invitation:
        In the application dashboard, go to the OAuth2 tab.
        Under Scopes, select the checkbox for bot.
        Under Bot Permissions, choose the permissions your bot requires:
            For this bot:
                Read Messages/View Channels
                Send Messages
                Embed Links
                Manage Channels (if auto-creating categories and channels).
        Copy the generated URL from the bottom of the OAuth2 section.

    Invite the Bot:
        Paste the URL into your browser and select the server where you want to invite the bot.

