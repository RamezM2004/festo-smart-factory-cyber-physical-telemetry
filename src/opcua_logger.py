"""
opcua_logger.py
---------------
Automated Python OPC UA Logger for Festo CP Factory PLCs.
Connects to any station's Siemens S7-1500 PLC via OPC UA, reads digital limit
switches and analog sensor tags live, and logs them to a CSV file.

Festo CP Factory Default Station IP Addresses:
    Station 1 (Warehouse AS/RS): opc.tcp://172.21.1.1:4840
    Station 2 (Linear Conveyor): opc.tcp://172.21.2.1:4840
    Station 3 (RASS Robot):      opc.tcp://172.21.3.1:4840
    Station 4 (Magazine):        opc.tcp://172.21.4.1:4840
    Station 5 (Muscle Press):    opc.tcp://172.21.5.1:4840

Usage:
    python opcua_logger.py --ip 172.21.3.1 --duration 180 --output opcua_rass_log.csv
"""

import sys
import time
import argparse
import pandas as pd
from datetime import datetime

try:
    from opcua import Client, ua
except ImportError:
    print("[ERROR] 'opcua' library not installed. Install with: pip install opcua")
    sys.exit(1)


def log_opcua_station(plc_ip: str, duration_sec: int, output_csv: str, poll_interval: float = 1.0):
    url = f"opc.tcp://{plc_ip}:4840"
    print(f"==================================================")
    print(f"  Festo CP Factory OPC UA Python Logger")
    print(f"  Connecting to PLC at: {url}")
    print(f"==================================================")

    client = Client(url)
    try:
        client.connect()
        print("  ✓ Connected successfully to OPC UA Server!")

        # Root node / Objects folder
        root = client.get_root_node()
        objects = client.get_objects_node()

        print("\n  Browsing PLC Data Blocks & Tags ...")
        
        # Look for Festo Application DB or Global DBs
        # Common OPC UA Tag Node IDs on Festo S7-1500 PLCs:
        # ns=3;s="DB_Station"."xStopperExtended"
        # ns=3;s="DB_Station"."xPalletPresent"
        # ns=3;s="DB_Sensors"."rPressure"
        
        # Collect nodes to log
        nodes_to_log = {}
        
        # Example tag definitions (NodeID strings)
        sample_tags = {
            "Stopper_Extended": 'ns=3;s="DB_Station"."xStopperExtended"',
            "Stopper_Retracted": 'ns=3;s="DB_Station"."xStopperRetracted"',
            "Pallet_Present": 'ns=3;s="DB_Station"."xPalletPresent"',
            "Automatic_Mode": 'ns=3;s="DB_Station"."xAutoMode"',
            "Busy_State": 'ns=3;s="DB_Station"."xBusy"',
            "Pressure_Bar": 'ns=3;s="DB_Sensors"."rPressure"',
            "Flow_Lmin": 'ns=3;s="DB_Sensors"."rFlow"',
        }

        # Try to resolve nodes
        valid_nodes = {}
        for tag_name, node_id_str in sample_tags.items():
            try:
                node = client.get_node(node_id_str)
                # Try reading value
                val = node.get_value()
                valid_nodes[tag_name] = node
                print(f"   [TAG FOUND] {tag_name:20s} = {val}")
            except Exception:
                pass

        if not valid_nodes:
            print("\n  [NOTE] Standard tag names not pre-resolved. Browsing root Objects folder instead ...")
            # Fallback browse
            children = objects.get_children()
            for child in children[:15]:
                try:
                    name = child.get_display_name().Text
                    print(f"    - {name} (NodeId: {child.nodeid})")
                except Exception:
                    pass

        print(f"\n  Starting logging for {duration_sec} seconds (Interval: {poll_interval}s) ...")
        print(f"  Press Ctrl+C to stop early.\n")

        records = []
        start_time = time.time()

        while (time.time() - start_time) < duration_sec:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row = {"Timestamp": now_str}

            if valid_nodes:
                for tag_name, node in valid_nodes.items():
                    try:
                        row[tag_name] = node.get_value()
                    except Exception:
                        row[tag_name] = None
            else:
                # If browsing fallback
                row["Status"] = "Connected_Logging"

            records.append(row)
            elapsed = int(time.time() - start_time)
            print(f"\r  Logged {len(records)} rows ({elapsed}/{duration_sec}s) ...", end="", flush=True)

            time.sleep(poll_interval)

        print(f"\n\n  ✓ Logging complete. Total rows: {len(records)}")

        df = pd.DataFrame(records)
        df.to_csv(output_csv, index=False)
        print(f"  ✓ Saved to: {output_csv}")

    except Exception as e:
        print(f"\n[ERROR] Connection or logging failed: {e}")
        print("  Make sure your laptop is connected to the 172.21.x.x lab network.")
    finally:
        try:
            client.disconnect()
            print("  ✓ Disconnected cleanly from OPC UA Server.")
        except Exception:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Python OPC UA Logger for Festo CP Factory")
    parser.add_argument("--ip", type=str, default="172.21.3.1", help="PLC IP Address (default: 172.21.3.1 for RASS)")
    parser.add_argument("--duration", type=int, default=180, help="Logging duration in seconds (default: 180s)")
    parser.add_argument("--output", type=str, default="opcua_station_log.csv", help="Output CSV filename")
    parser.add_argument("--interval", type=float, default=1.0, help="Poll interval in seconds (default: 1.0s)")

    args = parser.parse_args()
    log_opcua_station(args.ip, args.duration, args.output, args.interval)
