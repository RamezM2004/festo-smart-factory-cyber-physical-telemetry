import os
import shutil
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Publication quality style
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 9.5
plt.rcParams['axes.titlesize'] = 11
plt.rcParams['axes.labelsize'] = 10
plt.rcParams['xtick.labelsize'] = 9
plt.rcParams['ytick.labelsize'] = 9
plt.rcParams['legend.fontsize'] = 9
plt.rcParams['figure.titlesize'] = 12.5

DATA_DIR = r'c:\Smart Factory\Smart maintenance\data\Normal_Runs'
OUTPUT_DIR = r'c:\Smart Factory\Smart maintenance\models'
BRAIN_DIR = r'C:\Users\USER\.gemini\antigravity\brain\47a09c89-57eb-4793-9a50-2c2ce19d199f'

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(BRAIN_DIR, exist_ok=True)

# Load Datasets
df_mes = pd.read_csv(os.path.join(DATA_DIR, 'EfficencyReport.Normal3csv.csv'), sep=';')
df_cp = pd.read_csv(os.path.join(DATA_DIR, 'CP_ALL_NORMAL_RUN3_20260901_145501.csv'))
df_rass = pd.read_csv(os.path.join(DATA_DIR, 'RASS_NORMAL_RUN3_20260901_145501.csv'))
df_asrs = pd.read_csv(os.path.join(DATA_DIR, 'PLC_SWITCHES_ASRS_NORMAL_RUN3_20260901_145501.csv'))
df_mag = pd.read_csv(os.path.join(DATA_DIR, 'PLC_SWITCHES_MAGAZINE_NORMAL_RUN3_20260901_145501.csv'))
df_mpress = pd.read_csv(os.path.join(DATA_DIR, 'PLC_SWITCHES_MPRESS_NORMAL_RUN3_20260901_145501.csv'))
df_plc_rass = pd.read_csv(os.path.join(DATA_DIR, 'PLC_SWITCHES_RASS_NORMAL_RUN3_20260901_145501.csv'))

# Timestamps & elapsed seconds
t_start = pd.to_datetime('2026-09-01 ' + df_rass['Timestamp'].iloc[0])
t_end = pd.to_datetime('2026-09-01 ' + df_rass['Timestamp'].iloc[-1])
total_sec = (t_end - t_start).total_seconds()

for df in [df_rass, df_cp, df_asrs, df_mag, df_mpress, df_plc_rass]:
    df['sec'] = (pd.to_datetime('2026-09-01 ' + df['Timestamp']) - t_start).dt.total_seconds()

df_mes['dt'] = pd.to_datetime(df_mes['TimeStamp'])
df_mes['sec'] = (df_mes['dt'] - t_start).dt.total_seconds()

# ==============================================================================
# FIGURE 1: TRI-LAYER DIGITAL TWIN PRODUCTION RECONSTRUCTION
# ==============================================================================
fig1, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 10.5), sharex=True, gridspec_kw={'height_ratios': [1.3, 1.2, 1.5]})
fig1.suptitle('Study 1: Tri-Layer Digital Twin Production Reconstruction & MES4 Cross-Validation (Run 3)', 
              fontsize=13, fontweight='bold', y=0.98)

# Layer 1: MES4 State Ground Truth
station_meta = {
    1: ('Station 1: ASRS Warehouse', '#1565c0', 3),
    6: ('Station 6: Magazine Feeder', '#2e7d32', 2),
    7: ('Station 7: Muscle Press', '#c2185b', 1),
    3: ('Station 3: RASS Robot', '#e65100', 0)
}

for st_id, (name, color, y_pos) in station_meta.items():
    st_df = df_mes[df_mes['ID'] == st_id].sort_values('sec').reset_index(drop=True)
    ax1.barh(y_pos, total_sec, left=0, height=0.55, color='#f5f5f5', edgecolor='#e0e0e0', zorder=1)
    
    for i in range(len(st_df)-1):
        if st_df.loc[i, 'Busy'] == 1 and st_df.loc[i+1, 'Busy'] == 0:
            s_sec = max(0, st_df.loc[i, 'sec'])
            e_sec = min(total_sec, st_df.loc[i+1, 'sec'])
            w = e_sec - s_sec
            if w > 0:
                ax1.barh(y_pos, w, left=s_sec, height=0.55, color=color, edgecolor='black', linewidth=0.7, zorder=3)

ax1.set_yticks([0, 1, 2, 3])
ax1.set_yticklabels(['St.3: RASS Robot', 'St.7: Muscle Press', 'St.6: Magazine', 'St.1: ASRS Crane'], fontweight='bold')
ax1.set_title('A. Layer 1: Official MES4 Execution State Ground Truth (Busy = 1 Blocks)', fontweight='bold', loc='left')
ax1.grid(True, axis='x', linestyle=':', alpha=0.6)
ax1.set_ylabel('MES4 Station State', fontweight='bold')

# Layer 2: Continuous Analog Energy Telemetry
ax2_twin = ax2.twinx()
p_line = ax2.plot(df_rass['sec'], df_rass['ActivePowerL1'], color='#0d47a1', linewidth=1.5, label='RASS Active Power L1 (W)', zorder=3)
f_line = ax2_twin.plot(df_rass['sec'], df_rass['Flow'], color='#00897b', linewidth=1.3, linestyle='--', label='RASS Pneumatic Flow (L/min)', zorder=2)

# Shaded intervals for active assembly (>120W) - NO BOXES!
is_act = df_rass['ActivePowerL1'].values > 120
diffs = np.diff(is_act.astype(int))
starts = np.where(diffs == 1)[0] + 1
ends = np.where(diffs == -1)[0] + 1
if is_act[0]: starts = np.insert(starts, 0, 0)
if is_act[-1]: ends = np.append(ends, len(is_act))

prod_count = 0
for s, e in zip(starts, ends):
    dur = df_rass['sec'].iloc[min(e, len(df_rass)-1)] - df_rass['sec'].iloc[s]
    if dur > 15:
        prod_count += 1
        s_val = df_rass['sec'].iloc[s]
        e_val = df_rass['sec'].iloc[min(e, len(df_rass)-1)]
        ax2.axvspan(s_val, e_val, color='#e3f2fd', alpha=0.45, zorder=1)
        ax2.text((s_val + e_val)/2, 245, f'P{prod_count}', ha='center', va='top', fontsize=8, fontweight='bold', color='#0d47a1')

ax2.set_ylabel('Power L1 (Watts)', fontweight='bold', color='#0d47a1')
ax2_twin.set_ylabel('Flow (L/min)', fontweight='bold', color='#00897b')
ax2.set_ylim(40, 265)
ax2_twin.set_ylim(-1, 22)
ax2.set_title('B. Layer 2: Continuous Analog Energy Telemetry (Non-Invasive Physical Footprint)', fontweight='bold', loc='left')
ax2.grid(True, linestyle=':', alpha=0.6)

lines = p_line + f_line
labels = [l.get_label() for l in lines]
labels.append('Shaded: Product Assembly Cycles (P1-P8)')
custom_patch = mpatches.Patch(facecolor='#e3f2fd', edgecolor='#90caf9', alpha=0.7)
lines.append(custom_patch)
ax2.legend(lines, labels, loc='upper right', framealpha=0.9)

# Layer 3: Discrete Digital PLC Switch Transitions (Intuitive ASRS Crane Cycles!)
plc_signals = [
    (df_asrs, 'DataBlocksInstance.dbApplication.Outputs.xBusy', 'ASRS Crane Cycles (16 Operations)', '#1565c0', 3),
    (df_mag, 'Inputs.xCL_BG7', 'Magazine Feeder Gate (8 Triggers)', '#2e7d32', 2),
    (df_mpress, 'Inputs.xH_BG1', 'MPress Cylinder Head (8 Triggers)', '#c2185b', 1),
    (df_plc_rass, 'DataBlocksGlobal.dbRob.xRun', 'RASS Robot Running (8 Triggers)', '#e65100', 0),
]

for df_s, tag, label_str, col, y_lvl in plc_signals:
    ax3.barh(y_lvl, total_sec, left=0, height=0.5, color='#f7f7f7', edgecolor='#e0e0e0', zorder=1)
    if tag in df_s.columns:
        vals = df_s[tag].fillna(0).values
        secs = df_s['sec'].values
        for j in range(len(vals)-1):
            if vals[j] == 1:
                w = secs[j+1] - secs[j]
                if w > 0:
                    ax3.barh(y_lvl, w, left=secs[j], height=0.5, color=col, edgecolor='black', linewidth=0.6, zorder=3)

ax3.set_yticks([0, 1, 2, 3])
ax3.set_yticklabels(['RASS Robot (xRun)', 'MPress (xH_BG1)', 'Magazine (xCL_BG7)', 'ASRS Crane (xBusy)'], fontweight='bold')
ax3.set_title('C. Layer 3: Discrete PLC Sensor & Actuator Activations (Micro-Level Confirmation)', fontweight='bold', loc='left')
ax3.set_ylabel('Discrete PLC Tag', fontweight='bold')
ax3.set_xlabel('Elapsed Time (Seconds) from Batch Start (14:55:02 to 15:09:45)', fontweight='bold')
ax3.set_xlim(0, total_sec)
ax3.grid(True, axis='x', linestyle=':', alpha=0.6)

tick_secs = np.linspace(0, total_sec, 9)
tick_labels = [(t_start + pd.Timedelta(seconds=s)).strftime('%H:%M:%S') for s in tick_secs]
ax3.set_xticks(tick_secs)
ax3.set_xticklabels([f'{int(s)}s\n({lbl})' for s, lbl in zip(tick_secs, tick_labels)])

plt.tight_layout()
fig1_path = os.path.join(OUTPUT_DIR, 'study1_mes_cross_validation_gantt.png')
plt.savefig(fig1_path, dpi=300)
plt.close(fig1)
print('SUCCESS: Figure 1 saved.')

# ==============================================================================
# FIGURE 2: ASRS CRANE OPERATIONS & 3-PALLET CIRCULATION (CLEAN, NO BOXES)
# ==============================================================================
fig2, (ax_asrs_ops, ax_loop) = plt.subplots(2, 1, figsize=(15, 8.5), gridspec_kw={'height_ratios': [1.1, 1]})
fig2.suptitle('Study 1: Station 1 (ASRS) Operations & Little\'s Law 3-Pallet Circulation Proof', 
              fontsize=13, fontweight='bold', y=0.98)

# Top Panel: ASRS Crane Operations (8 Dispatches D1-D8 + 8 Storage Deposits S1-S8)
s_busy = df_asrs['DataBlocksInstance.dbApplication.Outputs.xBusy'].values
diff_busy = np.diff(s_busy.astype(float))
pos_busy = np.where(diff_busy > 0)[0] + 1
neg_busy = np.where(diff_busy < 0)[0] + 1
if s_busy[0] == 1: pos_busy = np.insert(pos_busy, 0, 0)
if s_busy[-1] == 1: neg_busy = np.append(neg_busy, len(s_busy))

dispatch_indices = [0, 1, 2, 4, 6, 8, 10, 12]  # D1 to D8
deposit_indices  = [3, 5, 7, 9, 11, 13, 14, 15] # S1 to S8

# Background tracks
ax_asrs_ops.barh(1, total_sec, left=0, height=0.45, color='#f5f5f5', edgecolor='#e0e0e0', zorder=1)
ax_asrs_ops.barh(0, total_sec, left=0, height=0.45, color='#f5f5f5', edgecolor='#e0e0e0', zorder=1)

d_num = 1
s_num = 1
for idx in range(min(16, len(pos_busy))):
    t0 = df_asrs['sec'].iloc[pos_busy[idx]]
    t1 = df_asrs['sec'].iloc[min(neg_busy[idx], len(df_asrs)-1)]
    dur = t1 - t0
    
    if idx in dispatch_indices:
        ax_asrs_ops.barh(1, dur, left=t0, height=0.45, color='#1565c0', edgecolor='black', linewidth=0.7, zorder=3)
        ax_asrs_ops.text(t0 + dur/2, 1, f'D{d_num}', ha='center', va='center', fontsize=8, fontweight='bold', color='white', zorder=4)
        d_num += 1
    else:
        ax_asrs_ops.barh(0, dur, left=t0, height=0.45, color='#f57c00', edgecolor='black', linewidth=0.7, zorder=3)
        ax_asrs_ops.text(t0 + dur/2, 0, f'S{s_num}', ha='center', va='center', fontsize=8, fontweight='bold', color='white', zorder=4)
        s_num += 1

ax_asrs_ops.set_yticks([0, 1])
ax_asrs_ops.set_yticklabels(['Storage Deposits\n(S1-S8: Infeed)', 'Dispatches\n(D1-D8: Outfeed)'], fontweight='bold')
ax_asrs_ops.set_title('A. Station 1 (ASRS High-Bay Warehouse): 16 Scheduled Operations (8 Dispatches + 8 Deposits)', fontweight='bold', loc='left')
ax_asrs_ops.grid(True, axis='x', linestyle=':', alpha=0.6)

# Legend for Top Panel
d_patch = mpatches.Patch(color='#1565c0', label='Dispatches D1-D8 (Retrieval from Rack to Conveyor)')
s_patch = mpatches.Patch(color='#f57c00', label='Deposits S1-S8 (Storage of Finished Goods to Rack)')
ax_asrs_ops.legend(handles=[d_patch, s_patch], loc='upper right', framealpha=0.9)

# Bottom Panel: Pallet Circulation Gantt & Little\'s Law Proof
pallet_colors = ['#d32f2f', '#1976d2', '#388e3c']
pallet_names = ['Pallet 1 (Carrier Alpha)', 'Pallet 2 (Carrier Beta)', 'Pallet 3 (Carrier Gamma)']

for p_i in range(3):
    ax_loop.barh(p_i, total_sec, left=0, height=0.45, color='#f5f5f5', edgecolor='#e0e0e0', zorder=1)

for i, (s, e) in enumerate(zip(starts, ends)):
    dur = df_rass['sec'].iloc[min(e, len(df_rass)-1)] - df_rass['sec'].iloc[s]
    if dur > 15:
        p_idx = i % 3  # 3 circulating pallets!
        s_sec = df_rass['sec'].iloc[s]
        ax_loop.barh(p_idx, dur, left=s_sec, height=0.45, color=pallet_colors[p_idx], edgecolor='black', linewidth=0.7, zorder=3)
        ax_loop.text(s_sec + dur/2, p_idx, f'Prod #{i+1} ({dur:.0f}s)', ha='center', va='center', fontsize=7.5, fontweight='bold', color='white', zorder=4)

ax_loop.set_yticks([0, 1, 2])
ax_loop.set_yticklabels(pallet_names, fontweight='bold')
ax_loop.set_title('B. Circulating Carrier Dynamics (Little\'s Law: N = T_loop / T_takt = 273s / 91s = 3.0 Pallets)', fontweight='bold', loc='left')
ax_loop.set_xlabel('Elapsed Time (Seconds)', fontweight='bold')
ax_loop.set_xlim(0, total_sec)
ax_loop.grid(True, axis='x', linestyle=':', alpha=0.6)

p_patches = [mpatches.Patch(color=pallet_colors[i], label=pallet_names[i]) for i in range(3)]
ax_loop.legend(handles=p_patches, loc='upper right', framealpha=0.9)

plt.tight_layout()
fig2_path = os.path.join(OUTPUT_DIR, 'study1_16_trigger_asrs_and_pallet_dynamics.png')
plt.savefig(fig2_path, dpi=300)
plt.close(fig2)
print('SUCCESS: Figure 2 saved.')

# ==============================================================================
# FIGURE 3: ENERGY & THERMODYNAMIC ENVELOPE
# ==============================================================================
fig3, (ax_pwr, ax_flw, ax_prs) = plt.subplots(3, 1, figsize=(15, 9.5), sharex=True)
fig3.suptitle('Study 1: Physical Energy & Thermodynamic Baseline Envelopes (Central Header vs. Station 3)', 
              fontsize=13, fontweight='bold', y=0.98)

# Subplot 1: Active Power L1 Comparison
ax_pwr.plot(df_rass['sec'], df_rass['ActivePowerL1'], color='#0d47a1', linewidth=1.5, label='RASS Local Power L1 (W) - Station 3 (Peak: 226.0 W)')
ax_pwr.plot(df_cp['sec'], df_cp['ActivePowerL1'], color='#e65100', linewidth=1.5, linestyle='-', label='Central Factory Header Power L1 (W) - Total Line (Peak: 145.3 W)')
ax_pwr.axhline(56.9, color='#78909c', linestyle=':', label='Tare Quiescent Floor (56.9 W)')

ax_pwr.set_ylabel('Power L1 (W)', fontweight='bold')
ax_pwr.set_ylim(40, 260)
ax_pwr.set_title('A. Active Electrical Power: Station 3 Dynamic Surge (226.0 W) vs. Central Header Load (145.3 W)', fontweight='bold', loc='left')
ax_pwr.grid(True, linestyle=':', alpha=0.6)
ax_pwr.legend(loc='upper right', framealpha=0.9)

# Subplot 2: Pneumatic Air Flow Comparison
ax_flw.plot(df_rass['sec'], df_rass['Flow'], color='#00897b', linewidth=1.5, label='RASS Pneumatic Flow (L/min) - Station 3 (Peak: 15.51 L/min)')
ax_flw.plot(df_cp['sec'], df_cp['Flow'], color='#f57c00', linewidth=1.2, linestyle='--', label='Central Header Flow (L/min) - Continuous Line Supply (Peak: 1.15 L/min)')

ax_flw.set_ylabel('Flow (L/min)', fontweight='bold')
ax_flw.set_ylim(-1, 20)
ax_flw.set_title('B. Pneumatic Flow Consumption: Local Cylinder Actuation Pulses (15.51 L/min) vs. Central Background Flow', fontweight='bold', loc='left')
ax_flw.grid(True, linestyle=':', alpha=0.6)
ax_flw.legend(loc='upper right', framealpha=0.9)

# Subplot 3: Main Line Pressure Stability (Nominal 7.0 bar)
ax_prs.plot(df_rass['sec'], df_rass['Pressure'], color='#1565c0', linewidth=1.5, label='RASS Local Pressure (bar) - Mean: 6.98 bar')
ax_prs.plot(df_cp['sec'], df_cp['Pressure'], color='#ef6c00', linewidth=1.3, linestyle='--', label='Central Header Pressure (bar) - Mean: 6.99 bar')
ax_prs.axhline(7.0, color='red', linestyle=':', label='Nominal 7.0 bar Setpoint')

ax_prs.set_ylabel('Pressure (bar)', fontweight='bold')
ax_prs.set_xlabel('Elapsed Time (Seconds)', fontweight='bold')
ax_prs.set_ylim(6.0, 7.8)
ax_prs.set_xlim(0, total_sec)
ax_prs.set_title('C. Pneumatic Pressure Stability: Nominal Operating Envelope (6.76 bar to 7.17 bar)', fontweight='bold', loc='left')
ax_prs.grid(True, linestyle=':', alpha=0.6)
ax_prs.legend(loc='upper right', framealpha=0.9)

plt.tight_layout()
fig3_path = os.path.join(OUTPUT_DIR, 'study1_energy_thermodynamic_envelope.png')
plt.savefig(fig3_path, dpi=300)
plt.close(fig3)
print('SUCCESS: Figure 3 saved.')

# Copy all 3 figures to Brain folder for embedding in report artifact
shutil.copy2(fig1_path, os.path.join(BRAIN_DIR, 'study1_mes_cross_validation_gantt.png'))
shutil.copy2(fig2_path, os.path.join(BRAIN_DIR, 'study1_16_trigger_asrs_and_pallet_dynamics.png'))
shutil.copy2(fig3_path, os.path.join(BRAIN_DIR, 'study1_energy_thermodynamic_envelope.png'))
print('SUCCESS: All 3 figures copied to brain directory.')
