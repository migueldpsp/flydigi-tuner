# Flydigi Tuner

[![tests](https://github.com/migueldpsp/flydigi-tuner/actions/workflows/tests.yml/badge.svg)](https://github.com/migueldpsp/flydigi-tuner/actions/workflows/tests.yml)
![version](https://img.shields.io/badge/version-0.7.0-blue)
![platform](https://img.shields.io/badge/platform-Windows-lightgrey)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Tune your Flydigi controller by talking to Claude.** A [Claude Code](https://claude.com/claude-code) plugin (MCP server and skill) for **Flydigi Space Station**: describe what you want in your own words and in your own language, and Claude prepares the profile for you.

> **You:** the shield in Smash comes out too late, and I want to jump with the back paddle
>
> **Claude:** Here is a simulation based on your slot 3 "Smash" (VADER 5 Pro [f5]). Nothing has been created yet:
>
> | Setting | Before | After |
> |---|---|---|
> | Left trigger › full-press point | 255 (100%) | 120 (47%) |
> | Right trigger › full-press point | 255 (100%) | 120 (47%) |
> | Button M1 | M1 | X (jump) |
>
> The shield now comes out with half a trigger press, and you can jump without letting go of the right stick. Shall I create it as a local profile?

## How it works in four steps

1. **You describe the problem** in plain words: "the right stick drifts", "aiming feels twitchy", "the brake is too short".
2. **Claude reads your current profile** from Space Station and works out which settings to change, in small steps.
3. **You see a before/after table** like the one above. Nothing exists yet, so you can say no or ask for something different.
4. **You approve, and Claude creates a local profile.** You open Space Station, check it under **Inactive Configs** and put it on a slot yourself. If you change your mind, ask Claude to undo.

No menus to dig through, no numbers to guess, and nothing reaches the controller until you apply it.

## Your controller is never touched

Space Station writes every on-screen change straight to the controller's memory. Flydigi Tuner never does: it only creates and edits **local profiles**, which are files on your PC that Space Station lists under **Inactive Configs**.

You open Space Station, review the profile, and put it on a slot yourself with **Apply to onboard configs** (the names appear in your app's language). Every command that could write to the controller, its firmware or its calibration is blocked in code, and every change is simulated first and backed up before it happens.

## What you can ask for

- **Buttons:** remap any button, map back paddles, map keyboard keys, turbo (rapid fire).
- **Sticks:** center and edge deadzones, response curve, circularity.
- **Triggers:** start and full-press point, trigger vibration.
- **Vibration, gyro and LED brightness.**
- **Profiles:** create from a slot, a local profile or a factory profile; edit, duplicate, rename, reorder, delete; undo the last change.
- **Sharing:** export any profile to a `.json` file and import other people's files. Imported files are fully validated first.

Talk normally: "the right stick drifts", "aiming feels twitchy", "the brake is too short", "turn off rumble". Claude reads your current settings, changes them in small steps, and asks a short question when a request could mean two things. It answers in your language and quotes Space Station's buttons with the app's own wording in all 12 of its languages.

## Supported controllers

| Controller | Extra buttons | Stick settings | Status |
|---|---|---|---|
| **VADER 5 Pro** | C, Z, M1–M6 | deadzones, custom curve, circularity | tested on a physical controller |
| **VADER 4 Pro** | C, Z, M1–M4 | deadzones, custom curve, circularity | verified against Space Station's data |
| **APEX 4** | M1–M4 | most editions: center deadzone only; WuKong edition: full | verified against Space Station's data |
| **VADER 3 Pro** | C, Z, M1–M4 | center deadzone only | verified against Space Station's data |

Special editions (EVA, ONE PIECE, DRAGON BALL Z, Assassin's Creed, Black Myth WuKong…) follow their base model. VADER 3, Direwolf 3/4 and APEX 5 can be read and exported, but not edited yet.

Each model's buttons and limits come from Space Station itself. "Verified against Space Station's data" means the plugin passes every check on that model's real factory profiles, but nobody has yet tried it with the physical controller. **Own one?** The 15-minute test in [CONTRIBUTING.md](CONTRIBUTING.md) helps everyone.

## Install

You need Windows, [Flydigi Space Station](https://www.flydigi.com/), [Claude Code](https://claude.com/claude-code) and [uv](https://docs.astral.sh/uv/), which sets up Python on its own.

```bash
claude plugin marketplace add migueldpsp/flydigi-tuner
```

```bash
claude plugin install flydigi-tuner@flydigi-tuner
```

Then start a new Claude Code session and ask, for example, "show me my Space Station profiles".

If Space Station is not installed in `C:\Program Files\Flydigi Space Station`, set the `FLYDIGI_DATA_DIR` environment variable to its folder.

## Using it

1. **Ask.** Reading works with Space Station open or closed.
2. **Close Space Station to create or edit**, including from the system tray. Its service talks to one program at a time.
3. **Approve.** Claude shows the changes first and only creates the local profile once you agree.
4. **Apply it yourself** in Space Station, on the slot you choose.
5. **Changed your mind?** Ask Claude to undo. Each undo goes one step further back.

## Good to know

- **Space Station updates:** the plugin re-reads the app's format after every update and checks that every field it uses is still there, with the same type. If anything it relies on changes, writing is blocked, with the exact field named, until the plugin is updated. Reading keeps working.
- **Backups:** every change is backed up first, and the newest 50 backups are kept.
- **Out of scope, on purpose:** writing to the controller, firmware, calibration, global controller settings (polling rate, sleep timer, global sensitivity, debounce), adaptive trigger modes and creating macros.

## How it works

Space Station has a UI (Electron) and a background service (`SpaceStationService.exe`) that talk over the named pipe `\\.\pipe\fcs.sock` with protobuf messages. Flydigi Tuner:

- **reads** profiles straight from Space Station's `.dat` files;
- **creates** local profiles with the same command the app uses to import a shared profile code, so the service writes the file and its index itself;
- recomputes stick curves with the app's own formula (verified against real profiles);
- reads the message format and the UI labels **from your own Space Station installation** the first time it runs, and again after every Space Station update ([extract.py](server/flydigi/extract.py)). It caches them in `%LOCALAPPDATA%\flydigi-tuner\cache`.

**This repository contains no Space Station code, data or files.** It only lists which fields the plugin relies on ([required.py](server/flydigi/required.py)), and its tests use a small self-written specification of those fields ([schema_stub.py](tests/schema_stub.py)) and synthetic profiles.

| Test | Needs | What it checks |
|---|---|---|
| `tests/test_offline.py` | nothing | Edits, per-model rules, validation, command blocking, backups and undo, compatibility, export/import, languages. Synthetic data only; runs in CI. |
| `tests/test_mcp_stdio.py` | nothing | Starts the real MCP server and calls every read-only tool, plus malformed input. Runs in CI. |
| `tests/test_real_data.py` | Space Station | Read-only checks against your real profiles and the factory profiles of every supported model. |
| `tests/test_live.py` | Space Station, closed | Against the real service: create, edit, rename, move, export, import, undo and delete a temporary profile, then checks nothing else changed. |

```bash
uv run --script tests/test_offline.py
```

## Disclaimer

Unofficial project, not affiliated with or endorsed by Flydigi. "Flydigi", "Space Station", "VADER", "APEX" and "Direwolf" are trademarks of their owners. Flydigi Tuner relies on an internal interface that may change with any Space Station update. Use it at your own risk.

## License

[MIT](LICENSE). See [CHANGELOG.md](CHANGELOG.md) for each version's changes and [CONTRIBUTING.md](CONTRIBUTING.md) to test a controller or add a model.
