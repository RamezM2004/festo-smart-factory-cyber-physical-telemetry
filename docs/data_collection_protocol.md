# Data Collection Protocol
## GJU Smart Factory — Smart Maintenance Fault Recording Sessions

---

## Overview

This document is your step-by-step guide for recording all 11 data sessions
(1 NORMAL baseline + 10 passive fault conditions) on the CP Factory.

Each session produces one CSV export from MES4 that will be used to train
the supervised fault-detection AI model.

---

## Before You Start

### Equipment & Materials Needed
- [ ] CP Factory running and warmed up (at least 5 minutes idle)
- [ ] MES4 software open and data logging active
- [ ] Pressure regulator accessible and readable
- [ ] Manual needle valves identified on pneumatic lines
- [ ] Extra weight for overload test (books, ~1–2 kg total, stacked on pallet)
- [ ] Small piece of cardboard or tape (for sensor obstruction test)
- [ ] This protocol printed out or open on a tablet
- [ ] Shared naming sheet to log filenames + timestamps

### Station Selection
> **Run all sessions on the same station** (recommend: RASS Robot Station)
> This keeps the baseline consistent and the classifier well-calibrated.

### Naming Convention for Exports
```
RASS_NORMAL_session1.csv
RASS_FM01_pressure_drop.csv
RASS_FM02_flow_restrict.csv
RASS_FM03_flow_block.csv
RASS_FM04_overload.csv
RASS_FM05_idle_no_load.csv
RASS_FM06_speed_reduction.csv
RASS_FM07_phase_imbalance.csv
RASS_FM08_sensor_obstruct.csv
RASS_FM09_intermittent.csv
RASS_FM10_overpressure.csv
```
Save all files into: `Smart maintenance/data/`

---

## Session 0 — NORMAL Baseline

**Duration:** 5 minutes minimum (300 rows)
**Goal:** Capture clean, healthy operation

1. Confirm pressure regulator is at nominal (~6.9 bar)
2. Confirm all valves are fully open
3. Confirm conveyor speed is at default
4. Place a pallet on the conveyor and let it cycle normally
5. Start MES4 data export / logging
6. Let run for **5 minutes minimum**
7. Stop export → save as `RASS_NORMAL_session1.csv`

> Record: Start time ________ | End time ________ | Notes: ________________

---

## Session 1 — FM-01: Pressure Drop

**Represents:** Air leak from worn seal or loose fitting
**Duration:** 3–5 minutes

1. Restore to NORMAL, record 30 seconds of normal, then:
2. **Turn pressure regulator DOWN to ~5.0 bar**
3. Observe that Pressure reads ~5.0 on the gauge
4. Start logging → run for 3–5 minutes
5. Restore regulator to ~6.9 bar
6. Save as `RASS_FM01_pressure_drop.csv`

**Expected sensors affected:** Pressure ↓, Flow ↑ slightly
> Record: Start time ________ | Regulator set to: ______ bar | Notes: ________________

---

## Session 2 — FM-02: Partial Flow Restriction

**Represents:** Partially clogged directional valve or kinked tubing
**Duration:** 3–5 minutes

1. Restore to NORMAL, then:
2. **Locate a manual needle valve on a pneumatic actuator line**
   (the small thumbscrew-type flow control fittings on the cylinder ports)
3. **Close it to approximately 50%** (turn clockwise ~2–3 turns from fully open)
4. Start logging → run for 3–5 minutes
5. Restore valve to fully open
6. Save as `RASS_FM02_flow_restrict.csv`

**Expected sensors affected:** Flow ↓ ~50%, Pressure normal, cycle time ↑
> Record: Start time ________ | Valve ID/location: ________________ | Notes: ________________

---

## Session 3 — FM-03: Complete Flow Blockage

**Represents:** Fully jammed actuator or completely closed solenoid valve
**Duration:** 3 minutes

1. Restore to NORMAL, then:
2. **Locate the same needle valve as FM-02**
3. **Fully close it** (turn clockwise until it stops — do not overtighten)
4. Start logging → run for 3 minutes (station may stall — this is expected)
5. Restore valve to fully open
6. Save as `RASS_FM03_flow_block.csv`

> ⚠️ If the station alarms and requires a reset in MES4, note this — it is valuable data showing the fault detection behavior.

**Expected sensors affected:** Flow → ~0, Pressure elevated, TotalPower drops to idle
> Record: Start time ________ | Notes: ________________

---

## Session 4 — FM-04: Motor Overload

**Represents:** Bearing wear, belt misalignment, or overloaded pallet
**Duration:** 3–5 minutes

1. Restore to NORMAL, then:
2. **Carefully place 1–2 kg of extra weight on top of the pallet**
   (use books or a measured sandbag — keep weight centered and stable)
3. Start logging → run for 3–5 minutes
4. Remove the added weight
5. Save as `RASS_FM04_overload.csv`

**Expected sensors affected:** CurrentL2 or CurrentL3 ↑ 20–50%, TotalPower ↑
> Record: Start time ________ | Added weight: ______ kg | Notes: ________________

---

## Session 5 — FM-05: Idle / No-Load Run

**Represents:** Pallet detection sensor failure; station cycles with no workpiece
**Duration:** 3–5 minutes

1. Restore to NORMAL, then:
2. **Remove the pallet from the conveyor** — let the station run its cycle without any workpiece
3. Start logging → run for 3–5 minutes (observe empty cycles)
4. Return pallet to conveyor
5. Save as `RASS_FM05_idle_no_load.csv`

**Expected sensors affected:** TotalPower → ~30% of normal, Flow ↓ sharply
> Record: Start time ________ | Notes: ________________

---

## Session 6 — FM-06: Conveyor Speed Reduction

**Represents:** Belt tension loss or worn drive roller
**Duration:** 3–5 minutes

**Option A (via MES4):**
1. In MES4, find the conveyor speed parameter for the RASS station
2. Reduce it to 50–60% of normal speed
3. Start logging → run for 3–5 minutes → restore speed → save

**Option B (via hardware potentiometer):**
1. Locate the speed adjustment potentiometer on the CP Factory drive module
2. Turn it to reduce speed by ~50%
3. Start logging → run for 3–5 minutes → restore → save

5. Save as `RASS_FM06_speed_reduction.csv`

**Expected sensors affected:** TotalPower slightly ↓, cycle time measurably longer
> Record: Start time ________ | Speed reduced to: ______% | Method used: ________________

---

## Session 7 — FM-07: Phase Imbalance

**Represents:** Loose terminal or blown fuse on one supply phase
**Duration:** 3–5 minutes

1. Restore to NORMAL, then:
2. **In MES4, identify and temporarily disable a sub-station or device that primarily loads one phase** (e.g., a specific motor or heater on L2)
3. Start logging → run for 3–5 minutes
4. Re-enable the sub-station in MES4
5. Save as `RASS_FM07_phase_imbalance.csv`

**Expected sensors affected:** One of ActivePowerL1/L2/L3 drops significantly
> Record: Start time ________ | Disabled device: ________________ | Notes: ________________

---

## Session 8 — FM-08: Sensor Obstruction

**Represents:** Dust or oil contamination on the RASS ultrasonic sensor lens
**Duration:** 3–5 minutes

1. Restore to NORMAL, then:
2. **Cut a small piece of cardboard or fold a piece of tape**
3. **Partially cover the face of the RASS ultrasonic sensor** (about 50% coverage)
4. Start logging → run for 3–5 minutes (observe retry loops / longer cycle times)
5. Remove the obstruction → clean the sensor face with a dry cloth
6. Save as `RASS_FM08_sensor_obstruct.csv`

**Expected sensors affected:** Power pattern shows repeated short actuations; cycle time increases and becomes irregular
> Record: Start time ________ | Coverage % of sensor: ______% | Notes: ________________

---

## Session 9 — FM-09: Intermittent Supply Interruption

**Represents:** Unstable power/air supply or relay contact bouncing
**Duration:** 4–5 minutes

1. Restore to NORMAL, then:
2. Start logging
3. **While running, briefly toggle the main air supply valve OFF for 2–3 seconds, then back ON**
4. Repeat this 4–5 times during the session with ~45 seconds of normal operation between each toggle
5. End with the supply in the normal ON state
6. Save as `RASS_FM09_intermittent.csv`

**Expected sensors affected:** Pressure and Flow drop sharply to ~0 for 2–3 seconds then recover, Power dips in sync — creates a distinct sawtooth/spike pattern
> Record: Start time ________ | Number of toggles: ______ | Notes: ________________

---

## Session 10 — FM-10: Over-Pressure

**Represents:** Faulty pressure regulator stuck at too-high a setting
**Duration:** 3–5 minutes

1. Restore to NORMAL, then:
2. **Turn pressure regulator UP to ~8.0 bar**
   (This is within the safe operating range of the CP Factory — max rated 8 bar)
3. Observe that Pressure reads ~7.5–8.0 on the gauge
4. Start logging → run for 3–5 minutes
5. Restore regulator to ~6.9 bar
6. Save as `RASS_FM10_overpressure.csv`

**Expected sensors affected:** Pressure ↑ to 7.5–8.0 bar, Flow ↑, actuator cycles slightly faster
> Record: Start time ________ | Regulator set to: ______ bar | Notes: ________________

---

## After All Sessions

1. Confirm you have **11 CSV files** in `Smart maintenance/data/`
2. Run `02_build_dataset.py` to assemble the labeled training dataset
3. Run `03_train_classifier.py` to train the models
4. Run `04_evaluate_model.py` to see accuracy results

---

## Quick Checklist — Between Every Session

- [ ] Restored pressure to ~6.9 bar
- [ ] All needle valves fully open
- [ ] Conveyor speed at default
- [ ] No extra weight on pallet
- [ ] Sensor faces clear and clean
- [ ] Air supply in normal ON state
- [ ] MES4 export saved and renamed

---

## Notes Log

| Session | Start Time | End Time | Rows Exported | Issues |
|---------|-----------|---------|--------------|--------|
| NORMAL  |           |         |              |        |
| FM-01   |           |         |              |        |
| FM-02   |           |         |              |        |
| FM-03   |           |         |              |        |
| FM-04   |           |         |              |        |
| FM-05   |           |         |              |        |
| FM-06   |           |         |              |        |
| FM-07   |           |         |              |        |
| FM-08   |           |         |              |        |
| FM-09   |           |         |              |        |
| FM-10   |           |         |              |        |
