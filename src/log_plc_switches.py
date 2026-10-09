"""
log_plc_switches.py
-------------------
Extracts and logs live PLC Digital I/O, Limit Switches, Proximity Sensors,
Cylinder Position feedbacks, and Error flags from ALL Festo CP Factory PLCs simultaneously.

Supports:
  - Station 1 (ASRS)      : 172.21.1.1
  - Station 3 (RASS)      : 172.21.3.1
  - Station 6 (Magazine)  : 172.21.6.1
  - Station 7 (Mpress)    : 172.21.7.1

Features:
  1. Simultaneously connects to all 4 active GJU PLCs in parallel asyncio tasks.
  2. Discovers all digital I/O, limit switches, and sensor tags on each station.
  3. Live terminal event monitor: prints in real-time with station tags when any switch changes state.
  4. Saves synchronized labeled CSVs for each station + consolidated master CSV to Smart maintenance/data/.

Usage:
    # 1. Log ALL active stations simultaneously:
    python "Smart maintenance\\log_plc_switches.py" --station ALL --label LIMIT_SWITCH_TEST

    # 2. Log ALL stations for 60 seconds auto-timed:
    python "Smart maintenance\\log_plc_switches.py" --station ALL --label LIMIT_SWITCH_TEST --duration 60

    # 3. Log a single station:
    python "Smart maintenance\\log_plc_switches.py" --station RASS --label LIMIT_SWITCH_TEST
"""

import asyncio
import argparse
import datetime
import os
import sys
import pandas as pd

try:
    from asyncua import Client, ua
except ImportError:
    print("[ERROR] 'asyncua' library not installed. Run: pip install asyncua")
    sys.exit(1)


PLC_DIRECTORY = {
    "ASRS": {"ip": "172.21.1.1", "name": "Station 1 — High-Bay Storage"},
    "RASS": {"ip": "172.21.3.1", "name": "Station 3 — Robot Assembly"},
    "MAGAZINE": {"ip": "172.21.6.1", "name": "Station 6 — Magazine Feeder"},
    "MPRESS": {"ip": "172.21.7.1", "name": "Station 7 — Muscle Press"},
}

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


async def discover_boolean_nodes(node, max_depth=4, current_depth=0, found=None, path=""):
    """Recursively discover boolean tags (limit switches, sensors, solenoids)."""
    if found is None:
        found = {}
    if current_depth > max_depth:
        return found

    try:
        children = await node.get_children()
        for child in children:
            try:
                name = (await child.read_display_name()).Text
                node_class = await child.read_node_class()
                child_path = f"{path}.{name}" if path else name

                # NodeClass.Variable = 2
                if int(node_class) == 2:
                    try:
                        val = await child.read_value()
                        if isinstance(val, bool):
                            clean_name = (
                                child_path.replace("DeviceSet.", "")
                                .replace("plcRass.", "")
                                .replace("plcMPress.", "")
                                .replace("plcMagBack.", "")
                                .replace("plcASRS32.", "")
                            )
                            found[child.nodeid.to_string()] = {
                                "name": clean_name,
                                "node": child,
                                "last_val": val,
                            }
                    except Exception:
                        pass
                else:
                    if name not in ["Server", "Aliases", "ServerCapabilities"]:
                        await discover_boolean_nodes(child, max_depth, current_depth + 1, found, child_path)
            except Exception:
                pass
    except Exception:
        pass

    return found


async def log_single_plc_task(station_key: str, label: str, interval: float, records: list, stop_event: asyncio.Event):
    """Task to stream boolean limit switches for one PLC."""
    plc_info = PLC_DIRECTORY[station_key]
    ip = plc_info["ip"]
    url = f"opc.tcp://{ip}:4840"

    print(f"  [{station_key:<8}] Connecting to PLC at {url} ...")

    try:
        async with Client(url=url, timeout=6) as client:
            print(f"  [{station_key:<8}] ✓ Connected! Discovering switches & sensors ...")

            objects = client.nodes.objects
            bool_tags = await discover_boolean_nodes(objects, max_depth=4)
            if not bool_tags:
                bool_tags = await discover_boolean_nodes(client.nodes.root, max_depth=4)

            nodes_to_read = [info["node"] for info in bool_tags.values()]
            tag_info_list = list(bool_tags.values())

            while not stop_event.is_set():
                now = datetime.datetime.now()
                ts_str = now.strftime("%H:%M:%S.%f")[:-3]
                row = {
                    "timestamp": ts_str,
                    "station": station_key,
                    "label": label,
                }

                try:
                    vals = await client.read_values(nodes_to_read)
                    for info, val in zip(tag_info_list, vals):
                        tag_name = info["name"]
                        row[tag_name] = int(val) if isinstance(val, bool) else val

                        # Edge trigger display
                        if isinstance(val, bool) and val != info["last_val"]:
                            arrow = "🟢 TRUE  [TRIGGERED]" if val else "⚪ FALSE [RELEASED]"
                            print(f"  [{station_key:<8} {ts_str}] {tag_name:<45} --> {arrow}")
                            info["last_val"] = val
                except Exception:
                    for info in tag_info_list:
                        tag_name = info["name"]
                        try:
                            val = await info["node"].read_value()
                            row[tag_name] = int(val) if isinstance(val, bool) else val
                            if isinstance(val, bool) and val != info["last_val"]:
                                arrow = "🟢 TRUE  [TRIGGERED]" if val else "⚪ FALSE [RELEASED]"
                                print(f"  [{station_key:<8} {ts_str}] {tag_name:<45} --> {arrow}")
                                info["last_val"] = val
                        except Exception:
                            row[tag_name] = None

                records.append(row)
                await asyncio.sleep(interval)

    except Exception as e:
        print(f"  [{station_key:<8}] ✗ Error connecting to {url}: {e}")


async def log_switches_orchestrator(target_stations: list, label: str, duration: int, interval: float):
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(DATA_DIR, exist_ok=True)

    print(f"\n{'═'*75}")
    print(f"  FESTO CP FACTORY — MULTI-STATION PLC LIMIT SWITCH LOGGER")
    print(f"{'═'*75}")
    print(f"  Target Stations  : {', '.join(target_stations)}")
    print(f"  Operating Label  : {label}")
    print(f"  Sample Rate      : Every {interval}s")
    print(f"  Duration Limit   : {'Continuous (Press Ctrl+C to stop)' if duration <= 0 else f'{duration} seconds ({duration/60:.1f} mins)'}")
    print(f"  Destination Dir  : {DATA_DIR}")
    print(f"{'═'*75}\n")

    stop_event = asyncio.Event()
    station_records = {st: [] for st in target_stations}
    tasks = []

    for st_key in target_stations:
        tasks.append(asyncio.create_task(
            log_single_plc_task(st_key, label, interval, station_records[st_key], stop_event)
        ))

    start_time = datetime.datetime.now()

    try:
        if duration > 0:
            while (datetime.datetime.now() - start_time).total_seconds() < duration:
                await asyncio.sleep(1.0)
        else:
            while True:
                await asyncio.sleep(1.0)

    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n\n[USER STOPPED] Finalizing switch recordings and saving CSV files ...")
    finally:
        stop_event.set()
        await asyncio.gather(*tasks, return_exceptions=True)

    # ── Save CSVs ─────────────────────────────────────────────────────────────
    print(f"\n{'═'*75}")
    print(f"  SWITCH DATASET EXPORT SUMMARY")
    print(f"{'═'*75}")

    all_dfs = []
    for st_key, recs in station_records.items():
        if not recs:
            print(f"  [WARN] {st_key:<10} : 0 samples captured.")
            continue

        df = pd.DataFrame(recs)
        filename = f"PLC_SWITCHES_{st_key}_{label}_{timestamp_str}.csv"
        filepath = os.path.join(DATA_DIR, filename)
        df.to_csv(filepath, index=False)
        all_dfs.append(df)
        print(f"  ✓ {st_key:<10} : {len(df):>5} samples ({df.shape[1]-3} switch tags) → {filename}")

    if len(all_dfs) > 1:
        merged_df = pd.concat(all_dfs, ignore_index=True)
        merged_filename = f"PLC_SWITCHES_ALL_STATIONS_{label}_{timestamp_str}.csv"
        merged_path = os.path.join(DATA_DIR, merged_filename)
        merged_df.to_csv(merged_path, index=False)
        print(f"  ✓ ALL STATIONS : Consolidated master file ({len(merged_df)} rows) → {merged_filename}")

    print(f"\nAll datasets saved to: {DATA_DIR}\n")


def main():
    parser = argparse.ArgumentParser(description="Live PLC Limit Switch & Digital I/O Extractor for All Stations")
    parser.add_argument(
        "--station",
        type=str,
        default="ALL",
        choices=["ALL", "ASRS", "RASS", "MAGAZINE", "MPRESS"],
        help="Target station PLC (or ALL for all 4 stations simultaneously, default: ALL)",
    )
    parser.add_argument(
        "--label",
        type=str,
        default="LIMIT_SWITCH_TEST",
        help="Operating condition label (default: LIMIT_SWITCH_TEST)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=0,
        help="Duration in seconds (0 = run until Ctrl+C, default: 0)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.2,
        help="Sampling rate in seconds (default: 0.2s for high-speed switch capture)",
    )

    args = parser.parse_args()

    if args.station == "ALL":
        target_stations = ["ASRS", "RASS", "MAGAZINE", "MPRESS"]
    else:
        target_stations = [args.station]

    asyncio.run(log_switches_orchestrator(target_stations, args.label, args.duration, args.interval))


if __name__ == "__main__":
    main()
