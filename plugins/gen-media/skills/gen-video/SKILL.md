---
name: gen-video
description: Generate text-to-video clips through the user's own New API gateway. Use when the user asks to create, generate, render, or download a video, clip, animation, camera move, or moving scene. For stills use gen-image.
argument-hint: "[视频描述]"
---

# Gen Video

Text-to-video through the user's own New API gateway. Script: `scripts/gen_media.py` relative to this skill folder. Reply in the user's language.

## Onboard — first use only

1. Run `python "<skill-dir>/scripts/gen_media.py" show-config`.
   - Prints Base URL + masked key → onboard done.
   - Stderr contains `CONFIG_MISSING` → continue.
2. Ask the user for their New API Base URL in chat (not a secret).
3. Hand the user this command to run in their own terminal session (agent shells have no TTY for hidden input). The key prompt hides input; the key stays out of chat, command arguments, and logs:

   ```text
   python "<skill-dir>/scripts/gen_media.py" configure --base-url "<url>"
   ```

4. Re-run `show-config`. Done when it prints the masked key.

Env override: `GEN_MEDIA_BASE_URL` + `GEN_MEDIA_API_KEY` skip the config file.

## Pick the model — once, then switch on demand

1. Run `python "<skill-dir>/scripts/gen_media.py" list-models` and show the user the catalog.
2. Text-to-video default: `happyhorse-1.1-t2v`. The `i2v` / `r2v` variants need image input and are outside this skill's prompt-only pipeline — the script rejects them.
3. Persist: `python "<skill-dir>/scripts/gen_media.py" set-model --video <model>`. One-off: `--model <model>` on the generate command.

Done when: `show-config` prints the chosen video model.

## Craft the brief

Never fire a vague one-liner at the model. Resolve these slots first; fill what the request implies, ask only what it cannot:

1. **Subject + action** — what moves, and how (one subject per shot; multiple subjects melt).
2. **Environment** — where, when, weather/time of day.
3. **Camera** — one movement per shot: push-in / pull-back / pan / orbit / drone dive.
4. **Timeline beats** — split the duration: what happens 0–2s, 2–4s, final second. No beats = static frame.
5. **Format** — platform decides ratio: desktop ad `16:9`, mobile/short-video `9:16`; resolution `1080P` default (`720P` for cheap drafts); duration `5` seconds default (3–15).
6. **Light & mood** — named lighting beats adjectives; one mood, not three.

- Vague request ("随便来个视频") → propose exactly 3 distinct directions (scene + camera), one line each; the user picks. Then fill the remaining slots.
- Ask at most 2 questions total, and only when a wrong guess would burn credits. Otherwise infer, state the assumptions in one line, and proceed.
- Add no logos, subtitles, or people unless asked.
- Done when: final prompt + ratio + resolution + duration decided.

Camera vocabulary, lighting terms, timeline templates, failure fixes → `references/prompt-guide.md` (load when the request is vague or the user wants better results).

## Green-light

Video burns credits. Show the full brief — prompt, model, ratio, resolution, duration — and wait for the user's explicit yes. No yes, no submit.

## Generate

```bash
python "<skill-dir>/scripts/gen_media.py" video --prompt "<prompt>" --resolution "1080P" --ratio "16:9" --duration 5
```

The script submits, polls, downloads the MP4, and prints its path; wait for it inside the script's timeout. Report the final file path plus the final prompt. No success claim until the MP4 exists locally.

On failure: report the API error verbatim, then triage in this order — model permission → channel model list → quota → task polling service.

## Iterate

After delivery, offer one concrete next take (new angle / longer cut / different light).

## Rules

- Bundled script only; no ad-hoc curl.
- The full API key is never printed, echoed, or logged, and is never written into the project directory.
- Save to the current working directory unless the user names an output directory.

## Update

User asks to update gen-media → use the host's plugin / skill update mechanism (Claude Code: `/plugin update gen-media`; Codex / WorkBuddy: pull the repo and recopy the skill folders). Config at `~/.gen-media/config.json` lives outside the skill folders and survives updates.
