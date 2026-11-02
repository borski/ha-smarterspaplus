"""Constants for the SmarterSpa+ integration.

Cloud configuration and commands observed from the original SmarterSpa+ app.
Only verified command strings are sent to the device.
"""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "smarterspa"

# Reference 3.1. Public Firebase client config from the app bundle.
PROJECT_ID = "controlomatic-ss-plus"
API_KEY = "AIzaSyCn5Yq8kQ6TX8wbrj_-bPUFsCbeCrNqopU"

SIGNIN_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"
REFRESH_URL = f"https://securetoken.googleapis.com/v1/token?key={API_KEY}"
FIRESTORE_BASE = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"


def document_url(uid: str) -> str:
    """Reference 3.3. One document per account."""
    return f"{FIRESTORE_BASE}/users/{uid}/ss_data/data"


# Polling. Reference 3.5 says allow up to 10 s for a command to land.
NORMAL_INTERVAL = timedelta(seconds=30)
FAST_INTERVAL = timedelta(seconds=2)
FAST_WINDOW = timedelta(seconds=10)

# Refresh the ID token when this much of its hour is left.
TOKEN_REFRESH_MARGIN = timedelta(minutes=5)

# Reference 3.5. Exact strings as captured. Do not add to this list
# without a captured observation in the reference.
CMD_CHLORINE_ON = "V1.1.8.B+"
CMD_CHLORINE_OFF = "V1.1.8.B-"
CMD_LIGHTS_ON = "L+"
CMD_LIGHTS_OFF = "L-"
CMD_UPDATE_CHECK = "Uc"


def cmd_power_level(level: int) -> str:
    if type(level) is not int or not 1 <= level <= 10:
        raise ValueError("power level must be 1..10")
    return f"V1.1.8.P+{level}/"


def cmd_zero_point(value: int) -> str:
    if type(value) is not int or not 10 <= value <= 150:
        raise ValueError("zero point must be 10..150")
    return f"Zz{value}/"


# Reference 3.3. Salt status codes. Only 0 and 1 are verified.
COMMAND_TARGETS = {
    CMD_CHLORINE_ON: ("Main", "g", 1),
    CMD_CHLORINE_OFF: ("Main", "g", 0),
    CMD_LIGHTS_ON: ("Settings", "l", 1),
    CMD_LIGHTS_OFF: ("Settings", "l", 0),
    **{cmd_power_level(n): ("Main", "p", n) for n in range(1, 11)},
    **{cmd_zero_point(n): ("Settings", "z", n) for n in range(10, 151)},
}
ALLOWED_COMMANDS = frozenset(COMMAND_TARGETS) | {CMD_UPDATE_CHECK}

SALT_STATUS = {0: "ok", 1: "low"}

CONF_UID = "uid"
CONF_DEVICE_ID = "device_id"
