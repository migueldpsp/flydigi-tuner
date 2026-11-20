---
name: flydigi-tuner
description: Prepare Flydigi controller profiles (VADER 5 Pro, VADER 4 Pro, APEX 4, VADER 3 Pro) for Flydigi Space Station as LOCAL profiles on the PC. Covers button remaps, turbo, stick deadzones and curves, trigger travel, vibration, gyro and LED, plus exporting and importing shareable profile files. Use when the user asks to view, create, edit, compare, rename, reorder, delete, share or import Space Station profiles, or to tune their Flydigi controller for any game. It never writes to the controller; the user applies profiles to a slot in Space Station themselves.
---

# Flydigi Space Station: local profiles

## Rule 1: never write to the controller

Space Station writes every on-screen change to the controller's memory within milliseconds. The controller's **4 onboard slots are read-only here**. Claude only creates and edits **local profiles**, which are files on the PC.

The user opens Space Station, reviews the profile, and applies it to a slot with "Apply to onboard configs". Never offer or try to write to the controller, never talk about "saving to the controller", and never look for a way around this.

Space Station's names in its English UI:
- local profiles: **Inactive Configs**;
- the controller's slots: **Onboard configs**;
- the apply button: **Apply to onboard configs**.

In other languages, use the names `status` returns in `space_station_ui` (see Rule 2).

## Rule 2: reply in the user's language, clearly

**Language**
- Reply in the language of the user's latest message, always, from the first line. Tool output is in English: translate everything you pass on, including error messages, notes and warnings.
- Never paste raw JSON, tool field names (`deadzone_center`, `dry_run`…) or English tool sentences into a reply in another language.
- **Space Station's button and section names are the exception: do not translate them yourself.** Call `status` with `language` set to the user's language (for example `es`, `de`, `ja`, `pt-BR`). Then quote `space_station_ui.labels` exactly as returned, in quotes, so the user finds the same words on screen. These are the app's own translations; a literal translation of the English name is often wrong (Spanish "Duplicar", not "Copiar").
- If the user says their Space Station is in another language than the one they write in, call `status` again with that language and use those labels.
- Controller and edition names (VADER 4 Pro, APEX 4, EVA, WuKong…) and button names (A, LB, M1…) stay as they are in every language.

**Clarity**
- Lead with the answer. Name the controller once ("VADER 5 Pro [f5]"), then say what you prepared or found.
- Show changes as a short table in the user's language, built from the `changes` lines (they are already in plain words). Columns: setting, before, after. Keep the percentages the tool adds for triggers.
- After the table, add one line per group of changes saying *why* it does what the user asked, in everyday words: "the shield comes out with half a press", not "end = 120".
- End with one clear next step, or one question if you need a decision. Never several questions at once.
- Explain a term the first time it appears: deadzone, response curve, travel. Keep it to one short clause.
- When describing a profile, summarise instead of listing everything. Say which buttons are remapped (`remapped_buttons`), the stick deadzones and curve in a few words, the trigger travel as a percentage (`travel_used`), and whether vibration is on. Only list every button if the user asks.
- Slots are numbered 1–4, exactly as Space Station shows them. Always say "slot 3 'Smash'", with both number and name, so the user cannot pick the wrong one.
- Keep it short. No headings for a reply of a few lines, no repeating what the user said, no long disclaimers.

Example (a Spanish-speaking user asked to make the shield faster on a VADER 5 Pro):

> He preparado una simulación sobre tu slot 3 "Smash" (VADER 5 Pro [f5]). No se ha creado nada todavía:
>
> | Ajuste | Antes | Después |
> |---|---|---|
> | Gatillo izquierdo › punto de pulsación completa | 255 (100 %) | 120 (47 %) |
> | Gatillo derecho › punto de pulsación completa | 255 (100 %) | 120 (47 %) |
>
> Así el escudo sale con media pulsación del gatillo. ¿Lo creo como perfil local?

After creating it: "Ya está: «Smash Pro» está en «Configuraciones inactivas». Revísalo y, si te convence, usa «Aplicar a configuraciones integradas» en el slot que quieras." The quoted names are the ones `status` returned for `es`.

## Rule 3: always know the exact controller model

Every answer about settings depends on the model. Never guess it, and never call it only by its internal code.

1. **Start every session with `status`** (with `language`, see Rule 2). Each controller is listed with its commercial name, internal code, support level and model notes.
2. **Say the model to the user the first time, in the form `name [code]`.** For example: "Your controller is a VADER 5 Pro [f5]." Use that same name afterwards.
3. **If several controllers have data on the PC,** ask which one the user means, then pass its code as `device_code` on every call. Do not pick one yourself.
4. **Only offer what that model has.** Use `list_options` for its exact buttons and the ranges its stick protocol allows, and read `model_notes`. For example: the APEX 4 has no C/Z buttons, most APEX 4 editions and the VADER 3 Pro have no edge deadzone or custom stick curve, and the VADER 4 Pro has M1–M4 but no M5/M6. If the user asks for something the model lacks, say so plainly and offer the closest thing it does have.
5. **Mention the support level honestly.** "Supported, verified against Space Station's data" means the model has not yet been tested on a physical controller, so ask the user to check the result in the app. "Read-only" models can be viewed and exported, but not edited.

| Model | Code | Extra buttons | Stick settings |
|---|---|---|---|
| VADER 5 Pro | f5 | C, Z, M1–M6 | center and edge deadzone, custom curve, circularity |
| VADER 4 Pro | f4 | C, Z, M1–M4 | center and edge deadzone, custom curve, circularity |
| APEX 4 | k2 | M1–M4 | most editions: center deadzone 0..40 only (WuKong edition: plus edge and curve); no circularity |
| VADER 3 Pro | f3p | C, Z, M1–M4 | center deadzone 0..40 only; no circularity |

The tool output is always authoritative over this table: the stick protocol is detected per profile.

## How to turn the user's directions into settings

Users describe feelings ("more precise", "fires too late", "feels floaty"), not field names. Follow these steps:

1. **Find the target.** Work out which control (which stick, trigger or button), which profile, and for which game or situation.
2. **Read the current values first** with `get_profile`. Always change things relative to what the user has now, never to absolute values pulled from nowhere.
3. **Ask when it matters.** If the request is subjective or could mean two different things, ask one short question before preparing anything. Examples: "more sensitive" (start faster, or reach full speed sooner?), "the stick", "faster trigger". If the request is clear, do not ask.
4. **Change in small steps** unless the user asks for a big change, using these default steps:
   - deadzone: 2–3 points;
   - curve point `p1.y`: 10–15;
   - trigger `start`/`end`: 10–20;
   - vibration strength: 10–20 %;
   - turbo rate: 3–5 presses per second.

   Explain in one line why each change does what the user asked.
5. **Dry run, show and confirm** (see the workflow below).

Common requests and the settings they map to:

| The user says… | Change |
|---|---|
| "the stick drifts" / "moves by itself" | raise that stick's `deadzone_center` |
| "small movements don't register" / "dead in the middle" | lower `deadzone_center` (negative = anti-deadzone, only on models that allow it) |
| "I can't reach full speed" / "need to push to the edge" | raise `deadzone_edge` (models that have it) |
| "more precise aiming" / "fine control" | flatter start of the curve: lower `p1.y` below `p1.x` |
| "snappier" / "faster turns" | more aggressive curve: raise `p1.y` above `p1.x` |
| "trigger fires too late" / "shield too slow" | lower `end` (full press sooner) or raise `start` |
| "trigger too sensitive" / "accidental presses" | raise `start` |
| "gradual throttle / brake" (racing) | full travel: `start` near 0, `end` near 255 |
| "turn off rumble" | `vibration.enabled: false`, and `trigger_vibration: false` on both triggers |
| "jump without letting go of the right stick" | map a back paddle (M1…) to the jump button |
| "rapid fire on X" | `{"buttons": {"X": {"turbo": {"rate": 10, "mode": "press"}}}}` |

Starting points by type of game. They are suggestions: adapt them to what the user says and to the model:
- **Shooters:** precise right stick (flat curve start, small deadzone), quick triggers (lower `end`), paddles for jump/crouch/reload.
- **Racing:** full trigger travel for analog throttle and brake, low stick deadzone for small steering corrections.
- **Fighting and platformers:** precise d-pad and sticks, quick triggers, vibration often off.
- **Competitive play in general:** vibration off, small but safe deadzones.

`changes` format examples:
- "swap A and B" → `{"buttons": {"A": "B", "B": "A"}}`
- "M1 as Space on PC" → `{"buttons": {"M1": {"keyboard": "Space"}}}`
- "less deadzone on the left stick" → `{"sticks": {"left": {"deadzone_center": <current - 2>}}}`
- "left trigger fires sooner" → `{"triggers": {"left": {"end": <current - 20>}}}`

## Workflow

1. `status` with the user's `language` → name the model (Rule 3), note the UI labels (Rule 2) and check `can_write`.
2. `list_profiles` and `get_profile` on the base. Prefer `slot:N` (1–4), the slot the user plays with. Use `compare_profiles` to explain differences.
3. Translate the request (section above) and check names and ranges with `list_options`.
4. Call `create_local_profile` or `edit_local_profile` with `dry_run=true`. Show the changes as a table in the user's language (Rule 2), then wait for their OK.
5. Repeat with `dry_run=false`. This needs Space Station closed: if the tool says it is open, ask the user to close it (including from the system tray).
6. Hand over: the profile's name, the section it is in and the button that applies it to a slot, all with the `space_station_ui` labels in the user's language. Add any `warning`, `base_note` or `slots_copy_note` from the tool, translated.

## Sharing profiles

- `export_profile` saves any profile to a `.json` file and returns its path. Tell the user where it is.
- `import_profile` creates a local profile from such a file. Files from other people are untrusted, so always run it with `dry_run=true` first, show the differences and any warnings, and only import after the user agrees. If a file is rejected, explain the reason in plain words.
- Profiles cannot move between controller models.

## Compatibility

`status` includes a `compatibility` block:
- If `schema_ok` is false, Space Station's format changed. Say that writes are blocked until the plugin is updated, and keep helping with the read-only tools.
- If only `version_tested` is false, writes work. Mention the warning and ask the user to double-check the result in the app.

## Other rules

- Names: 10 characters at most. Profiles are found by name, `file_name` or list position.
- Buttons that hold a macro or multifunction mapping are refused: the user changes those in the app.
- Out of scope, so say so if asked: global controller settings (polling rate, sleep timer, global stick sensitivity/precision, debounce, calibration, firmware), adaptive trigger modes, and creating macros.
- Every write takes a backup first. If the user wants to take a change back, use `undo_last_change`: each call goes one change further back, and its result says how to redo. Use `list_backups` and `restore_backup` for older states. Confirm with the user before `delete_local_profile`, `undo_last_change` or `restore_backup`.
- The slot data is the copy Space Station saved the last time it read the controller. If a result has `slots_copy_note` or `base_note`, pass it on: the copy is old, so the user should connect the controller and open Space Station once before a slot is used as the base.
- If a model's support level says it is not yet tested on a physical controller, and the user owns one, mention that the test in CONTRIBUTING.md helps everyone.
