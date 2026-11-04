"""Constants for the SmarterSpa+ integration.

Two connection modes. Cloud talks to the original vendor's Firebase backend
with command strings observed from the app. Local talks to the replacement
controller (smarterspa-local) over its REST API and event stream.
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


# Salt status codes from the original controller's source (cgsupport.operation):
# electrode current under 1.0 A is 0 (low, red LED), 1.0 to 2.0 A is 1 (ok,
# blue), over 2.0 A is 2 (high, green), overcurrent shutdown is 3, and 4 means
# no cycle has run since boot. The first version of this map had 0 and 1
# swapped, based on the app's labels.
COMMAND_TARGETS = {
    CMD_CHLORINE_ON: ("Main", "g", 1),
    CMD_CHLORINE_OFF: ("Main", "g", 0),
    CMD_LIGHTS_ON: ("Settings", "l", 1),
    CMD_LIGHTS_OFF: ("Settings", "l", 0),
    **{cmd_power_level(n): ("Main", "p", n) for n in range(1, 11)},
    **{cmd_zero_point(n): ("Settings", "z", n) for n in range(10, 151)},
}
ALLOWED_COMMANDS = frozenset(COMMAND_TARGETS) | {CMD_UPDATE_CHECK}

SALT_STATUS = {0: "low", 1: "ok", 2: "high", 3: "shutdown", 4: "unknown"}

CONF_UID = "uid"
CONF_DEVICE_ID = "device_id"

# Connection modes. Entries created before local mode existed have no
# CONF_CONNECTION and are cloud.
CONF_CONNECTION = "connection"
CONNECTION_CLOUD = "cloud"
CONNECTION_LOCAL = "local"
CONF_TOKEN = "token"
DEFAULT_LOCAL_PORT = 8080

LOCAL_FALLBACK_INTERVAL = timedelta(seconds=60)
"""Poll this often in local mode as a backstop to the event stream."""

LOCAL_NETWORK_INTERVAL = timedelta(minutes=5)
