"""Controller models: commercial names and what each one physically has.

Space Station identifies controllers by an internal code (f4, k2, ...). Every profile file stores the same 32
button slots for every model, so what a model really has comes from Space Station's own per-model layout and
UI rules (see the notes on each model). Models not listed here can be read but not edited."""

from dataclasses import dataclass, field

STANDARD_BUTTONS = [
    "Up",
    "Right",
    "Down",
    "Left",
    "A",
    "B",
    "X",
    "Y",
    "Select",
    "Start",
    "Lb",
    "Rb",
    "Lt",
    "Rt",
    "Thl",
    "Thr",
]

# Names Space Station uses for each code (from its English UI), including special editions.
FAMILY_NAMES = {
    "f3": "VADER 3",
    "f3p": "VADER 3 Pro",
    "f4": "VADER 4 Pro",
    "f5": "VADER 5 Pro",
    "fp3": "Direwolf 3",
    "fp4": "Direwolf 4",
    "k2": "APEX 4",
    "k5": "APEX 5",
}
EDITIONS = {
    "f3p": {"80": "VADER 3 Pro", "81": "VADER 3 Pro ONE PIECE", "88": "VADER 3 Pro EVA"},
    "f4": {"85": "VADER 4 Pro", "91": "VADER 4 Pro Assassin's Creed", "105": "VADER 4 Pro"},
    "f5": {"130": "VADER 5 Pro", "144": "VADER 5 Pro DRAGON BALL Z", "145": "VADER 5 Pro"},
    "k2": {
        "84": "APEX 4",
        "86": "APEX 4 EVA",
        "87": "APEX 4 STN",
        "92": "APEX 4 Assassin's Creed",
        "93": "ARDOR GAMING APEX 4",
        "102": "Apex 4 Black Myth WuKong",
    },
}


@dataclass(frozen=True)
class Model:
    code: str
    name: str
    extra_buttons: tuple
    circularity: bool  # Space Station shows the stick circularity setting
    hardware_tested: bool  # verified end to end with a physical controller
    notes: tuple = field(default=())

    @property
    def buttons(self) -> list[str]:
        """Buttons the user can physically press, i.e. the ones that can be remapped."""
        return STANDARD_BUTTONS + list(self.extra_buttons)


SUPPORTED = {
    "f5": Model("f5", "VADER 5 Pro", ("C", "Z", "M1", "M2", "M3", "M4", "M5", "M6"), True, True),
    "f4": Model("f4", "VADER 4 Pro", ("C", "Z", "M1", "M2", "M3", "M4"), True, False),
    "k2": Model(
        "k2",
        "APEX 4",
        ("M1", "M2", "M3", "M4"),
        False,
        False,
        (
            "No C/Z buttons (owners report the Apex 4 dropped them; "
            "Space Station's shared layout file still lists them).",
            "Most APEX 4 editions use Space Station's older stick protocol (center deadzone 0..40, no edge "
            "deadzone, no custom curve); the Black Myth WuKong edition uses the current one. "
            "Detected per profile automatically.",
            "Stick circularity is hidden by Space Station on most APEX 4 units, so it is not editable here.",
            "Adaptive (force feedback) trigger modes are not edited by this plugin.",
        ),
    ),
    "f3p": Model(
        "f3p",
        "VADER 3 Pro",
        ("C", "Z", "M1", "M2", "M3", "M4"),
        False,
        False,
        (
            "Uses Space Station's older stick protocol: center deadzone 0..40 only, no edge deadzone and no custom "
            "curve.",
            "Stick circularity is hidden by Space Station on this model.",
        ),
    ),
}

# Space Station switches to its older stick settings for profiles below this format version.
NEW_STICK_PROTOCOL = 769


class UnsupportedModel(LookupError):
    pass


def name(code: str) -> str:
    return FAMILY_NAMES.get(code, "unknown Flydigi controller")


def label(code: str) -> str:
    """Unambiguous label used everywhere: commercial name plus internal code."""
    return f"{name(code)} [{code}]"


def get(code: str) -> Model:
    if code not in SUPPORTED:
        raise UnsupportedModel(
            f"{label(code)} can be read but not edited yet. Supported for editing: "
            + ", ".join(label(c) for c in SUPPORTED)
            + "."
        )
    return SUPPORTED[code]


def support_level(code: str) -> str:
    if code not in SUPPORTED:
        return "read-only (not supported for editing yet)"
    if SUPPORTED[code].hardware_tested:
        return "supported, tested on a physical controller"
    return "supported, verified against Space Station's data (not yet tested on a physical controller)"


def old_stick_protocol(bean) -> bool:
    return bean.protoVersion < NEW_STICK_PROTOCOL
