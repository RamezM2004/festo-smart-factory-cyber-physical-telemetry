FESTO CP FACTORY SMART MAINTENANCE

Master OPC UA Node, Sensor Telemetry & Data Label Reference Guide
German Jordanian University (GJU) Smart Factory Laboratory

This reference document provides a complete mapping of network server endpoints, continuous telemetry channels, OPC UA discrete PLC address space tags, and standardized data labels for AI model training on the Festo CP Factory.

1. Network Server Endpoints & Station IP Map

2. Continuous 33-Sensor Telemetry Channels (MES4 / CPX-IOT Stream)

3. OPC UA Station PLC Discrete Tag Reference (S7-1500 Address Space)

IEC 61131-3 Naming Rules: x = Boolean (0/1), r = Real (float), MB = Solenoid Valve Command (Magnet-Befehl), GF = Device Feedback (Geräte-Feedback), BG = Limit Switch, Out = Digital Output.

4. Standardized Failure Mode Data Labels for ML Training


### Table 1

| Workstation / Layer | PLC / Gateway Type | OPC UA Endpoint IP URL | Function / Scope |
| --- | --- | --- | --- |
| Station 1 (ASRS) | Siemens S7-1500 PLC | opc.tcp://172.21.1.1:4840 | Warehouse Storage & Retrieval |
| Station 2 (Linear) | Siemens S7-1500 PLC | opc.tcp://172.21.2.1:4840 (or .7.1) | Linear Branching Conveyor |
| Station 3 (RASS PLC) | Siemens S7-1500 PLC | opc.tcp://172.21.3.1:4840 | Mitsubishi RV-4FL Robot PLC |
| Station 3 (RASS Energy) | Festo CPX-E_EMB_RASS | opc.tcp://172.21.3.60:4840 | RASS Robot Local Power & Air |
| Station 4 (Magazine) | Siemens S7-1500 PLC | opc.tcp://172.21.4.1:4840 | Workpiece Magazine Feeding |
| Station 5 (Muscle Press) | Siemens S7-1500 PLC | opc.tcp://172.21.5.1:4840 | Pneumatic Muscle Press PLC |
| Station 5 (Press Energy) | Festo CPX-E_EMB_MPRESS | opc.tcp://172.21.5.60:4840 | Muscle Press Local Power & Air |
| Central Line Energy | Festo CPX-E_Energy | opc.tcp://172.21.0.60:4840 | Total CP Line Power & Air Header |
| Central MES4 Server | Festo Ciros Studio / MES | opc.tcp://172.21.0.90:4840 | Central MES Production Server |



### Table 2

| Sensor Channel Name | Unit | Measurement Scope | AI Maintenance Significance |
| --- | --- | --- | --- |
| Pressure | bar | Pneumatic Line Air Pressure | Detects leaks, pressure drops & FRL regulator issues |
| Flow | L/min | Active Moving Air Volume Rate | Detects cylinder actuation spikes & line blowouts |
| ActivePowerTotal | Watts (W) | Total 3-Phase Electrical Power | Primary indicator of total mechanical workload & speed |
| ActivePowerL1 / L2 / L3 | Watts (W) | Per-Phase Electrical Power Distribution | Detects phase unbalance & single-phase overload |
| CurrentL1 / L2 / L3 | Amperes (A) | 3-Phase Line Currents | Detects motor friction, mechanical binding & load shifts |
| VoltageL1 / L2 / L3 | Volts (V) | 3-Phase AC Line Voltages | Monitors supply voltage stability & brownouts |
| PowerFactorL1 / L2 / L3 | Ratio (0-1) | Electrical Power Factors per Phase | Indicates inductive motor efficiency & reactive loss |
| ReactivePowerTotal | VAR | Total Reactive Electrical Power | Measures inductive motor magnetizing load |
| ReactivePowerL1/L2/L3 | VAR | Per-Phase Reactive Power | Diagnostic metric for motor winding degradation |



### Table 3

| PLC Tag Name (UaExpert) | Signal Type | Physical Hardware Component | Manual Citation & Page |
| --- | --- | --- | --- |
| xG1_MB20 | BOOL (Output) | Stopper 1 Solenoid Valve Lower/Extend | RASS Manual p.184 / ASRS Manual p.95 |
| xG1_MB21 | BOOL (Output) | Stopper 1 Solenoid Valve Raise/Retract | EPLAN Schematics p.37 |
| xG1_MB30 | BOOL (Output) | Stopper 2 Solenoid Valve Lower/Extend | RASS Manual p.184 / ASRS Manual p.97 |
| xG1_MB40 | BOOL (Output) | Stopper 3 / Bypass Solenoid Valve | RASS Manual p.185 |
| xG1_GF25 | BOOL (Input) | Stopper 1 Device Position Feedback | EPLAN Schematics p.38 |
| xG1_BG20 | BOOL (Input) | Stopper 1 Down Limit Switch | RASS Manual p.184 |
| xG1_BG21..BG24 | BOOL (Input) | Pallet RFID & Optical Identity Sensors | RASS Manual p.184 |
| xG1_Out00 / Out01 | BOOL (Output) | Conveyor Belt Motor Run & Direction Relays | ASRS Manual p.144 |
| xG1_Out02 / Out03 | BOOL (Output) | Station Signal Tower Lamps (Green/Yellow/Red) | RASS Manual p.158 |
| xH_D1 / xH_D2 | BOOL (Handshake) | Station-to-Robot Handshake (Ready to Pick) | RASS Manual p.158 |



### Table 4

| Dataset Label String | Failure Mode Description | Lab Physical Induction Method | AI Performance Status |
| --- | --- | --- | --- |
| NORMAL | Healthy Baseline Operation | 100% Robot Speed, 6.6 bar supply, 3 carriers | 🟢 100% Real Lab Data |
| FM01_PRESSURE_DROP | Air Supply Pressure Drop / Leakage | FRL Regulator set to 5.0 bar (MS6-LFR) | 🟢 100% Real Lab Data (1.00 F1) |
| FM02_FLOW_RESTRICT | Partial Flow Restriction | Stopper Cylinder Needle Valve 2 turns CW | 🟡 Protocol Ready / Smoke tested |
| FM03_FLOW_HEAVY_RESTRICT | Heavy Flow Restriction (~75%) | Stopper Cylinder Needle Valve 4 turns CW | 🟡 Protocol Ready / Smoke tested |
| FM04_OVERLOAD | Conveyor Belt Slip / Motor Overload | Conveyor belt tension adjustment screw | 🟡 Protocol Ready / Smoke tested |
| FM05_IDLE_NO_LOAD | Empty Station Cycle (No Workpiece) | Cycle executed without pallet in station | 🟡 Protocol Ready / Smoke tested |
| FM06_SPEED_REDUCTION | Robot Speed Override (50%) | Robot controller speed override set to 50% | 🟢 100% Real Lab Data (1.00 F1) |
| FM07_PHASE_IMBALANCE | Electrical Sub-Device Phase Shift | Sub-device load disabled in MES4 | 🟡 Protocol Ready / Smoke tested |
| FM08_SENSOR_OBSTRUCT | Optical Sensor Lens Obstruction | Semi-transparent film over optical lens | 🟡 Protocol Ready / Smoke tested |
| FM09_INTERMITTENT | Dynamic Pressure Modulation | Regulator knob modulated 5.0 ↔ 6.6 bar | 🟡 Protocol Ready / Smoke tested |
| FM10_OVERPRESSURE | Line Overpressure (~7.8 bar) | FRL Regulator set to 7.8 bar | 🟡 Protocol Ready / Smoke tested |

