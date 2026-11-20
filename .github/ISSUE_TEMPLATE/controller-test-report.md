---
name: Controller test report
about: Report how the plugin works with your Flydigi controller (see CONTRIBUTING.md)
title: "Test report: <controller name>"
labels: hardware-test
---

**Controller** (as Claude named it, for example "APEX 4 [k2]"):

**Edition** (standard, EVA, Black Myth WuKong…):

**Space Station version:**

**Plugin version** (from CHANGELOG.md):

### Output of `uv run --script tests/test_real_data.py`

```
paste here
```

### Results

- [ ] Claude named the model correctly and did not offer buttons the controller lacks
- [ ] The test profile appeared under "Inactive Configs" with the right name
- [ ] The values shown in Space Station matched what Claude reported
- [ ] After "Apply to onboard configs", the remapped button worked (checked with joy.cpl)
- [ ] The stick deadzone change was noticeable
- [ ] The trigger change was noticeable

### Anything unexpected

