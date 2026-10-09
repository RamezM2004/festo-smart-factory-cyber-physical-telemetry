# GJU CP Factory — CORRECTED Full Network Map
# Source: 230829_NetworkNumberingPlan_1692418.xlsm.pdf (Official Festo Configuration)

## KEY DISCOVERY: The GJU line has 13 stations (0-12), NOT 5!

Our previous scripts assumed only 5 stations. The official Festo network plan
reveals the ACTUAL station numbering and IP assignments:

## Complete Station List

| Station # | ID / Name | Application Module | PLC Name | PLC IP | HMI IP | RFID IP | Other Devices |
|---|---|---|---|---|---|---|---|
| 0 | SERVER | MES PC | FESTO-MES-PC | 172.21.0.90 | — | — | MES Server |
| 1 | F-ASRS32-P | High Bay Warehouse | plcasrs32 (S7-1512SP) | 172.21.1.1 | 172.21.1.10 | 172.21.1.20 | X-axis motor 172.21.1.30, Z-axis motor 172.21.1.31 |
| 2 | F-LINEAR-iDRILL | iDrilling | plcidrill (S7-1512SP) | 172.21.2.1 | 172.21.2.10 | 172.21.2.20 | CECC plcappidrill 172.21.2.2 |
| 3 | F-RASS | Robot Assembly | plcrass (S7-1512SP) | 172.21.3.1 | 172.21.3.10 | 172.21.3.20, .21 | Camera 172.21.3.50, Robot 172.21.3.41 |
| 4 | F-LINEAR-CAM | Camera Inspection | plccam (S7-1512SP) | 172.21.4.1 | 172.21.4.10 | 172.21.4.20 | Camera 172.21.4.50 |
| 5 | F-LINEAR-PICK | PickByLight | plcpick (S7-1512SP) | 172.21.5.1 | 172.21.5.10 | 172.21.5.20 | CECC plcappipick 172.21.5.2 |
| 6 | F-LINEAR-MAG | Magazine (Black) | plcmagback (S7-1512SP) | 172.21.6.1 | 172.21.6.10 | 172.21.6.20 | — |
| 7 | F-LINEAR-MPRESS | Muscle Press | plcmpress (S7-1512SP) | 172.21.7.1 | 172.21.7.10 | 172.21.7.20 | — |
| 8 | F-LINEAR-LABEL | Labeling | plclabel (S7-1512SP) | 172.21.8.1 | 172.21.8.10 | 172.21.8.20 | Zebra printer 172.21.8.70 |
| 9 | F-LINEAR-MAN-WORK | Manual Work | plcman (S7-1512SP) | 172.21.9.1 | 172.21.9.10 | 172.21.9.20 | — |
| 10 | F-BYPASS-COBOT | COBOT + Docking | plccobot (S7-1512SP) | 172.21.10.1 | 172.21.10.10 | 172.21.10.20 | UR Robot 172.21.10.40 |
| 11 | F-MSRS20 | Manual Storage | — | — | — | — | Tablet PC 172.21.11.90 |
| 12 | LOG-MR-B | Robotino (boxes) | — | — | — | — | Robotino PC 172.21.12.90 |


## CRITICAL CORRECTIONS TO OUR SCRIPTS

### 1. Muscle Press is Station 7, NOT Station 5!
    - WRONG: 172.21.5.1 → that's the PickByLight station PLC (plcpick)
    - CORRECT: 172.21.7.1 → that's the Muscle Press PLC (plcmpress)
    - This is why discover_nodes.py --ip 172.21.7.1 worked for MPRESS tags!

### 2. Magazine is Station 6, NOT Station 4!
    - WRONG: 172.21.4.1 → that's the Camera Inspection PLC (plccam)
    - CORRECT: 172.21.6.1 → that's the Magazine PLC (plcmagback)

### 3. The "linear" station at 172.21.2.1 is actually iDrill, not a bare conveyor

### 4. Energy Gateway IPs (172.21.X.60) are NOT listed in this document
    - The network plan only shows Production network devices
    - Energy gateways live on a separate Energy/IoT VLAN: 172.21.200.0/24
    - The .60 addresses (172.21.3.60, 172.21.5.60, 172.21.0.60) are likely on a bridged segment


## Network VLANs

| VLAN | CIDR | Purpose |
|---|---|---|
| Production | 172.21.0.0/18 | All PLCs, HMIs, RFIDs, robots |
| Energy/IoT | 172.21.200.0/24 | Energy monitoring gateways (CPX-E) |
| NetManagement | 172.21.210.0/24 | Switch/router management |
| Transfer | 172.21.215.0/24 | Data transfer |
| DMZ | 172.21.220.0/24 | External-facing services |


## IP Addressing Pattern (Production Network)

172.21.<station#>.1    →  PLC (Siemens S7-1512SP)
172.21.<station#>.2    →  Application Module PLC (CECC, if present)
172.21.<station#>.10   →  HMI Touch Panel (TP 700 Comfort)
172.21.<station#>.20   →  RFID Gateway (Turck)
172.21.<station#>.21   →  Second RFID Gateway (if present, e.g. RASS)
172.21.<station#>.30+  →  Motor controllers / servo drives
172.21.<station#>.40+  →  Robot controllers
172.21.<station#>.50   →  Vision cameras
172.21.<station#>.70   →  Printers / peripherals
172.21.<station#>.90   →  PCs / tablets


## All OPC UA Capable PLCs (S7-1512SP, port 4840)

172.21.1.1   plcasrs32   Station 1  ASRS Warehouse
172.21.2.1   plcidrill   Station 2  iDrilling
172.21.3.1   plcrass     Station 3  RASS Robot Assembly
172.21.4.1   plccam      Station 4  Camera Inspection
172.21.5.1   plcpick     Station 5  PickByLight
172.21.6.1   plcmagback  Station 6  Magazine Feeder
172.21.7.1   plcmpress   Station 7  Muscle Press
172.21.8.1   plclabel    Station 8  Labeling
172.21.9.1   plcman      Station 9  Manual Workstation
172.21.10.1  plccobot    Station 10 COBOT with Docking
