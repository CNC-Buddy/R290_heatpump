"""Conservative functional priorities; no inferred device compatibility."""

import math

DEFAULTS = {
    "polling_profile": "legacy",
    "poll_fast": 10.0,
    "poll_normal": 30.0,
    "poll_slow": 120.0,
    "poll_config": 600.0,
    "poll_budget": 0.6,
}
BOUNDS = {
    "poll_fast": (5, 60),
    "poll_normal": (5, 300),
    "poll_slow": (30, 1800),
    "poll_config": (60, 86400),
    "poll_budget": (0.1, 0.9),
}


def settings(data):
    result = {k: data.get(k, v) for k, v in DEFAULTS.items()}
    if result["polling_profile"] not in ("legacy", "auto"):
        raise ValueError("Unknown polling profile")
    for key, (low, high) in BOUNDS.items():
        result[key] = float(result[key])
        if not math.isfinite(result[key]) or not low <= result[key] <= high:
            raise ValueError(f"Invalid {key}")
    if (
        not result["poll_fast"]
        <= result["poll_normal"]
        <= result["poll_slow"]
        <= result["poll_config"]
    ):
        raise ValueError("Require fast <= normal <= slow <= configuration interval")
    return result


def policy(address, requested, config):
    # All enabled real-time measurements remain at least normal priority.
    # Tanks are deliberately not classified as slow: DHW control consumes them.
    if 0 <= address < 0x40 or address in (0x40, 0x58, 0x5E):
        priority, target = 1, config["poll_fast"]
    elif address == 0x4A:
        priority, target = 3, config["poll_slow"]
    elif 0x40 <= address <= 0xFF:
        priority, target = 2, config["poll_normal"]
    else:
        priority, target = 3, config["poll_config"]
    interval = min(float(requested), target)
    # Age bounds do not grow with adaptive slowdown. Consumers can require less.
    return (
        interval,
        priority,
        (
            min(120.0, max(30.0, interval * 2.5))
            if priority <= 2
            else max(60.0, interval * 2.5)
        ),
    )


ATOMIC_PAIRS = ((0xE5, 0xE6), (0xEC, 0xED))


def blocks(addresses, limit):
    """Only join explicitly requested neighbours; do not split known word pairs."""
    addresses = sorted(set(addresses))
    limit = max(1, min(125, int(limit)))
    while addresses:
        start = addresses.pop(0)
        block = [start]
        # The adaptive single-register fallback still keeps a requested pair
        # together; two words are the minimum useful read of that value.
        if addresses and (start, addresses[0]) in ATOMIC_PAIRS:
            block.append(addresses.pop(0))
        while addresses and addresses[0] == block[-1] + 1 and len(block) < limit:
            if len(block) == limit - 1 and any(
                addresses[0] == a and b in addresses for a, b in ATOMIC_PAIRS
            ):
                break
            block.append(addresses.pop(0))
        yield block[0], len(block)
