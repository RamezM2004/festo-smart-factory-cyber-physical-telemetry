"""
discover_all.py
----------------
Probes EVERY IP address found in the Festo Network Numbering Plan
(230829_NetworkNumberingPlan_1692418.xlsm.pdf) plus known Energy/IoT gateways.

Saves everything into ONE single timestamped text file + a nodes_cache.json
for automatic use by run_multi_logger.py.

Key Resilience Features:
1. Fast-filtering: Skips standard OPC UA server diagnostic folders (Server, Aliases, etc.)
2. Safe Tag Reads: Each tag read has a 2-second individual timeout and catches all exceptions/cancellations.
3. Total Isolation: If a PLC disconnects or errors, it records the error and smoothly moves to the next station.

Usage:
    python discover_all.py
    python discover_all.py --timeout 10
"""

import asyncio
import argparse
import json
import os
import sys
from datetime import datetime, timezone

try:
    from asyncua import Client
except ImportError:
    print("[ERROR] asyncua not installed.")
    sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════
# COMPLETE IP MAP — every address from the Festo Network Numbering Plan
# plus known Energy/IoT gateway addresses.
# ══════════════════════════════════════════════════════════════════════════════

ALL_ENDPOINTS = [
    # ── GJU Confirmed Energy/IoT Gateways (CPX-E) ─────────────────────────────
    {"ip": "172.21.0.60",  "name": "Central_Energy_Header",      "type": "Festo CPX-E_Energy",    "gju": True,  "opcua": True},
    {"ip": "172.21.3.60",  "name": "Station3_RASS_Energy",       "type": "Festo CPX-E_EMB_RASS",  "gju": True,  "opcua": True},
    {"ip": "172.21.5.60",  "name": "Station5_Mpress_Energy",     "type": "Festo CPX-E_EMB_MPRESS","gju": True,  "opcua": True},

    # ── GJU Production PLCs (Siemens S7-1512SP, OPC UA on port 4840) ──────────
    {"ip": "172.21.0.90",  "name": "MES_Server",                 "type": "Festo MES4 PC",         "gju": True,  "opcua": True},
    {"ip": "172.21.1.1",   "name": "Station1_ASRS_PLC",          "type": "S7-1512SP (plcasrs32)", "gju": True,  "opcua": True},
    {"ip": "172.21.2.1",   "name": "Station2_Linear_PLC",        "type": "S7-1512SP (plcidrill)", "gju": True,  "opcua": True},
    {"ip": "172.21.3.1",   "name": "Station3_RASS_PLC",          "type": "S7-1512SP (plcrass)",   "gju": True,  "opcua": True},
    {"ip": "172.21.4.1",   "name": "Station4_Magazine_PLC",      "type": "S7-1512SP (plccam)",    "gju": True,  "opcua": True},
    {"ip": "172.21.5.1",   "name": "Station5_Mpress_PLC",        "type": "S7-1512SP (plcpick)",   "gju": True,  "opcua": True},

    # ── Festo Template Stations (NOT installed at GJU — probe anyway) ─────────
    {"ip": "172.21.6.1",   "name": "Template_Sta6_MagBack_PLC",  "type": "S7-1512SP (plcmagback)","gju": False, "opcua": True},
    {"ip": "172.21.7.1",   "name": "Template_Sta7_Mpress_PLC",   "type": "S7-1512SP (plcmpress)", "gju": False, "opcua": True},
    {"ip": "172.21.8.1",   "name": "Template_Sta8_Label_PLC",    "type": "S7-1512SP (plclabel)",  "gju": False, "opcua": True},
    {"ip": "172.21.9.1",   "name": "Template_Sta9_ManWork_PLC",  "type": "S7-1512SP (plcman)",    "gju": False, "opcua": True},
    {"ip": "172.21.10.1",  "name": "Template_Sta10_Cobot_PLC",   "type": "S7-1512SP (plccobot)",  "gju": False, "opcua": True},

    # ── Application Module PLCs (CECC co-processors) ─────────────────────────
    {"ip": "172.21.2.2",   "name": "Station2_iDrill_AppPLC",     "type": "CECC (plcappidrill)",   "gju": True,  "opcua": True},
    {"ip": "172.21.5.2",   "name": "Station5_Pick_AppPLC",       "type": "CECC (plcappipick)",    "gju": True,  "opcua": True},

    # ── Possible energy gateways for other stations ──────────────────────────
    {"ip": "172.21.1.60",  "name": "Station1_ASRS_Energy?",      "type": "CPX-E? (unconfirmed)",  "gju": False, "opcua": True},
    {"ip": "172.21.2.60",  "name": "Station2_Linear_Energy?",    "type": "CPX-E? (unconfirmed)",  "gju": False, "opcua": True},
    {"ip": "172.21.4.60",  "name": "Station4_Magazine_Energy?",  "type": "CPX-E? (unconfirmed)",  "gju": False, "opcua": True},
    {"ip": "172.21.6.60",  "name": "Template_Sta6_Energy?",      "type": "CPX-E? (unconfirmed)",  "gju": False, "opcua": True},
    {"ip": "172.21.7.60",  "name": "Template_Sta7_Energy?",      "type": "CPX-E? (unconfirmed)",  "gju": False, "opcua": True},

    # ── Non-OPC UA Devices (Listed for completeness) ─────────────────────────
    {"ip": "172.21.1.10",  "name": "Station1_ASRS_HMI",          "type": "TP 700 (hmiasrs32)",    "gju": True,  "opcua": False},
    {"ip": "172.21.2.10",  "name": "Station2_Linear_HMI",        "type": "TP 700 (hmiidrill)",    "gju": True,  "opcua": False},
    {"ip": "172.21.3.10",  "name": "Station3_RASS_HMI",          "type": "TP 700 (hmirass)",      "gju": True,  "opcua": False},
    {"ip": "172.21.4.10",  "name": "Station4_Magazine_HMI",      "type": "TP 700 (hmicam)",       "gju": True,  "opcua": False},
    {"ip": "172.21.5.10",  "name": "Station5_Mpress_HMI",        "type": "TP 700 (hmipick)",      "gju": True,  "opcua": False},
    {"ip": "172.21.1.20",  "name": "Station1_ASRS_RFID",         "type": "Turck RFID",            "gju": True,  "opcua": False},
    {"ip": "172.21.2.20",  "name": "Station2_Linear_RFID",       "type": "Turck RFID",            "gju": True,  "opcua": False},
    {"ip": "172.21.3.20",  "name": "Station3_RASS_RFID_Conv",    "type": "Turck RFID",            "gju": True,  "opcua": False},
    {"ip": "172.21.3.21",  "name": "Station3_RASS_RFID_Box",     "type": "Turck RFID",            "gju": True,  "opcua": False},
    {"ip": "172.21.4.20",  "name": "Station4_Magazine_RFID",     "type": "Turck RFID",            "gju": True,  "opcua": False},
    {"ip": "172.21.5.20",  "name": "Station5_Mpress_RFID",       "type": "Turck RFID",            "gju": True,  "opcua": False},
    {"ip": "172.21.1.30",  "name": "Station1_ASRS_Motor_X",      "type": "CMMP-AS (X axis)",      "gju": True,  "opcua": False},
    {"ip": "172.21.1.31",  "name": "Station1_ASRS_Motor_Z",      "type": "CMMP-AS (Z axis)",      "gju": True,  "opcua": False},
    {"ip": "172.21.3.41",  "name": "Station3_RASS_Robot",         "type": "Mitsubishi RV-4FL",     "gju": True,  "opcua": False},
    {"ip": "172.21.3.50",  "name": "Station3_RASS_Camera",        "type": "Sensopart Visor",       "gju": True,  "opcua": False},
    {"ip": "172.21.4.50",  "name": "Station4_Cam_Inspection",     "type": "Sensopart Visor",       "gju": True,  "opcua": False},
    {"ip": "172.21.11.90", "name": "Template_ManualStorage_PC",   "type": "Tablet PC",             "gju": False, "opcua": False},
    {"ip": "172.21.12.90", "name": "Template_Robotino_PC",        "type": "Robotino PC",           "gju": False, "opcua": False},
]

# Folders to skip so we don't waste time scanning internal OPC UA server diagnostics
SKIP_FOLDERS = {
    "Server", "ServerCapabilities", "ServerDiagnostics", "Aliases",
    "HistoricalDataConfiguration", "Namespaces", "OPCBinarySchema_TypeSystem"
}


async def safe_read(coro, timeout_sec=2.0):
    """Executes an asyncua read with an isolated timeout, absorbing any cancellation."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_sec)
    except BaseException:
        return None


async def browse_recursive(node, out, depth=0, max_depth=8, found_tags=None, path=""):
    if found_tags is None:
        found_tags = {}
    if depth > max_depth:
        return found_tags

    try:
        children = await safe_read(node.get_children(), timeout_sec=5.0)
        if not children:
            return found_tags

        for child in children:
            try:
                display_name_obj = await safe_read(child.read_display_name(), timeout_sec=2.0)
                name = display_name_obj.Text if display_name_obj else "Unknown"

                # Skip standard OPC UA system folders to browse 10x faster
                if depth == 0 and name in SKIP_FOLDERS:
                    continue

                node_id = child.nodeid.to_string()
                child_path = f"{path}/{name}" if path else name

                node_class_val = await safe_read(child.read_node_class(), timeout_sec=2.0)
                if node_class_val is None:
                    continue

                # NodeClass.Variable = 2
                if int(node_class_val) == 2:
                    val = await safe_read(child.read_value(), timeout_sec=2.0)
                    found_tags[node_id] = {
                        "name": name,
                        "node_id": node_id,
                        "val": val,
                        "path": child_path,
                        "type": type(val).__name__ if val is not None else "Unknown"
                    }
                    indent = "  " * depth
                    out.append(f"{indent}├── [TAG] {name:35s} | {node_id:<52s} | {repr(val)}")
                else:
                    indent = "  " * depth
                    out.append(f"{indent}├── 📁 [{name}] (NodeId: {node_id})")
                    await browse_recursive(child, out, depth + 1, max_depth, found_tags, child_path)
            except BaseException:
                pass
    except BaseException:
        pass

    return found_tags


async def probe_opcua(ep: dict, timeout: int):
    """Probe a single OPC UA endpoint safely. Never throws or halts the loop."""
    ip   = ep["ip"]
    name = ep["name"]
    url  = f"opc.tcp://{ip}:4840"
    out  = []
    tags = {}
    status = "UNREACHABLE"
    error_msg = ""

    def w(text=""):
        out.append(text)

    w("=" * 85)
    w(f"  SERVER : {name}")
    w(f"  TYPE   : {ep['type']}")
    w(f"  URL    : {url}")
    w(f"  GJU    : {'YES — installed at GJU' if ep['gju'] else 'NO — Festo template only (probe to check)'}")
    w(f"  PROBED : {datetime.now(timezone.utc).isoformat()}")
    w("=" * 85)
    w()

    client = None
    try:
        client = Client(url=url, timeout=timeout)
        # Wrap connection in wait_for
        await asyncio.wait_for(client.connect(), timeout=timeout)
        w("  ✓ CONNECTED SUCCESSFULLY!")
        w()

        # Try CODESYS GVL shortcut (Festo energy gateways)
        start_node = None
        mode = "OBJECTS"
        try:
            gvl = client.get_node('ns=4;s=|var|CPX-E-CEC-C1.Application.GVL')
            kids = await safe_read(gvl.get_children(), timeout_sec=2.0)
            if kids:
                start_node = gvl
                mode = "CODESYS_GVL"
                w("  Mode: CODESYS GVL (Festo CPX-E energy gateway)")
        except BaseException:
            pass

        if start_node is None:
            start_node = client.get_objects_node()
            w("  Mode: Full Objects tree (Siemens S7-1500 or other)")

        w()
        w("─" * 85)
        w("  ADDRESS SPACE TREE")
        w("─" * 85)
        w()

        tags = await browse_recursive(start_node, out, depth=0, max_depth=8)

        bool_tags  = {k: v for k, v in tags.items() if isinstance(v["val"], bool)}
        float_tags = {k: v for k, v in tags.items()
                      if isinstance(v["val"], (int, float)) and not isinstance(v["val"], bool)}
        ext_tags   = {k: v for k, v in tags.items()
                      if not isinstance(v["val"], (int, float, bool, str)) and v["val"] is not None}

        w()
        w("─" * 85)
        w(f"  SUMMARY — {name} ({ip})")
        w("─" * 85)
        w(f"  Total readable tags     : {len(tags)}")
        w(f"  Boolean  (digital I/O)  : {len(bool_tags)}  ← limit switches, solenoids")
        w(f"  Numeric  (float/int)    : {len(float_tags)}  ← sensors, counters")
        w(f"  ExtensionObject (struct): {len(ext_tags)}  ← Festo PAC3200/SFAH/SPAU structs")
        w()

        if bool_tags:
            w(f"  BOOLEAN TAGS ({len(bool_tags)})  —  TRUE = currently ACTIVE / ENERGIZED")
            w()
            for nid, t in sorted(bool_tags.items(), key=lambda x: x[1]["name"]):
                state = "TRUE  ← ACTIVE" if t["val"] else "false"
                w(f"    {t['name']:35s} | {nid:<55s} | {state}")
            w()

        if float_tags:
            w(f"  NUMERIC TAGS ({len(float_tags)})")
            w()
            for nid, t in sorted(float_tags.items(), key=lambda x: x[1]["name"]):
                w(f"    {t['name']:35s} | {nid:<55s} | {t['val']}")
            w()

        if ext_tags:
            w(f"  EXTENSION OBJECT TAGS ({len(ext_tags)})")
            w()
            for nid, t in sorted(ext_tags.items(), key=lambda x: x[1]["name"]):
                w(f"    {t['name']:35s} | {nid}")
            w()

        # Python copy-paste block
        if bool_tags:
            w("  PYTHON BOOL_TAGS (copy into run_multi_logger.py)")
            w()
            w(f'  # {name} ({ip})')
            w(f'  "{ip}": [')
            for nid, t in sorted(bool_tags.items(), key=lambda x: x[1]["name"]):
                clean = t["name"].lower().replace('"','').replace(' ','_').replace('-','_')
                w(f'      ("{clean}", \'{nid}\'),  # {t["name"]}  current={t["val"]}')
            w("  ],")
            w()

        status = "OK"

    except BaseException as e:
        error_msg = str(e) if str(e) else type(e).__name__
        w(f"  ✗ UNREACHABLE / ERROR — {error_msg}")
        status = "UNREACHABLE"
    finally:
        if client:
            try:
                await client.disconnect()
            except BaseException:
                pass

    w()
    return {
        "name": name, "ip": ip, "type": ep["type"],
        "gju": ep["gju"], "status": status,
        "tags": len(tags),
        "bool_tags": len([v for v in tags.values() if isinstance(v["val"], bool)]),
        "error": error_msg, "lines": out, "tag_data": tags
    }


async def main():
    parser = argparse.ArgumentParser(
        description="Full network OPC UA discovery — probes every IP from Festo Network Plan."
    )
    parser.add_argument("--outdir",  type=str, default="discovery_reports")
    parser.add_argument("--timeout", type=int, default=8,
                        help="Connection timeout per server in seconds (default: 8)")
    parser.add_argument("--opcua-only", action="store_true",
                        help="Only probe likely OPC UA endpoints (skip HMIs/RFIDs/cameras)")
    args = parser.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(args.outdir, exist_ok=True)
    out_path   = os.path.join(args.outdir, f"CP_FACTORY_FULL_NETWORK_{ts}.txt")
    cache_path = os.path.join(args.outdir, "nodes_cache.json")

    # Decide which endpoints to probe
    if args.opcua_only:
        endpoints = [ep for ep in ALL_ENDPOINTS if ep["opcua"]]
    else:
        endpoints = ALL_ENDPOINTS

    opcua_eps    = [ep for ep in endpoints if ep["opcua"]]
    nonopcua_eps = [ep for ep in endpoints if not ep["opcua"]]

    all_lines = []
    def w(text=""):
        all_lines.append(text)
        print(text)

    w("=" * 85)
    w("  FESTO CP FACTORY — COMPLETE NETWORK OPC UA DISCOVERY")
    w(f"  Source    : Festo Network Numbering Plan + GJU Energy Gateways")
    w(f"  Started   : {datetime.now(timezone.utc).isoformat()}")
    w(f"  OPC UA    : {len(opcua_eps)} endpoints to probe")
    w(f"  Non-OPC UA: {len(nonopcua_eps)} devices listed (not probed)")
    w(f"  Timeout   : {args.timeout}s per connection")
    w(f"  Output    : {out_path}")
    w("=" * 85)
    w()

    # ── Probe all OPC UA endpoints ─────────────────────────────────────────
    results = []
    for i, ep in enumerate(opcua_eps, 1):
        gju_tag = "[GJU]" if ep["gju"] else "[TPL]"
        print(f"\n[{i}/{len(opcua_eps)}] {gju_tag} Probing {ep['name']} ({ep['ip']}) ...")
        result = await probe_opcua(ep, args.timeout)
        results.append(result)
        all_lines.extend(result["lines"])
        icon = "✓" if result["status"] == "OK" else "✗"
        print(f"         {icon} {result['status']} — {result['tags']} tags ({result['bool_tags']} boolean)")

    # ── Non-OPC UA devices section ─────────────────────────────────────────
    all_lines.append("=" * 85)
    all_lines.append("  NON-OPC UA DEVICES (from Network Plan — not probed)")
    all_lines.append("=" * 85)
    all_lines.append(f"  {'Device':<40} {'IP':<18} {'Type':<25} GJU?")
    all_lines.append("  " + "─" * 82)
    for ep in nonopcua_eps:
        gju = "YES" if ep["gju"] else "no"
        all_lines.append(f"  {ep['name']:<40} {ep['ip']:<18} {ep['type']:<25} {gju}")
    all_lines.append("")

    # ── Master summary ─────────────────────────────────────────────────────
    all_lines.append("=" * 85)
    all_lines.append("  NETWORK MASTER SUMMARY")
    all_lines.append(f"  Scan completed : {datetime.now(timezone.utc).isoformat()}")
    all_lines.append("=" * 85)
    all_lines.append(f"  {'Server':<40} {'IP':<18} {'GJU':>4} {'Status':<13} {'Tags':>6} {'Bool':>5}  Type")
    all_lines.append("  " + "─" * 90)

    total_tags = 0
    total_bool = 0
    reachable  = 0
    for r in results:
        icon = "✓" if r["status"] == "OK" else "✗"
        gju  = "YES" if r["gju"] else "—"
        all_lines.append(
            f"  {icon} {r['name']:<38} {r['ip']:<18} {gju:>4} {r['status']:<13} "
            f"{r['tags']:>6} {r['bool_tags']:>5}  {r['type']}"
        )
        if r["error"]:
            all_lines.append(f"      Error: {r['error'][:80]}")
        total_tags += r["tags"]
        total_bool += r["bool_tags"]
        if r["status"] == "OK":
            reachable += 1

    all_lines.append("  " + "─" * 90)
    all_lines.append(f"  TOTALS: {reachable}/{len(results)} reachable | {total_tags} tags | {total_bool} boolean")
    all_lines.append("")

    # ── Write the single text file ─────────────────────────────────────────
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(all_lines))

    # ── Write nodes_cache.json (for auto-loading by run_multi_logger.py) ───
    cache = {
        "scan_time": datetime.now(timezone.utc).isoformat(),
        "servers": {}
    }
    for r in results:
        if r["status"] == "OK" and r["tag_data"]:
            bool_list = []
            for nid, t in r["tag_data"].items():
                if isinstance(t["val"], bool):
                    clean = t["name"].lower().replace('"','').replace(' ','_').replace('-','_')
                    bool_list.append({"col_name": clean, "node_id": nid,
                                      "name": t["name"], "path": t["path"]})
            cache["servers"][r["ip"]] = {
                "name": r["name"], "type": r["type"], "gju": r["gju"],
                "total_tags": r["tags"], "bool_tags": len(bool_list),
                "booleans": bool_list
            }
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

    # ── Final console summary ──────────────────────────────────────────────
    print()
    print("=" * 85)
    print("  SCAN COMPLETE")
    print(f"  {'Server':<40} {'IP':<18} {'GJU':>4} {'Status':<13} {'Tags':>6} {'Bool':>5}")
    print("  " + "─" * 82)
    for r in results:
        icon = "✓" if r["status"] == "OK" else "✗"
        gju  = "YES" if r["gju"] else "—"
        print(f"  {icon} {r['name']:<38} {r['ip']:<18} {gju:>4} {r['status']:<13} {r['tags']:>6} {r['bool_tags']:>5}")
    print()
    print(f"  ✓ Full report   → {out_path}")
    print(f"  ✓ Nodes cache   → {cache_path}")
    print("=" * 85)


if __name__ == "__main__":
    asyncio.run(main())
