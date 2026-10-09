# Sample Production Telemetry Datasets

This folder provides sample sensor telemetry streams recorded directly from the industrial Festo Cyber-Physical (CP) Factory at the German Jordanian University (GJU).

## Files Included

### 1. `sample_energy_telemetry_run3.csv` (Continuous Thermodynamic Channels)
- **Source**: Festo CPX-E Energy Gateways (Central Line Header `172.21.0.60` and Station 3 `172.21.3.60`)
- **Sampling Rate**: 1.0 Hz (continuous time-series)
- **Batch Horizon**: Full 883-second pristine production run producing 8 smart devices (`NORMAL_RUN3`)
- **Columns (23 channels)**:
  - `Timestamp`: ISO datetime
  - `Pressure`: Pneumatic line pressure (bar)
  - `Flow`: Volumetric compressed air flow rate (L/min)
  - `ActivePowerTotal`: 3-phase total active electrical power (W)
  - `ActivePowerL1`, `ActivePowerL2`, `ActivePowerL3`: Per-phase active power distribution (W)
  - `CurrentL1`, `CurrentL2`, `CurrentL3`: Phase line currents (A)
  - `VoltageL1`, `VoltageL2`, `VoltageL3`: Phase line voltages (V)
  - `PowerFactorL1`, `PowerFactorL2`, `PowerFactorL3`: Electrical power factors

### 2. `sample_plc_limit_switches_asrs_run3.csv` (Discrete Machine State Switches)
- **Source**: Siemens S7-1512SP Station 1 PLC (`172.21.1.1`) polled passively via OPC UA
- **Sampling Interval**: ~3.9 s polling loop (avoids scan jitter)
- **Channels**: 265 discrete boolean state tags:
  - `DataBlocksInstance.dbApplication.Outputs.xBusy`: Master crane busy execution flag (captures all 16 warehouse operations)
  - `Inputs.xU1_BG46`: Telescopic fork extension proximity reed switch (`SMT-8M-PS-24V`)
  - `Inputs.xG1_BG21`: Turntable infeed stopper optical sensor (traces all 8 completed workpiece deposits)
  - `Inputs.xU1_BG51`, `Inputs.xU1_BG53`: Shelf position and gantry home sensors

### 3. `sample_plc_limit_switches_all_stations.csv` (Multi-Station Limit Switches)
- Synchronized limit switch captures across all four automated stations:
  - Station 1 (ASRS High-Bay Warehouse)
  - Station 6 (Magazine Front Cover Feeder)
  - Station 7 (Festo Fluidic Muscle Press)
  - Station 3 (RASS Mitsubishi RV-4FL Articulated Assembly Robot)
