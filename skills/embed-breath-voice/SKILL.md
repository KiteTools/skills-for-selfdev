---
name: embed-breath-voice
description: Insert one spoken phrase or question at a chosen timestamp in a supplied breathing MP3, using an existing voice clip or ElevenLabs synthesis and ffmpeg background ducking. Use for timed voice overlays; Muse hardware, EEG and a specific breathing app are not required.
---

# Add a voice phrase to a breathing MP3

Create a new MP3 from a user-selected local track. Preserve the source, exact requested phrase and chosen insertion time. Do not infer a breath-hold phase or change breathing instructions, the player or EEG configuration.

## Inputs and prerequisites

Ask only for missing values: source MP3, timestamp (`mm:ss`, `h:mm:ss` or seconds), and either an existing spoken clip or the exact Russian text plus selected voice. One overlay per run; for multiple lines, establish their individual timestamps before separate runs.

Requires Node.js 22+, `ffmpeg` with `libmp3lame`, and `ffprobe` on PATH. There are no npm dependencies. `ELEVENLABS_API_KEY` is required only for synthesis. Read it from the environment, never from a prompt or a committed file. Installation does not create an account or configure the key.

For synthesis, tell the person that their exact text goes to ElevenLabs and uses their account quota. Use the supplied key only for the requested synthesis. Keep `eleven_multilingual_v2`; do not silently substitute another model, voice or service after an error. The default voice aliases are `male` / `мужской` (`0BcDz9UPwL3MpsnTeUlO`) and `female` / `женский` (`EDpEYNf6XIeKYRzYcx4I`). Their availability depends on the account; a custom accessible voice ID is accepted. Never clone a voice as part of this skill.

## Run

From this skill directory, using private paths chosen by the person:

```sh
node scripts/embed-voice.mjs \
  --input /absolute/private/breathing.mp3 --at 12:05 \
  --text "Я спокоен." --voice male \
  --output /absolute/private/breathing-with-voice.mp3
```

To mix an existing clip entirely locally, omit `--text` and `--voice`:

```sh
node scripts/embed-voice.mjs \
  --input /absolute/private/breathing.mp3 --at 12:05 \
  --voice-file /absolute/private/question.mp3 \
  --output /absolute/private/breathing-with-voice.mp3
```

The output parent must exist. Without `--output`, the name is `{source}_voice_{mm-ss}.mp3` beside the source. The script refuses existing outputs, including symlinks; choose another filename to retry. `--help` prints usage. Check the exit code before reporting success.

## What the script does

- Refuses a timestamp at or beyond the end of the source.
- Preserves the source timeline and inserts the clip at the requested offset.
- Lowers the background to 18% during the phrase, with a 0.3-second fade on each side (the entry fade is shortened near the start).
- Encodes a new MP3. If the phrase extends beyond the source, the output extends to finish it.
- Uses a private temporary directory, removes temporary speech and mix files, and never overwrites an existing destination.

Return the output path, insertion time, voice mode and clip duration from the printed JSON. Listen to the insertion boundary if playback is available; otherwise state that playback was not checked. The numerical mix does not guarantee intelligibility for every source or recording level. Keep supplied audio and generated speech outside public Git. Muse is optional: this skill edits audio and does not measure brain activity or validate a breathing practice.
