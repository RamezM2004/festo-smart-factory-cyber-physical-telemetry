# Mpress Station — Severity-Graduated Pressure Data Collection Protocol
## GJU Smart Factory — Multi-Severity Fault Induction on Muscle Press (Station 5)

---

## Overview

This protocol extends the original fault induction study to the **Muscle Press station
(Station 5)** with a **multi-severity pressure gradient**. Instead of a single pressure
drop level, we record data at 2 graduated severity levels to train a **degradation
staging model** that classifies fault severity, not just fault presence.

> **Important**: The Muscle Press requires up to **10 bar peak force** for its press
> stroke. Below ~5 bar the station **cannot complete the press operation** and will
> fault. This limits the useful degradation window to ~7.4 → ~5.0 bar.

This protocol also covers collecting **cross-station pressure drop** data from the
other 3 stations (ASRS, Linear, Magazine) and **conveyor belt slowdown** (FM06) data.

### Station Details

| Parameter | Value |
|-----------|-------|
| Station | Muscle Press (Station 5) |
| PLC | Siemens S7-1500 (`opc.tcp://172.21.5.1:4840`) |
| Energy Gateway | Festo CPX-E_EMB_MPRESS (`opc.tcp://172.21.5.60:4840`) |
| Central Line Energy | Festo CPX-E_Energy (`opc.tcp://172.21.0.60:4840`) |
| Nominal Pressure | ~7.4 bar |
| Peak Requirement | ~10 bar (press stroke) |
| Minimum Operating | ~5.0 bar (below this → station fails) |

### Data Source

Export data from the **CPX-IOT energy dashboard** (same method you used for the
`RASS_Mpress_low.csv` and `CP_MPress_low.csv` files).

---

## Before You Start

### Pre-Flight Checks
- [ ] CP Factory powered on and warmed up (at least 5 minutes idle)
- [ ] MES4 running and Muscle Press station is cycling normally
- [ ] CPX-IOT dashboard open in browser
- [ ] Pressure gauge readable at the FRL regulator
- [ ] This protocol open on a tablet or printed out
- [ ] Previous data backed up

### File Naming Convention

Use this exact naming pattern for the files you export:

```
MPRESS_NORMAL_baseline.csv        ← Healthy baseline at ~7.4 bar
CP_ALL_NORMAL_mpress_baseline.csv ← Central line view of baseline

MPRESS_FM01_LOW01_mild.csv        ← Mild drop at ~6.5 bar
CP_ALL_FM01_LOW01_mild.csv        ← Central line view

MPRESS_FM01_LOW02_moderate.csv    ← Moderate drop at ~5.5 bar (near failure threshold)
CP_ALL_FM01_LOW02_moderate.csv    ← Central line view
```

For cross-station pressure drop recordings:
```
ASRS_FM01_pressure_drop.csv       ← ASRS warehouse at lowered pressure
LINEAR_FM01_pressure_drop.csv     ← Linear conveyor at lowered pressure
MAGAZINE_FM01_pressure_drop.csv   ← Magazine feeder at lowered pressure
```

For conveyor belt slowdown:
```
RASS_FM06_belt_slowdown.csv       ← Conveyor belt physically slowed
```

Save all files into: `Smart maintenance/data/`

---

## Session 0 — NORMAL Baseline (MPRESS)

**Duration:** 10 minutes minimum (600 rows)
**Pressure:** ~7.4 bar (factory default — do NOT touch the regulator)

1. Confirm pressure regulator is at nominal (~7.4 bar on the gauge)
2. Confirm the Muscle Press is cycling normally in MES4
3. Open CPX-IOT dashboard → select the Mpress energy gateway
4. Start data export / recording
5. Let the station run normally for **10 minutes**
6. Stop export → save **two files**:
   - `MPRESS_NORMAL_baseline.csv` (from the Mpress energy box view)
   - `CP_ALL_NORMAL_mpress_baseline.csv` (from the central line view)

> Record: Start time ________ | End time ________ | Gauge reading: ________ bar

---

## Session 1 — FM01_LOW01: Mild Pressure Drop (~6.5 bar)

**Duration:** 10 minutes
**Target pressure:** ~6.5 bar
**Represents:** Early-stage seal wear, minor leak beginning

1. Confirm station is cycling normally, then:
2. **Slowly turn the FRL pressure regulator DOWN to ~6.5 bar**
3. Wait 30 seconds for pressure to stabilize
4. Confirm the gauge reads ~6.5 bar
5. Start CPX-IOT data export
6. Let run for **10 minutes** (station should still cycle normally, just slightly slower)
7. Stop export → save as:
   - `MPRESS_FM01_LOW01_mild.csv`
   - `CP_ALL_FM01_LOW01_mild.csv`

**Expected observations:**
- Pressure channel: ~6.5 bar (vs normal ~7.4)
- Flow: slightly higher as system compensates
- Power: minor variation
- Station should still complete cycles normally

> Record: Start time ________ | Gauge: ________ bar | Station cycling OK? Y / N

---

## Session 2 — FM01_LOW02: Moderate Pressure Drop (~5.5 bar)

**Duration:** 10 minutes
**Target pressure:** ~5.5 bar
**Represents:** Moderate degradation — near the failure threshold

1. Confirm station has returned to normal cycling, then:
2. **Turn the FRL pressure regulator DOWN to ~5.5 bar**
3. Wait 30 seconds for stabilization
4. Confirm gauge reads ~5.5 bar
5. Start CPX-IOT data export
6. Let run for **10 minutes**
7. Stop export → save as:
   - `MPRESS_FM01_LOW02_moderate.csv`
   - `CP_ALL_FM01_LOW02_moderate.csv`

**Expected observations:**
- Pressure channel: ~5.5 bar
- Flow: noticeably different pattern
- Power: actuator cycles may show slower completion
- Station may show occasional delays but should still complete the press

> ⚠️ This is close to the failure threshold (~5.0 bar). If station faults/stops,
> note the time — the transition from operating to failing is the most valuable data.

> Record: Start time ________ | Gauge: ________ bar | Any stalls? ________

---

## Session 3 — Cross-Station Pressure Drop (ASRS, Linear, Magazine)

**Duration:** 5–10 minutes per station
**Target pressure:** ~5.0 bar (or wherever you lowered the regulator)
**Purpose:** Same fault (FM01) across different stations → transfer learning study

These stations use smaller cylinders for stoppers and actuators, so they can
tolerate lower pressures than the Muscle Press.

### 3a — ASRS Warehouse (Station 1)
1. Lower the pressure regulator to ~5.0 bar
2. Start data export from the CPX-IOT dashboard
3. Let run for 5–10 minutes
4. Save as `ASRS_FM01_pressure_drop.csv`

### 3b — Linear Conveyor (Station 2)
1. Same pressure setting (~5.0 bar)
2. Export data for 5–10 minutes
3. Save as `LINEAR_FM01_pressure_drop.csv`

### 3c — Magazine Feeder (Station 4)
1. Same pressure setting (~5.0 bar)
2. Export data for 5–10 minutes
3. Save as `MAGAZINE_FM01_pressure_drop.csv`

> **Restore pressure to ~7.4 bar after each station recording.**

> Record each station: Start time ________ | Gauge: ________ bar | Notes: ________

---

## Session 4 — FM06: Conveyor Belt Slowdown

**Duration:** 5–10 minutes
**Purpose:** Real belt-slowdown data to complement the existing robot-speed FM06 data
**Represents:** Belt tension loss, worn drive roller, motor aging

> Note: You already have FM06 data from robot speed reduction (50%). This session
> captures the *conveyor belt* version of the same fault — a physically different
> mechanism with a different sensor signature.

1. Restore all pressures to nominal (~7.4 bar)
2. Physically slow the conveyor belt (via the speed potentiometer, MES4 parameter,
   or belt tension adjustment — whichever method is accessible)
3. Start data export
4. Let run for 5–10 minutes
5. Restore belt speed to default
6. Save as `RASS_FM06_belt_slowdown.csv`

**Expected observations:**
- Power: slightly lower than normal
- Current: slightly lower
- Cycle time: measurably longer
- Pressure/Flow: largely unchanged (this is a mechanical fault, not pneumatic)

> Record: Start time ________ | Speed reduced to: ________% | Method: ________

---

## Restore & Verify

After completing all sessions:

1. **Turn the FRL regulator BACK to ~7.4 bar**
2. Wait 1 minute for system to stabilize
3. Confirm the station cycles normally for at least 2 minutes
4. Verify gauge reads ~7.4 bar

---

## After All Sessions

1. Confirm you have your CSV files in `Smart maintenance/data/`:
   - 2 MPRESS baseline files (MPRESS + CP_ALL)
   - 4 MPRESS fault files (2 severity levels × 2 views each)
   - 3 cross-station FM01 files (ASRS, Linear, Magazine)
   - 1 belt slowdown file
2. Run `python 02_build_dataset.py` to rebuild the labeled dataset
3. Run `python 03_train_classifier.py` to retrain with the expanded data
4. Run `python 06_cross_station_analysis.py` for cross-station transfer evaluation

---

## Session Log

| Session | Pressure Target | Actual Gauge | Start Time | End Time | Rows | Station OK? | Notes |
|---------|----------------|-------------|-----------|---------|------|------------|-------|
| MPRESS NORMAL | ~7.4 bar |          |           |         |      |            |       |
| MPRESS LOW01 | ~6.5 bar  |          |           |         |      |            |       |
| MPRESS LOW02 | ~5.5 bar  |          |           |         |      |            |       |
| ASRS FM01    | ~5.0 bar  |          |           |         |      |            |       |
| LINEAR FM01  | ~5.0 bar  |          |           |         |      |            |       |
| MAGAZINE FM01| ~5.0 bar  |          |           |         |      |            |       |
| FM06 Belt    | N/A       |          |           |         |      |            |       |

---

## Quick Reference — What You Already Have

From your previous session (Aug 12), you collected data at a pressure that drifted
from ~7.45 → ~7.08 bar. This has been saved as:

| File | → Saved As |
|------|----------|
| `RASS_Mpress_low.csv` | `MPRESS_FM01_LOW01_pressure_drop.csv` |
| `CP_MPress_low.csv` | `CP_ALL_FM01_LOW01_pressure_drop.csv` |

This data represents a **mild/early-stage** pressure drop and will be used as
the LOW01 severity level. You still need to collect:
- MPRESS NORMAL baseline (~7.4 bar)
- MPRESS LOW02 (~5.5 bar — near the failure threshold)
- Cross-station FM01 from ASRS, Linear, Magazine
- FM06 belt slowdown (optional but recommended)
