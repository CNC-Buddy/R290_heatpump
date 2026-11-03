"""Short-lived, connection-bound panel grants verified against live P183.

This prevents accidental writes through the panel, not native HA administrator
services. Passwords and password-register changes are never stored in the audit.
"""
import asyncio
import hashlib
import hmac
import secrets
import time

PASSWORD_REGISTER = 0x01B7
TTL = 600


class ConnectionGrants:
    """Stored as a HA disconnect subscription; ActiveConnection uses slots."""

    def __init__(self):
        self.values = {}
        self.closed = False

    def __call__(self):
        self.values.clear()
        self.closed = True


def access_state(connection):
    key = ("r290_heatpump", "system_access")
    if key not in connection.subscriptions:
        connection.subscriptions[key] = ConnectionGrants()
    return connection.subscriptions[key]


def grants(connection):
    return access_state(connection).values


def status(connection):
    now = time.monotonic()
    return {key: max(0, int(value["until"] - now)) for key, value in grants(connection).items()
            if value["until"] > now and value["user"] == connection.user.id}


async def password(hass, entry):
    runtime = hass.data["r290_heatpump"].get(entry.entry_id, {})
    if entry.data.get("device_type") != "heat_pump" or getattr(entry, "disabled_by", None) or not runtime.get("hub"):
        raise ValueError("WÃ¤rmepumpe nicht erreichbar / Heat pump unavailable")
    hub = runtime["hub"]
    args = (int(entry.data.get("slave", 1)), PASSWORD_REGISTER, 1)
    async with asyncio.timeout(8):
        values = await hub.async_read_block(*args, owner=entry.entry_id, priority=0) if getattr(hub, "scheduler", None) else await hub.async_read_block(*args)
    if len(values) != 1 or type(values[0]) is not int or not 0 <= values[0] <= 9999:
        raise ValueError("P183 nicht lesbar / Cannot read P183")
    return str(values[0])


def digest(secret, value):
    return hmac.new(secret, value.encode(), hashlib.sha256).digest()


async def unlock(hass, connection, entries, supplied):
    if not isinstance(supplied, str) or not supplied.isascii() or not supplied.isdigit() or len(supplied) > 4:
        raise ValueError("Passwort muss 1â€“4 Ziffern enthalten / Password must contain 1â€“4 digits")
    panel = hass.data["r290_heatpump"]["_panel"]
    attempts = panel.setdefault("system_attempts", {})
    now = time.monotonic()
    attempts[connection.user.id] = [at for at in attempts.get(connection.user.id, []) if now-at < 60]
    if len(attempts[connection.user.id]) >= 5:
        raise ValueError("Bitte eine Minute warten / Please wait one minute")
    attempts[connection.user.id].append(now)
    access = access_state(connection)
    pending = {}
    for entry in entries:
        # Relocking first ensures a failed attempt cannot retain an old grant.
        grants(connection).pop(entry.entry_id, None)
    for entry in entries:
        actual = await password(hass, entry)
        if not hmac.compare_digest(str(int(supplied)), actual):
            raise ValueError("Passwort stimmt nicht mit P183 Ã¼berein / Password does not match P183")
        secret = secrets.token_bytes(32)
        pending[entry.entry_id] = {"until": time.monotonic()+TTL, "secret": secret,
                                   "digest": digest(secret, actual), "user": connection.user.id}
    if access.closed:
        raise ValueError("Verbindung beendet / Connection closed")
    access.values.update(pending)


async def verify(hass, connection, entry):
    access = access_state(connection)
    grant = access.values.get(entry.entry_id)
    if not grant or grant["until"] <= time.monotonic() or grant["user"] != connection.user.id:
        raise ValueError("Systemparameter gesperrt: P183 eingeben / System parameters locked: enter P183")
    try:
        actual = await password(hass, entry)
        if access.closed:
            raise ValueError("Verbindung beendet / Connection closed")
        if not hmac.compare_digest(grant["digest"], digest(grant["secret"], actual)):
            raise ValueError("P183 wurde geÃ¤ndert; erneut entsperren / P183 changed; unlock again")
    except Exception:
        grants(connection).pop(entry.entry_id, None)
        raise
