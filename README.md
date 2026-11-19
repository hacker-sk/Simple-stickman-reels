# Simple stickman reels

One GitHub Actions job (`make`): payload -> Gemini voice (Iapetus) -> Cloudflare Flux images -> black-background video -> Buffer.

Run it by pushing `jobs/package.json`, or Actions > Simple Stickman Reel > Run workflow and paste the package.

Package format and options: `pipeline/package.py`.

Secrets: `GEMINI_API_KEY`, `GEMINI_API_KEY_2`, `CF_ACCOUNT_ID`, `CF_API_TOKEN`, `CF_ACCOUNT_ID_2`, `CF_API_TOKEN_2`, `BUFFER_TOKEN`.
Variables: `BUFFER_YOUTUBE_CHANNEL_ID`, `BUFFER_INSTAGRAM_CHANNEL_ID`, optional `BUFFER_FACEBOOK_CHANNEL_ID`.
