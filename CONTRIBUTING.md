# Contributing

The most useful contribution right now is **testing a controller model on real hardware**. The VADER 4 Pro, APEX 4 and VADER 3 Pro are supported and checked against Space Station's own data, but nobody has yet run them end to end with the physical controller.

## Test your controller (about 15 minutes)

You need Windows, Flydigi Space Station, [uv](https://docs.astral.sh/uv/), Claude Code with this plugin installed, and your controller.

1. **Refresh the data.** Connect the controller, open Space Station once so it reads the controller, then close Space Station completely (including from the system tray).
2. **Run the read-only check.** It writes nothing:

   ```bash
   uv run --script tests/test_real_data.py
   ```

   It must end with `OK`. Note the lines that name your controller.
3. **Ask Claude to identify the controller.** Ask: "What controller do I have and what can you change on it?" Check that it names your exact model (for example "APEX 4 [k2]") and does not offer buttons your controller lacks.
4. **Create a test profile.** Ask for a small, easy-to-check profile based on slot 1. For example: "map M1 to A, raise the left stick deadzone a little, and make the right trigger reach full press at half travel". Check the dry run, approve it, and let Claude create it.
5. **Check it in Space Station.** Open Space Station. The profile must appear under **Inactive Configs** with its name. Look through it and compare the values with what Claude reported.
6. **Apply it to a slot you don't mind overwriting.** First use **Duplicate** on that slot to keep a backup. Then use **Apply to onboard configs** on the test profile.
7. **Check that it works.** Press Win + R, type `joy.cpl` and open the controller's properties. M1 must act as A, the left stick must need a little more movement to register, and the right trigger must reach the maximum at about half travel.
8. **Restore your slot** from the copy you made in step 6.
9. **Report it** with the "Controller test report" issue template. Include the output of step 2.

**What to share:** the output of `tests/test_real_data.py` and what you observed. It contains no personal data. Do not share the files in Space Station's `Configs` folder: they include your controller's identifier.

## Adding a new controller model

1. Find the model's code and name in Space Station's English translations (`product_name_<code>_keep`).
2. Read its buttons from Space Station's per-model layout. Check which settings Space Station's UI hides for that model and which profile format version its factory profiles use (`protoVersion`; below 769 means the older stick protocol).
3. Add a `Model` entry to [server/flydigi/models.py](server/flydigi/models.py), with notes for anything unusual, and add the code to `PROTO` and `FACTORY_ID` in [tests/fixtures.py](tests/fixtures.py).
4. Add model-specific cases to `tests/test_offline.py` (what it must accept and what it must reject), then run every test.
5. Mark the model `hardware_tested=False` until someone completes the hardware test above.

## Code changes

- Never add a command that writes to the controller. `ipc.ALLOWED` is the complete list of commands that may be sent, and any change to it needs a clear reason in the pull request.
- Never commit anything taken from Space Station (code, message format, translations, factory profiles, images). The plugin reads what it needs from the user's own installation at runtime. If you use a new message, field or enum value, add its name to [required.py](server/flydigi/required.py) and a minimal self-written entry to [tests/schema_stub.py](tests/schema_stub.py).
- Every user-facing message is in English, clear and actionable.
- `tests/test_offline.py` and `tests/test_mcp_stdio.py` must pass (CI runs them). Run `tests/test_real_data.py` and, with Space Station closed, `tests/test_live.py` if you have Space Station installed.
- Add an entry to [CHANGELOG.md](CHANGELOG.md).
