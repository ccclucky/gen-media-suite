---
name: gen-image
description: Generate images through the user's own New API gateway. Use when the user asks to create, draw, render, generate, or download an image, poster, illustration, cover, or product visual. For moving footage use gen-video.
argument-hint: "[图片描述]"
---

# Gen Image

Images through the user's own New API gateway. Script: `scripts/gen_media.py` relative to this skill folder. Reply in the user's language.

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

1. Run `python "<skill-dir>/scripts/gen_media.py" list-models` and show the user the catalog (model + one-line trait).
2. Recommend a default by intent: commercial/product → `wan2.7-image-pro`; heavy in-image text → `qwen-image-2.0-pro`; credit-saving drafts → `wan2.7-image`.
3. Persist the choice: `python "<skill-dir>/scripts/gen_media.py" set-model --image <model>`.
4. Later switches: same `set-model` command. One-off experiments: `--model <model>` on the generate command (does not persist).

Done when: `show-config` prints the chosen image model.

## Craft the brief

Never fire a vague one-liner at the model. Resolve these five slots first; fill what the request implies, ask only what it cannot:

1. **Subject** — what, in what state (product + material/condition; person + pose; scene + focal element).
2. **Purpose & canvas** — ad / poster / icon / wallpaper decides the aspect ratio (see sizes below).
3. **Style** — photography, illustration, 3D render, flat vector, ink…
4. **Light & palette** — studio softbox / golden hour / neon; named colors beat adjectives.
5. **In-image text** — capture VERBATIM in quotes, or confirm "no text".

- Vague request ("来张好看的") → propose exactly 3 distinct directions (subject + style + palette), one line each; the user picks. Then fill the remaining slots.
- Ask at most 2 questions total, and only when a wrong guess would waste the shoot. Otherwise infer, state the assumptions in one line, and proceed.
- Done when: all five slots resolved into a final prompt + size.

Sizes — default `2048x2048`; 16:9 `2720x1536`; 9:16 `1536x2720`; 4:3 `2304x1728`; 3:4 `1728x2304`.

Recipes, vocabulary, and per-purpose templates → `references/prompt-guide.md` (load when the request is vague or the user wants better results).

## Generate

```bash
python "<skill-dir>/scripts/gen_media.py" image --prompt "<prompt>" --size "<WIDTHxHEIGHT>"
```

Report the absolute path of every file plus the final prompt used, so "再来一版……" iterations stay precise. No success claim until the file exists locally.

## Iterate

After delivery, offer one concrete next take (palette / angle / variant). Hero shot landed → suggest gen-video to animate it.

## Rules

- Bundled script only; no ad-hoc curl.
- The full API key is never printed, echoed, or logged, and is never written into the project directory.
- Save to the current working directory unless the user names an output directory.

## Update

User asks to update gen-media → use the host's plugin / skill update mechanism (Claude Code: `/plugin update gen-media`; Codex / WorkBuddy: pull the repo and recopy the skill folders). Config at `~/.gen-media/config.json` lives outside the skill folders and survives updates.
