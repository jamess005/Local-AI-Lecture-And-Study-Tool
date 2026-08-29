"""Colour system for the Lecture & Study Tool (dark).

Shares its ground and neon character with MathView and Stock Manager so the
three read as siblings. The chrome accent is violet here: MathView's red and
Stock Manager's cyan are already taken, and a study tool has no prior meaning
attached to any hue, so it can take the one that is free.

Every colour used anywhere in the UI is named here. No hex literal should
appear in app.py, notes_tab.py or study_tab.py.

Contrast against SURFACE, measured: INK 17.0:1, INK2 6.7:1, MUTED 3.5:1,
ACCENT 9.0:1, GOOD 10.5:1, WARN 10.9:1, BAD 5.6:1. White text on PRIMARY is
5.2:1, comfortably above the 4.5:1 needed for body text.
"""

# Ground.
PAGE = "#08080a"
SURFACE = "#121215"
RAISED = "#1c1c21"
BORDER = "#2a2a31"

# Text.
INK = "#f4f4f6"
INK2 = "#9a9aa6"
MUTED = "#6a6a76"

# Chrome accent - violet. Highlights and focus, never a status.
ACCENT = "#b4a9ff"

# Primary action. Deeper than ACCENT so white button text stays readable.
PRIMARY = "#6d4aff"
PRIMARY_HOVER = "#8468ff"

# Secondary action - recedes into the panel rather than competing.
NEUTRAL = "#2a2a31"
NEUTRAL_HOVER = "#35353d"

# Status. Reserved for state; never decoration.
GOOD = "#3ddc84"
WARN = "#ffb931"
BAD = "#ff4757"
BAD_HOVER = "#d92d3d"

# Destructive action fill - darker than BAD so its white label stays legible.
DANGER = "#8c1622"
DANGER_HOVER = "#a81b2a"

# Positive action fill. GOOD is a status colour and far too light to carry
# white button text; this is its fill counterpart.
SUCCESS = "#1f7a4d"
SUCCESS_HOVER = "#27965f"
