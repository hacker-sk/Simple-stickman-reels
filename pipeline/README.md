# Hindi portrait Shorts pipeline (GitHub Actions)

Workflow: `.github/workflows/shorts.yml`, entry point: `pipeline/run_shorts.py`. n8n is not needed at runtime.

## Flow

Scheduled: cron -> topic (`topics.py`) -> Hindi script (`script.py`) -> image prompts (`image_prompts.py`) -> render
(`render_hindi.py`, same job) -> output check -> Buffer (`buffer.py`) -> topic history -> run summary.

Manual (GitHub Mobile): Actions > Hindi Shorts > Run workflow. Fill in an `idea` (script is written for you) or a
finished `script` (used word for word, only English words are respelled in Devanagari), or leave both empty for an
automatic topic. Optional: `script_mode` (auto/truth/story, automatic topics only) and `art_style`
(painterly default, sepia, night, golden). There is no preview or approval step: the video is rendered and scheduled on Buffer.

## Files

- `topic_banks.py`, `topics.py`: niches, topic prompts, duplicate prevention. History is `state/topic_history.json`.
- `script_prompts_truth.py`, `script_prompts_story.py`, `script.py`: prompts, validation, retries, narration.
- `styles.py`, `image_prompts.py`: art styles and image prompts.
- `gemini.py`: Gemini client with the original model fallback order and API key rotation.
- `buffer.py`: schedules on YouTube and Instagram (required) and Facebook (best effort).
- `run_shorts.py`: runs all steps, starts the renderer, validates `output/video.mp4` and `output/result.json`.

## Schedule

Cron runs at 10:00, 13:30, 17:00 and 20:30 IST (04:30, 08:00, 11:30, 15:00 UTC). Scheduled runs only start when the
repository variable `SHORTS_SCHEDULE_ENABLED` is `true`. Manual runs always work.

## Secrets and variables

- Secrets: `GEMINI_API_KEY` (+ `_2`..`_6`), `HF_TOKEN` (+ `_2`..`_6`), `ELEVENLABS_API_KEY`, `FISH_API_KEY`,
  `CF_ACCOUNT_ID` / `CF_API_TOKEN` (+ `_2`..`_6`), `COLAB_URL`, `COLAB_URL_SOURCE`, `COLAB_TOKEN`, `BUFFER_TOKEN`.
- Variables: `BUFFER_YOUTUBE_CHANNEL_ID`, `BUFFER_INSTAGRAM_CHANNEL_ID`, optional `BUFFER_FACEBOOK_CHANNEL_ID`,
  optional `IMAGE_PROVIDER_ORDER` (for example `cloudflare,hfspace,pollinations`; passed to the renderer as `HINDI_IMAGE_ORDER`).
  The Buffer channel ids may also be stored as secrets of the same name.

## State and concurrency

One run at a time (`concurrency: hindi-shorts`, queued, never cancelled). After Buffer accepts the video, the topic is
added to `state/topic_history.json` and committed back to `main` (pull --rebase and push, up to 5 tries).

## Failure behaviour

A failed step stops the run and the reason is shown in the run summary and log. Nothing is published unless the
video passed validation (portrait, audio, 5 to 180 s, public URL). If Buffer accepts only some channels, the run is marked
failed but the topic is still recorded so it is not reused. A copy of every rendered video is kept as a GitHub release
(newest 20).

## Not part of this pipeline

Landscape rendering, YouTube API publishing, Vertex AI and Telegram.
