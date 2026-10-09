"""
plc_opcua_live_logger.py
-------------------------
Directly connects to a Siemens S7-1512SP PLC on the Festo CP Factory network
via OPC UA (port 4840), discovers published tags, and logs live telemetry to CSV.

Usage:
    # 1. Ensure your PC Ethernet adapter is set to static IP (e.g. 172.21.0.150, mask 255.255.192.0)
    # 2. Run:
    python plc_opcua_live_logger.py --ip 172.21.3.1 --station RASS
    python plc_opcua_live_logger.py --ip 172.21.7.1 --station MPRESS

Requirements:
    pip install asyncua pandas
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
    print("[ERROR] 'asyncua' library is not installed.")
    print("        Run: pip install asyncua")
    sys.exit(1)


async def browse_and_log(plc_ip: str, station_name: str, interval: float, output_csv: str):
    url = f"opc.tcp://{plc_ip}:4840"
    print(f"\n{'═'*65}")
    print(f"  Festo CP Factory — Direct PLC OPC UA Live Data Logger")
    print(f"{'═'*65}")
    print(f"  Target PLC       : {station_name} ({url})")
    print(f"  Sample Interval  : {interval} seconds")
    print(f"  Destination CSV  : {output_csv}")
    print(f"{'═'*65}\n")

    print(f"Connecting to {url} ...")
    
    try:
        async with Client(url=url, timeout=5) as client:
            print(f"✓ Connected successfully to {station_name} PLC!")

            # Browse the PLC Root -> Objects -> Server / PLC tags
            root = client.nodes.root
            objects = client.nodes.objects
            
            print("Discovering available PLC nodes ...")
            children = await objects.get_children()
            
            # Find PLC data nodes
            target_nodes = []
            for node in children:
                name = await node.read_display_name()
                # Exclude internal OPC UA server diagnostics
                if name.Text not in ["Server", "Aliases", "ServerCapabilities"]:
                    target_nodes.append((name.Text, node))

            if not target_nodes:
                for n in children:
                    target_nodes.append(((await n.read_display_name()).Text, n))

            print(f"Found {len(target_nodes)} accessible top-level node blocks:")
            for tag_name, _ in target_nodes:
                print(f"  - {tag_name}")

            print(f"\n[RECORDING STARTED] Press Ctrl+C to stop recording and save CSV.\n")
            
            records = []
            start_time = datetime.datetime.now()
            
            try:
                sample_idx = 0
                while True:
                    timestamp_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    row = {
                        "timestamp": timestamp_now,
                        "station": station_name,
                        "plc_ip": plc_ip,
                    }
                    
                    # Read values for discovered nodes
                    for tag_name, node in target_nodes:
                        try:
                            val = await node.read_value()
                            row[tag_name] = val
                        except Exception:
                            row[tag_name] = None
                            
                    records.append(row)
                    sample_idx += 1
                    
                    if sample_idx % 10 == 0:
                        elapsed = (datetime.datetime.now() - start_time).total_seconds()
                        print(f"  [{timestamp_now}] Logged {sample_idx} samples ({elapsed:.1f}s elapsed)")
                        
                    await asyncio.sleep(interval)
                    
            except KeyboardInterrupt:
                print("\n[STOPPED] Stopping recording on user request (Ctrl+C) ...")

            if records:
                df = pd.DataFrame(records)
                os.makedirs(os.path.dirname(os.path.abspath(output_csv)), exist_ok=True)
                df.to_csv(output_csv, index=False)
                print(f"\n✓ Saved {len(df)} samples to: {output_csv}")
            else:
                print("No records logged.")

    except Exception as e:
        print(f"\n[CONNECTION ERROR] Could not connect to PLC at {url}")
        print(f"  Details: {e}")
        print(f"\nTroubleshooting Checklist:")
        print(f"  1. Is your PC connected to the factory Ethernet switch?")
        print(f"  2. Is your PC static IP set to e.g. 172.21.0.150 (Subnet: 255.255.192.0)?")
        print(f"  3. Can you ping {plc_ip} in PowerShell?")


def main():
    parser = argparse.ArgumentParser(description="Live OPC UA Data Logger for Festo CP Factory PLCs")
    parser.add_argument("--ip", type=str, default="172.21.3.1", help="PLC IP address (e.g. 172.21.3.1)")
    parser.add_argument("--station", type=str, default="RASS", help="Station name (e.g. RASS, MPRESS)")
    parser.add_argument("--interval", type=float, default=0.5, help="Sampling interval in seconds (default 0.5s)")
    parser.add_argument("--out", type=str, default=None, help="Output CSV path")

    args = parser.parse_args()

    if args.out is None:
        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        args.out = os.path.join(os.path.dirname(__file__), "data", f"PLC_{args.station}_{timestamp_str}.csv")

    asyncio.run(browse_and_log(args.ip, args.station, args.interval, args.out))


if __name__ == "__main__":
    main()
