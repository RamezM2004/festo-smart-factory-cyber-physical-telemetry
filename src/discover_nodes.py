"""
discover_nodes.py
------------------
Automated OPC UA Tag Discovery Tool for Festo CPX-E-CEC Controllers & Siemens PLCs.

ALL OUTPUT is saved to a timestamped .txt file AND printed to the terminal simultaneously.
This prevents VS Code terminal buffer overflow on large address spaces (600+ tags).

Tries the CODESYS Global Variable List shortcut first:
    ns=4;s=|var|CPX-E-CEC-C1.Application.GVL
If that folder doesn't exist on the target server (e.g. a Siemens S7-1500
station PLC, which uses Objects -> DeviceSet -> plcXXX -> Inputs /
DataBlocksGlobal / DataBlocksInstance instead), it falls back to browsing
the full address space from the generic Objects node - so the same script
works against both the CPX-E energy gateways AND the station PLCs where
limit switches and other digital I/O actually live.

Output files (auto-created in discovery_reports/ folder):
    discovery_172_21_3_60_<timestamp>.txt   ← full tree + summary
    discovery_172_21_3_60_<timestamp>_booleans.txt  ← boolean tags only (limit switches)
    discovery_172_21_3_60_<timestamp>_nodes.py      ← ready-to-paste NODES dict

Usage:
    python discover_nodes.py --ip 172.21.3.60   # RASS CPX-E energy gateway (pressure/flow/power)
    python discover_nodes.py --ip 172.21.3.1    # RASS station PLC (limit switches, digital I/O)
    python discover_nodes.py --ip 172.21.1.1    # ASRS station PLC
    python discover_nodes.py --ip 172.21.2.1    # Linear Conveyor PLC
    python discover_nodes.py --ip 172.21.4.1    # Magazine Feeder PLC
    python discover_nodes.py --ip 172.21.5.1    # Muscle Press PLC
    python discover_nodes.py --ip 172.21.5.60   # Muscle Press energy gateway
    python discover_nodes.py --ip 172.21.0.60   # Central Line energy header
"""

import sys
import asyncio
import argparse
import os
from datetime import datetime, timezone


try:
    from asyncua import Client
except ImportError:
    print("[ERROR] 'asyncua' library not installed. Install with: pip install asyncua")
    sys.exit(1)


class DualWriter:
    """Writes output to both stdout and a file simultaneously."""
    def __init__(self, filepath):
        self._file = open(filepath, "w", encoding="utf-8")
        self._stdout = sys.stdout

    def write(self, text):
        self._stdout.write(text)
        self._stdout.flush()
        self._file.write(text)
        self._file.flush()

    def flush(self):
        self._stdout.flush()
        self._file.flush()

    def close(self):
        self._file.close()


def log(writer, text=""):
    writer.write(text + "\n")


async def browse_recursive(node, writer, depth=0, max_depth=8, found_tags=None, path=""):
    if found_tags is None:
        found_tags = {}

    if depth > max_depth:
        return found_tags

    try:
        children = await node.get_children()
        for child in children:
            try:
                node_class = await child.read_node_class()
                name = (await child.read_display_name()).Text
                node_id = child.nodeid.to_string()
                child_path = f"{path}/{name}" if path else name

                # NodeClass.Variable = 2 in OPC UA standard
                if int(node_class) == 2:
                    try:
                        val = await child.read_value()
                        found_tags[node_id] = {
                            "name": name,
                            "node_id": node_id,
                            "val": val,
                            "path": child_path,
                            "type": type(val).__name__
                        }
                        indent = "  " * depth
                        log(writer, f"{indent}├── [TAG] {name:35s} | {node_id:<50s} | {repr(val)}")
                    except Exception:
                        pass
                else:
                    indent = "  " * depth
                    log(writer, f"{indent}├── 📁 [{name}] (NodeId: {node_id})")
                    await browse_recursive(child, writer, depth + 1, max_depth, found_tags, child_path)
            except Exception:
                pass
    except Exception:
        pass

    return found_tags


async def get_start_node(client, writer):
    """Try the CODESYS GVL shortcut; fall back to generic Objects-node browsing."""
    try:
        gvl_node = client.get_node('ns=4;s=|var|CPX-E-CEC-C1.Application.GVL')
        children = await gvl_node.get_children()
        if children:
            log(writer, "  ✓ Found CODESYS GVL Folder — browsing GVL variables (Festo CPX-E gateway)\n")
            return gvl_node, "CODESYS_GVL"
    except Exception:
        pass

    log(writer, "  → No CODESYS GVL folder found — browsing full address space from Objects root")
    log(writer, "    (Expected for Siemens S7-1500 PLCs: look for Inputs / DataBlocksGlobal folders)")
    log(writer, "    Limit switches live under  ns=3;s=\"xG1_BG..\"  and  ns=3;s=\"xG1_MB..\"\n")
    return client.get_objects_node(), "SIEMENS_OBJECTS"


def write_boolean_report(writer_path, bool_tags, url):
    """Write a standalone file with only boolean (limit switch / digital I/O) tags."""
    with open(writer_path, "w", encoding="utf-8") as f:
        f.write(f"BOOLEAN / DIGITAL I/O TAG REPORT\n")
        f.write(f"Server: {url}\n")
        f.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"Total boolean tags found: {len(bool_tags)}\n")
        f.write("=" * 80 + "\n\n")

        # Group by path prefix
        by_group = {}
        for nid, t in bool_tags.items():
            group = t["path"].split("/")[0] if "/" in t["path"] else "root"
            by_group.setdefault(group, []).append(t)

        for group, tags in sorted(by_group.items()):
            f.write(f"\n── {group} ({len(tags)} tags) ──\n")
            for t in sorted(tags, key=lambda x: x["path"]):
                current = "TRUE  ← ACTIVE" if t["val"] else "false"
                f.write(f"  {t['name']:35s} | {t['node_id']:<55s} | {current}\n")


def write_nodes_dict(writer_path, all_tags, bool_tags, url):
    """Write a ready-to-paste Python NODES dict for run_logger.py / run_multi_logger.py."""
    with open(writer_path, "w", encoding="utf-8") as f:
        f.write(f"# Auto-generated OPC UA Node Map\n")
        f.write(f"# Server: {url}\n")
        f.write(f"# Generated: {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"# Total tags: {len(all_tags)}  |  Boolean (digital I/O): {len(bool_tags)}\n")
        f.write("#\n")
        f.write("# Paste this into run_logger.py -> STATION_PLC_TAGS or run_multi_logger.py\n")
        f.write("#\n\n")

        f.write("# ─── BOOLEAN / DIGITAL I/O TAGS (limit switches, solenoids) ─────────────\n")
        f.write("BOOL_TAGS = [\n")
        for nid, t in sorted(bool_tags.items(), key=lambda x: x[1]["name"]):
            clean = t["name"].lower().replace('"', '').replace(" ", "_").replace("-", "_")
            current = t["val"]
            f.write(f'    ("{clean}", \'{t["node_id"]}\'),  '
                    f'# {t["name"]}  |  current: {current}  |  path: {t["path"]}\n')
        f.write("]\n\n")

        f.write("# ─── ALL READABLE TAGS ────────────────────────────────────────────────────\n")
        f.write("ALL_TAGS = {\n")
        for nid, t in sorted(all_tags.items(), key=lambda x: x[1]["name"]):
            clean = t["name"].lower().replace('"', '').replace(" ", "_").replace("-", "_")
            f.write(f'    "{clean}": \'{t["node_id"]}\',  '
                    f'# type={t["type"]}  val={repr(t["val"])}  path={t["path"]}\n')
        f.write("}\n")


async def main():
    parser = argparse.ArgumentParser(
        description="OPC UA Node Discovery — saves full output to file (no VS Code overflow)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python discover_nodes.py --ip 172.21.3.60    # RASS energy gateway
  python discover_nodes.py --ip 172.21.3.1     # RASS PLC (limit switches)
  python discover_nodes.py --ip 172.21.5.60    # Mpress energy gateway
  python discover_nodes.py --ip 172.21.5.1     # Mpress PLC
  python discover_nodes.py --ip 172.21.1.1     # ASRS PLC
  python discover_nodes.py --ip 172.21.2.1     # Linear Conveyor PLC
  python discover_nodes.py --ip 172.21.4.1     # Magazine Feeder PLC
  python discover_nodes.py --ip 172.21.0.60    # Central energy header
        """
    )
    parser.add_argument("--ip",        type=str, default="172.21.3.60", help="Target server IP")
    parser.add_argument("--port",      type=int, default=4840,           help="OPC UA port (default: 4840)")
    parser.add_argument("--max-depth", type=int, default=8,              help="Max tree recursion depth")
    parser.add_argument("--outdir",    type=str, default="discovery_reports",
                        help="Directory for saved reports (default: discovery_reports/)")

    args = parser.parse_args()
    url = f"opc.tcp://{args.ip}:{args.port}"

    # ── Create output directory ──────────────────────────────────────────────
    os.makedirs(args.outdir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ip_safe = args.ip.replace(".", "_")
    base = os.path.join(args.outdir, f"discovery_{ip_safe}_{ts}")

    main_log_path    = base + ".txt"
    bool_report_path = base + "_booleans.txt"
    nodes_dict_path  = base + "_nodes.py"

    writer = DualWriter(main_log_path)

    try:
        header = [
            "=" * 80,
            "  FESTO CP FACTORY — OPC UA FULL NODE DISCOVERY",
            f"  Target Server  : {url}",
            f"  Timestamp      : {datetime.now(timezone.utc).isoformat()}",
            f"  Max Depth      : {args.max_depth}",
            f"  Output Files   : {main_log_path}",
            f"                   {bool_report_path}",
            f"                   {nodes_dict_path}",
            "=" * 80,
            "",
        ]
        for line in header:
            log(writer, line)

        async with Client(url=url, timeout=10) as client:
            log(writer, "  ✓ Connected successfully!\n")

            start_node, mode = await get_start_node(client, writer)
            log(writer, f"  Browse mode: {mode}\n")
            log(writer, "─" * 80)
            log(writer, "  FULL ADDRESS SPACE TREE")
            log(writer, "─" * 80 + "\n")

            tags = await browse_recursive(
                start_node, writer, depth=0, max_depth=args.max_depth
            )

            bool_tags = {nid: t for nid, t in tags.items() if isinstance(t["val"], bool)}
            float_tags = {nid: t for nid, t in tags.items()
                          if isinstance(t["val"], (int, float)) and not isinstance(t["val"], bool)}
            ext_tags   = {nid: t for nid, t in tags.items()
                          if not isinstance(t["val"], (int, float, bool, str))}

            # ── Summary ──────────────────────────────────────────────────────
            log(writer, "")
            log(writer, "=" * 80)
            log(writer, f"  DISCOVERY SUMMARY — {url}")
            log(writer, "=" * 80)
            log(writer, f"  Total readable tags  : {len(tags)}")
            log(writer, f"  Boolean (digital I/O): {len(bool_tags)}  ← limit switches, solenoids")
            log(writer, f"  Numeric (float/int)  : {len(float_tags)}  ← sensors, counters")
            log(writer, f"  ExtensionObjects     : {len(ext_tags)}  ← Festo struct sensors (struct decode needed)")
            log(writer, "")

            # ── Boolean tags inline summary ───────────────────────────────────
            if bool_tags:
                log(writer, f"  ── BOOLEAN / DIGITAL I/O TAGS ({len(bool_tags)} tags) ─────────────────")
                log(writer, "     (TRUE = currently ACTIVE/ENERGIZED)")
                log(writer, "")
                for nid, t in sorted(bool_tags.items(), key=lambda x: x[1]["name"]):
                    state = "TRUE  ← ACTIVE" if t["val"] else "false"
                    log(writer, f"     {t['name']:35s} | {nid:<55s} | {state}")
                log(writer)

            # ── Numeric tags inline summary ───────────────────────────────────
            if float_tags:
                log(writer, f"  ── NUMERIC / SENSOR TAGS ({len(float_tags)} tags) ─────────────────────")
                log(writer, "")
                for nid, t in sorted(float_tags.items(), key=lambda x: x[1]["name"]):
                    log(writer, f"     {t['name']:35s} | {nid:<55s} | {t['val']}")
                log(writer, "")

            # ── ExtensionObject tags inline summary ───────────────────────────
            if ext_tags:
                log(writer, f"  ── EXTENSION OBJECT TAGS ({len(ext_tags)} tags) — need load_data_type_definitions()")
                log(writer, "")
                for nid, t in sorted(ext_tags.items(), key=lambda x: x[1]["name"]):
                    log(writer, f"     {t['name']:35s} | {nid}")
                log(writer, "")

            log(writer, "=" * 80)
            log(writer, f"  OUTPUT FILES SAVED:")
            log(writer, f"    Full tree + summary  → {main_log_path}")
            log(writer, f"    Booleans only        → {bool_report_path}")
            log(writer, f"    NODES dict (Python)  → {nodes_dict_path}")
            log(writer, "=" * 80)

        # ── Write the two extra output files ──────────────────────────────────
        write_boolean_report(bool_report_path, bool_tags, url)
        write_nodes_dict(nodes_dict_path, tags, bool_tags, url)

        print(f"\n✓ All discovery data saved to: {os.path.abspath(args.outdir)}/")
        print(f"  → {os.path.basename(main_log_path)}     (full tree)")
        print(f"  → {os.path.basename(bool_report_path)}  (boolean tags only)")
        print(f"  → {os.path.basename(nodes_dict_path)}   (Python NODES dict)")

    except Exception as e:
        log(writer, f"\n[ERROR] Connection failed to {url}: {e}")
        print(f"\n[ERROR] Connection failed to {url}: {e}")

    finally:
        writer.close()


if __name__ == "__main__":
    asyncio.run(main())
