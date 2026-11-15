# Hindi Shorts, GitHub only

No n8n needed. Everything runs in GitHub Actions.

## Make a video from the GitHub mobile app
1. Open the repo, tap **Actions**, then **Hindi Shorts**.
2. Tap **Run workflow**, paste the finished script JSON into `script`, tap **Run workflow**.
3. When the video is made it is published straight away (Instagram, YouTube, Facebook via Buffer) and a note comes on Telegram.

## Script JSON format
```json
{
  "title": "Hindi hook title under 70 characters",
  "description": "Two Hindi sentences.",
  "hashtags": ["#a", "#b", "#c", "#d", "#e", "#f", "#g", "#h"],
  "tags": ["t1", "t2", "t3", "t4", "t5"],
  "mood": "emotional",
  "artStyle": "Emotional Painterly Storybook",
  "scenes": [
    {"narration": "Hindi in Devanagari only, no English letters", "image_prompt": "English image prompt, at least 40 characters"}
  ]
}
```

`mood` is one of: inspiring, emotional, mysterious, dramatic, upbeat, calm.

## Secrets (Settings > Secrets and variables > Actions)
Already used by the renderer: GEMINI_API_KEY (and _2 to _6), HF_TOKEN (and _2 to _6), ELEVENLABS_API_KEY, FISH_API_KEY, CF_ACCOUNT_ID / CF_API_TOKEN (and _2 to _6), COLAB_*.

New for this pipeline:
- BUFFER_TOKEN
- BUFFER_INSTAGRAM_CHANNEL_ID
- BUFFER_YOUTUBE_CHANNEL_ID
- BUFFER_FACEBOOK_CHANNEL_ID (optional, found automatically when there is one Facebook channel)
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID

