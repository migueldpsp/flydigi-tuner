# Changelog

## 0.7.0

### Changed
- **The repository no longer contains anything from Space Station.** The message format and the UI labels are read from the user's own installation the first time the plugin runs, and again after every Space Station update. They are cached in `%LOCALAPPDATA%\flydigi-tuner\cache`. The bundled `descriptors.tsv` and `ui_labels.json` and the `tools/extract_ui_labels.py` script are gone.
- Stronger compatibility check: the installed app's format must contain every message, field and enum value the plugin uses (`required.py`), with the same types. Otherwise writes are blocked and the missing field is named.
- Tests run against a synthetic app laid out like Space Station's, built from a small self-written specification of the 37 messages and 115 fields the plugin uses (`tests/schema_stub.py`), so CI also exercises the code that reads the format from the app.

## 0.6.0

### Changed
- **Slots are numbered 1-4, exactly as Space Station shows them** (`slot:1` … `slot:4`; factory slots too). They were 0-3 before, one off from what users see in the app, which could lead to overwriting the wrong slot.
- Profile views only list the buttons the controller physically has (no reserved slots, no M5/M6 on four-paddle models) and add a summary: `remapped_buttons`, the trigger travel as a percentage, and which stick settings the model offers. Summary fields never show up as changes.
- The skill asks Claude to summarise profiles instead of listing every button, and to always name a slot by number and name.

### Quality
- The code passes `ruff` lint and format checks, which CI now enforces (`ruff.toml`). This removed an unused import, closes every file it opens, and keeps the cause of chained errors.

## 0.5.0

### Added
- Replies in the user's language with Space Station's exact UI names: `status(language=...)` returns the app's own labels (Inactive Configs, Apply to onboard configs, Duplicate…) in any of its 12 languages, extracted from the app by `tools/extract_ui_labels.py`. Regional codes such as `es-MX`, `pt-BR`, `zh-TW` and `pl` are understood, and a missing language falls back to English with a note.
- Changes are described in plain words and in a logical order, for example `Left trigger › full-press point: 255 → 120 (100% → 47% of travel)`, instead of technical paths.
- The skill has a language and clarity rule: answer in the user's language, translate tool output, never translate the app's labels yourself, show changes as a short table and end with one clear next step. It includes a worked example.

### Fixed
- The guide called Space Station's slot-copy button "Copy"; its real label is "Duplicate".

## 0.4.0

### Added
- `undo_last_change`: undoes the most recent change to local profiles; repeat it to go further back. Every undo says how to redo it. Verified against the real service, which never brings an undone profile back.
- `list_backups` now shows when each backup was taken and which change it precedes.
- A note when the copy of the controller's slots is 14 or more days old, both in the profile list and when a slot is used as a base.
- CONTRIBUTING.md with a 15-minute hardware test for owners of untested models, a guide to adding new models, and a GitHub issue template for test reports.

### Fixed
- Malformed input no longer crashes a tool. Examples: `slot:x`, a factory slot that does not exist, a section given as text or a list instead of an object, or exporting to a folder that does not exist. Each now gets a clear message, and a safety net turns any unexpected error into a readable one. 18 such inputs are now tested through the real MCP server.
- `status` works when Space Station is installed but no controller is registered yet.
- On models with the older stick protocol, a deadzone change on a stick in mouse or keyboard mode is now rejected, instead of being silently ignored.

## 0.3.0

### Added
- Support for the **VADER 4 Pro** (`f4`), **APEX 4** (`k2`) and **VADER 3 Pro** (`f3p`), alongside the VADER 5 Pro
  (`f5`). Each model only accepts the buttons it physically has and the stick settings Space Station offers for it:
  - APEX 4: no C/Z buttons;
  - VADER 4 Pro, APEX 4 and VADER 3 Pro: no M5/M6;
  - VADER 3 Pro and most APEX 4 editions: older stick protocol, with center deadzone 0..40 only and no edge
    deadzone or custom curve;
  - APEX 4 and VADER 3 Pro: no circularity.
- Controllers are always shown by commercial name and code (for example `VADER 4 Pro [f4]`), with their support
  level and model notes. Other Flydigi models are listed as read-only.
- When several controllers have data on the PC, the plugin asks which one instead of picking.
- The skill explains how to turn plain-language requests ("drifts", "fires too late", "more precise") into settings,
  with default step sizes and starting points for each type of game.
- `test_real_data.py` checks the real factory profiles of every supported model.

## 0.2.0

### Added
- `export_profile` / `import_profile`: share profiles as portable `.json` files without Flydigi's cloud.
  Imports are untrusted: format, checksum, controller model and every value range are validated before
  anything is created, and an outdated stick curve table is repaired with a warning.
- Compatibility checks in `status`: Space Station version (tested: 4.2.3.1) and profile format. If the format
  changed, every write is blocked while reading keeps working; an untested version only adds a warning.
- Synthetic test data (`tests/fixtures.py`), so the tests need neither a Space Station install nor real user data.
- `tests/test_real_data.py`: read-only checks of the plugin's assumptions against the local install.
- GitHub Actions workflow, MIT license and this changelog.

### Fixed
- Trigger edits now also update the trigger curve endpoints, exactly as Space Station's service does.
- Two changes within the same second no longer fail because of a backup folder name collision.
- Only the newest 50 backups are kept.
- Reserved button slots show as `Reserved26` instead of a bare number.

## 0.1.0

- First version: read slots, local and factory profiles; create, edit, duplicate, rename, reorder and delete
  local profiles; backups and restore. Never writes to the controller.
