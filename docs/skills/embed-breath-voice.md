# Add a voice phrase to a breathing MP3

**English** · [Русский](embed-breath-voice.ru.md)

Put your question or reminder at the moment you choose. Supply a local MP3, a timestamp and either exact Russian text for ElevenLabs or an existing spoken clip. The skill writes a **new MP3**, gently lowering the background during the phrase. **Muse hardware is not required.**

## What you get

One voice overlay per run, with the source timeline preserved. Background volume drops to 18%, with 0.3-second transitions. If the phrase continues past the source end, the output extends to finish it. The source and existing output files are never overwritten, including symlink destinations. For several inserts, use each result as the next input with a new output name.

## Requirements and installation

You need Node.js 22+, `ffmpeg` with `libmp3lame`, and `ffprobe` on PATH. No npm packages are required. Set your own `ELEVENLABS_API_KEY` in the environment for synthesis only. The `--voice-file` mode needs no account or key.

Check `node --version`, `ffmpeg -version` and `ffprobe -version`. From the repository root:

```sh
python3 scripts/install.py embed-breath-voice --dest /absolute/private/project/.claude/skills
```

For Cursor, choose your project's `.cursor/skills` directory. You can also copy the entire [skill folder](../../skills/embed-breath-voice) manually; Python is needed only for this installer. Installation does not install dependencies or connect accounts.

## Use an existing voice clip locally

From the repository root:

```sh
node skills/embed-breath-voice/scripts/embed-voice.mjs \
  --input /absolute/private/breathing.mp3 --at 12:05 \
  --voice-file /absolute/private/question.mp3 \
  --output /absolute/private/breathing-with-voice.mp3
```

Replace paths and time with your own. The output parent must exist and the filename must be new. Without `--output`, the result is written beside the input as `{source}_voice_{mm-ss}.mp3`. Timestamps accept seconds, `mm:ss`, or `h:mm:ss`; at or beyond the source end is rejected.

## Generate a spoken phrase

Set the key privately in your shell environment, without putting it in Git or chat, then run:

```sh
node skills/embed-breath-voice/scripts/embed-voice.mjs \
  --input /absolute/private/breathing.mp3 --at 12:05 \
  --text "Что сейчас для меня важно?" --voice male \
  --output /absolute/private/breathing-with-voice.mp3
```

Voice aliases are `male`, `female`, `мужской`, `женский`, or an accessible ElevenLabs voice ID. The supplied aliases retain the original skill's IDs; availability depends on your account. The model is `eleven_multilingual_v2`; see the [ElevenLabs API reference](https://elevenlabs.io/docs/api-reference/text-to-speech/convert).

Synthesis sends your exact text to ElevenLabs and uses your account quota. The background MP3 stays local. Using an existing clip makes no ElevenLabs request. Keep personal audio, keys and results out of public Git.

## Ask your agent

> Use embed-breath-voice to insert the exact phrase “Что сейчас для меня важно?” at 12:05 in my breathing MP3, with the male voice. Preserve the source and create a separate file. Ask only for missing paths or synthesis access.

The script prints JSON with the output path, insertion time, source/clip/result durations and selected voice. Listen around the insertion boundary to check intelligibility; fixed mixing levels cannot guarantee it for every recording.

## Verification and limits

Synthetic audio tests check overlay timing, background ducking and recovery, preservation of inputs, overwrite refusal and errors. The TTS contract is tested with a local mocked API response; a live request and account-specific voice access are not confirmed by those tests. Tests run locally on macOS and on Linux in CI; Windows is not separately verified. Audio files are not included in the package.

This edits audio only: it does not infer breathing phases, interact with EEG or evaluate a practice's benefits.

[Skill instructions](../../skills/embed-breath-voice/SKILL.md) · [Practice example](https://app.imt.dev/artifacts/selfdev/#muse-mountain-practice) · [Catalog](../catalog.md)
