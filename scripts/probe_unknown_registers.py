"""Bounded read-only FC03 probe of undocumented addresses in the workbook.

Uses a new TCP socket and transaction 1 per request for the configured proxy.
Never writes registers, changes HA, or connects to the upstream RTU gateway.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import struct
import time

ROOT = Path(__file__).resolve().parents[1]


def receive(sock, count):
    data = b""
    while len(data) < count:
        part = sock.recv(count - len(data))
        if not part:
            raise OSError("Incomplete Modbus response")
        data += part
    return data


def read_registers(host, port, slave, address, count):
    if not (1 <= slave <= 247 and 1 <= count <= 32 and 0x40 <= address <= address + count - 1 <= 0xFF):
        raise ValueError("Read outside documented realtime range")
    with socket.create_connection((host, port), timeout=12) as sock:
        sock.settimeout(12)
        sock.sendall(struct.pack(">HHHBBHH", 1, 0, 6, slave, 3, address, count))
        transaction, protocol, length, unit = struct.unpack(">HHHB", receive(sock, 7))
        if (transaction, protocol, unit) != (1, 0, slave) or not 2 <= length <= 67:
            raise ValueError("Invalid response header")
        pdu = receive(sock, length - 1)
        if pdu[0] == 0x83:
            raise ValueError(f"Modbus exception {pdu[1]}")
        if pdu[:2] != bytes((3, count * 2)) or len(pdu) != 2 + count * 2:
            raise ValueError("Invalid FC03 payload")
        return struct.unpack(">" + "H" * count, pdu[2:])


def blocks(addresses):
    for address in sorted(addresses):
        if 'start' not in locals():
            start = end = address
        elif address == end + 1 and address - start < 32:
            end = address
        else:
            yield start, end - start + 1
            start = end = address
    if 'start' in locals():
        yield start, end - start + 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    catalog = json.loads((ROOT / "custom_components/r290_heatpump/frontend/register-catalog.json").read_text(encoding="utf-8"))
    addresses = {r["address"] for r in catalog["records"] if r["unknown"] and r["section"] == 2}
    result = dict(method="FC03, fresh proxy socket; raw uint16, int16 shown without scaling", samples=[], errors=[])
    failed = 0
    for sample in range(2):
        for slave in (1, 2):
            for start, count in blocks(addresses):
                at = datetime.now(timezone.utc).isoformat()
                try:
                    values = read_registers(args.host, args.port, slave, start, count)
                    result["samples"].extend(dict(at=at, slave=slave, address=start+i, raw=v, signed=v if v < 32768 else v-65536) for i, v in enumerate(values))
                    failed = 0
                except (OSError, ValueError) as exc:
                    result["errors"].append(dict(at=at, slave=slave, address=start, count=count, error=str(exc)))
                    failed += 1
                if failed >= 3:
                    break
                time.sleep(.3)
            if failed >= 3:
                break
        if failed >= 3:
            break
        if sample == 0:
            time.sleep(3)
    path = ROOT / "artifacts/register-live-samples.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(dict(samples=len(result['samples']), errors=result['errors'], path=str(path)), ensure_ascii=False))


if __name__ == "__main__":
    main()
