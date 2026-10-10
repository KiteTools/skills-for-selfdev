#!/usr/bin/env node
/**
 * Generate one Russian line with ElevenLabs and overlay it on an mp3
 * at a user-supplied timestamp. The original track is ducked under the line.
 *
 * Requires ELEVENLABS_API_KEY unless --voice-file is set.
 * Requires ffmpeg and ffprobe on PATH.
 */

import { spawn } from "node:child_process";
import { mkdtemp, stat, lstat, copyFile, chmod, writeFile, rm } from "node:fs/promises";
import { constants } from "node:fs";
import os from "node:os";
import path from "node:path";

const VOICES = {
  male: "0BcDz9UPwL3MpsnTeUlO",
  female: "EDpEYNf6XIeKYRzYcx4I",
};

const MODEL_ID = "eleven_multilingual_v2";
const DUCK_LEVEL = 0.18;
const FADE_SEC = 0.3;

function usage() {
  return `Usage:
  node embed-voice.mjs --input <file.mp3> --at <mm:ss> --text <phrase> --voice <male|female|voice_id> [--output <file.mp3>]
  node embed-voice.mjs --input <file.mp3> --at <mm:ss> --voice-file <line.mp3> [--output <file.mp3>]

--voice-file skips ElevenLabs and mixes an existing clip.`;
}

function parseArgs(argv) {
  const args = {
    input: "",
    at: "",
    text: "",
    voice: "",
    voiceFile: "",
    output: "",
  };

  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (!key.startsWith("--")) {
      throw new Error(`Unexpected argument: ${key}`);
    }
    if (value === undefined || value.startsWith("--")) {
      throw new Error(`Missing value for ${key}`);
    }
    i += 1;
    if (key === "--input") args.input = value;
    else if (key === "--at") args.at = value;
    else if (key === "--text") args.text = value;
    else if (key === "--voice") args.voice = value;
    else if (key === "--voice-file") args.voiceFile = value;
    else if (key === "--output") args.output = value;
    else throw new Error(`Unknown argument: ${key}`);
  }

  if (!args.input) throw new Error("--input is required");
  if (!args.at) throw new Error("--at is required");
  if (args.voiceFile && (args.text || args.voice)) throw new Error("Use either --voice-file or --text with --voice.");
  if (!args.voiceFile && !args.text.trim()) throw new Error("--text is required");
  if (!args.voiceFile && !args.voice) throw new Error("--voice is required");
  return args;
}

function parseTimestamp(value) {
  const trimmed = value.trim();
  if (/^\d+(\.\d+)?$/.test(trimmed)) {
    const seconds = Number(trimmed);
    if (!Number.isFinite(seconds)) throw new Error("Timestamp must be finite.");
    return seconds;
  }

  const parts = trimmed.split(":");
  if (parts.length < 2 || parts.length > 3) {
    throw new Error(`Invalid timestamp "${value}". Use mm:ss, h:mm:ss, or seconds.`);
  }

  const numbers = parts.map((part) => {
    if (!/^\d+(\.\d+)?$/.test(part)) {
      throw new Error(`Invalid timestamp "${value}".`);
    }
    return Number(part);
  });

  if (numbers.some((n) => !Number.isFinite(n) || n < 0)) {
    throw new Error(`Invalid timestamp "${value}".`);
  }

  if (parts.length === 2) {
    const [minutes, seconds] = numbers;
    if (seconds >= 60) throw new Error(`Seconds must be < 60 in "${value}".`);
    return minutes * 60 + seconds;
  }

  const [hours, minutes, seconds] = numbers;
  if (minutes >= 60 || seconds >= 60) {
    throw new Error(`Minutes and seconds must be < 60 in "${value}".`);
  }
  return hours * 3600 + minutes * 60 + seconds;
}

function resolveVoiceId(voice) {
  const key = voice.trim().toLowerCase();
  if (key === "male" || key === "мужской") return VOICES.male;
  if (key === "female" || key === "женский") return VOICES.female;
  if (/^[A-Za-z0-9]{10,}$/.test(voice.trim())) return voice.trim();
  throw new Error(`Unknown voice "${voice}". Use male, female, or an ElevenLabs voice ID.`);
}

function stampName(seconds) {
  const total = Math.floor(seconds);
  const mm = String(Math.floor(total / 60)).padStart(2, "0");
  const ss = String(total % 60).padStart(2, "0");
  return `${mm}-${ss}`;
}

function defaultOutput(inputPath, startSec) {
  const dir = path.dirname(inputPath);
  const base = path.basename(inputPath, path.extname(inputPath));
  return path.join(dir, `${base}_voice_${stampName(startSec)}.mp3`);
}

function run(command, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk;
    });
    child.on("error", (error) => {
      if (error.code === "ENOENT") {
        reject(new Error(`${command} is not installed or not on PATH.`));
        return;
      }
      reject(error);
    });
    child.on("close", (code) => {
      if (code === 0) resolve({ stdout, stderr });
      else reject(new Error(`${command} exited ${code}: ${stderr.trim() || stdout.trim()}`));
    });
  });
}

async function probeDuration(filePath) {
  const { stdout } = await run("ffprobe", [
    "-v",
    "error",
    "-show_entries",
    "format=duration",
    "-of",
    "default=noprint_wrappers=1:nokey=1",
    filePath,
  ]);
  const duration = Number(stdout.trim());
  if (!Number.isFinite(duration) || duration <= 0) {
    throw new Error(`Could not read duration of ${filePath}.`);
  }
  return duration;
}

function duckExpression(startSec, voiceSec) {
  const fade = FADE_SEC;
  const duckStart = Math.max(0, startSec - fade);
  const voiceEnd = startSec + voiceSec;
  const duckEnd = voiceEnd + fade;
  const level = DUCK_LEVEL;
  const rise = (1 - level).toFixed(4);
  const fadeText = fade.toFixed(3);
  const entryFadeText = Math.max(startSec - duckStart, 0.001).toFixed(3);
  const parts = [
    `if(lt(t,${duckStart.toFixed(3)}),1`,
    `if(lt(t,${startSec.toFixed(3)}),1-${rise}*((t-${duckStart.toFixed(3)})/${entryFadeText})`,
    `if(lt(t,${voiceEnd.toFixed(3)}),${level}`,
    `if(lt(t,${duckEnd.toFixed(3)}),${level}+${rise}*((t-${voiceEnd.toFixed(3)})/${fadeText}),1))))`,
  ];
  return parts.join(",");
}

async function synthesize(text, voiceId, destPath) {
  const apiKey = process.env.ELEVENLABS_API_KEY;
  if (!apiKey) {
    throw new Error("ELEVENLABS_API_KEY is not set.");
  }

  const response = await fetch(
    `https://api.elevenlabs.io/v1/text-to-speech/${voiceId}`,
    {
      method: "POST",
      signal: AbortSignal.timeout(90000),
      redirect: "error",
      headers: {
        "xi-api-key": apiKey,
        "Content-Type": "application/json",
        Accept: "audio/mpeg",
      },
      body: JSON.stringify({
        text,
        model_id: MODEL_ID,
        voice_settings: {
          stability: 0.55,
          similarity_boost: 0.75,
          style: 0,
          use_speaker_boost: true,
        },
      }),
    },
  );

  if (!response.ok) {
    throw new Error(`ElevenLabs returned HTTP ${response.status}. Check your account, voice access and quota.`);
  }

  const bytes = Buffer.from(await response.arrayBuffer());
  if (bytes.length < 100) {
    throw new Error("ElevenLabs returned an empty audio file.");
  }
  await writeFile(destPath, bytes, { flag: "wx", mode: 0o600 });
}

async function mix({ input, voiceFile, output, startSec, voiceSec }) {
  const delayMs = Math.round(startSec * 1000);
  const expression = duckExpression(startSec, voiceSec);
  const filter = [
    `[1:a]adelay=${delayMs}:all=1[voice]`,
    `[0:a]volume='${expression}':eval=frame[bg]`,
    "[bg][voice]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[out]",
  ].join(";");

  await run("ffmpeg", [
    "-n",
    "-i",
    input,
    "-i",
    voiceFile,
    "-filter_complex",
    filter,
    "-map",
    "[out]",
    "-c:a",
    "libmp3lame",
    "-q:a",
    "2",
    output,
  ]);
}

async function main() {
  if (process.argv.length === 3 && process.argv[2] === "--help") {
    process.stdout.write(`${usage()}\n`);
    return;
  }
  const args = parseArgs(process.argv.slice(2));
  const startSec = parseTimestamp(args.at);
  const input = path.resolve(args.input);
  if (!(await stat(input)).isFile()) throw new Error("Input must be a local file.");
  await run("ffmpeg", ["-version"]);

  const sourceSec = await probeDuration(input);
  if (startSec >= sourceSec) {
    throw new Error(
      `Timestamp ${args.at} (${startSec.toFixed(2)}s) is at or past the end of the file (${sourceSec.toFixed(2)}s).`,
    );
  }

  const output = path.resolve(args.output || defaultOutput(input, startSec));
  if (output === input) {
    throw new Error("Refusing to overwrite the source mp3. Choose a different --output.");
  }

  if (path.extname(output).toLowerCase() !== ".mp3") throw new Error("Output must end in .mp3.");
  try {
    await lstat(output);
    throw new Error("Output already exists. Choose a new --output.");
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
  if (!(await stat(path.dirname(output))).isDirectory()) throw new Error("Output parent must exist.");
  const tmpDir = await mkdtemp(path.join(os.tmpdir(), "embed-breath-voice-"));
  const tmpVoice = path.join(tmpDir, "line.mp3");
  const tmpOutput = path.join(tmpDir, "result.mp3");
  let voiceFile = args.voiceFile ? path.resolve(args.voiceFile) : tmpVoice;
  let voiceId = null;

  try {
    if (!args.voiceFile) {
      voiceId = resolveVoiceId(args.voice);
      await synthesize(args.text.trim(), voiceId, tmpVoice);
      voiceFile = tmpVoice;
    } else {
      if (!(await stat(voiceFile)).isFile()) throw new Error("Voice clip must be a local file.");
    }

    const voiceSec = await probeDuration(voiceFile);
    await mix({ input, voiceFile, output: tmpOutput, startSec, voiceSec });
    const outputSec = await probeDuration(tmpOutput);
    await chmod(tmpOutput, 0o600);
    // Exclusive publication also refuses symlinks and files created during mixing.
    await copyFile(tmpOutput, output, constants.COPYFILE_EXCL);

    const result = {
      output,
      start_sec: Number(startSec.toFixed(3)),
      voice_sec: Number(voiceSec.toFixed(3)),
      source_sec: Number(sourceSec.toFixed(3)),
      output_sec: Number(outputSec.toFixed(3)),
      voice_id: voiceId,
      model_id: args.voiceFile ? null : MODEL_ID,
      ducked_to: DUCK_LEVEL,
    };
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  } finally {
    await rm(tmpDir, { recursive: true, force: true });
  }
}

main().catch((error) => {
  process.stderr.write(`${error.message}\n${usage()}\n`);
  process.exit(1);
});
