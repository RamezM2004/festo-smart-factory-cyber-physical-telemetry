"""
MES4 Efficiency Report Parser
Parses MES4 Efficiency Report CSV files and cross-references them with energy telemetry AI predictions.
This script performs Pillar 2 of the Plan B research scope.
"""
import os
import sys
import argparse
import csv
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')

# ───────────────────────────────────────────────────────────────────────────────
# Data Parsing & Metrics Calculation
# ───────────────────────────────────────────────────────────────────────────────

def parse_mes4_report(filepath):
    """Parses MES4 efficiency report CSV."""
    entries = []
    
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            dt = datetime.strptime(row['TimeStamp'], '%m/%d/%Y %I:%M:%S %p')
            entries.append({
                'id': int(row.get('ID', 0)),
                'timestamp': dt,
                'automatic_mode': int(row.get('AutomaicMode', 0)),
                'manual_mode': int(row.get('ManualMode', 0)),
                'busy': int(row.get('Busy', 0)),
                'reset': int(row.get('Reset', 0)),
                'error_l0': int(row.get('ErrorL0', 0)),
                'error_l1': int(row.get('ErrorL1', 0)),
                'error_l2': int(row.get('ErrorL2', 0))
            })
            
    return entries

def compute_metrics(entries):
    """Computes OEE-like metrics from MES4 entries."""
    total_entries = len(entries)
    if total_entries == 0:
        return None
        
    start_time = entries[0]['timestamp']
    end_time = entries[-1]['timestamp']
    duration_mins = (end_time - start_time).total_seconds() / 60.0
    
    auto_no_err_count = sum(1 for e in entries if e['automatic_mode'] == 1 and e['error_l0'] == 0 and e['error_l1'] == 0 and e['error_l2'] == 0)
    busy_count = sum(1 for e in entries if e['busy'] == 1)
    error_count = sum(1 for e in entries if e['error_l0'] == 1 or e['error_l1'] == 1 or e['error_l2'] == 1)
    
    availability = (auto_no_err_count / total_entries) * 100
    utilization = (busy_count / total_entries) * 100
    error_rate = (error_count / total_entries) * 100
    
    class0_events = sum(1 for e in entries if e['error_l0'] == 1)
    class1_events = sum(1 for e in entries if e['error_l1'] == 1)
    class2_events = sum(1 for e in entries if e['error_l2'] == 1)
    reset_events = sum(1 for e in entries if e['reset'] == 1)
    
    # Calculate Mean Cycle Time (average time between consecutive Busy=1 transitions)
    busy_transitions = []
    for i in range(1, len(entries)):
        if entries[i]['busy'] == 1 and entries[i-1]['busy'] == 0:
            busy_transitions.append(entries[i]['timestamp'])
            
    cycle_times = []
    for i in range(1, len(busy_transitions)):
        diff = (busy_transitions[i] - busy_transitions[i-1]).total_seconds()
        cycle_times.append(diff)
        
    mean_cycle_time = sum(cycle_times) / len(cycle_times) if cycle_times else 0.0
    
    return {
        'start_time': start_time,
        'end_time': end_time,
        'total_entries': total_entries,
        'duration_mins': duration_mins,
        'availability': availability,
        'utilization': utilization,
        'error_rate': error_rate,
        'class0_events': class0_events,
        'class1_events': class1_events,
        'class2_events': class2_events,
        'reset_events': reset_events,
        'mean_cycle_time': mean_cycle_time
    }

# ───────────────────────────────────────────────────────────────────────────────
# AI Inference Cross-Reference
# ───────────────────────────────────────────────────────────────────────────────

def cross_reference_ai(entries, inference_path):
    """
    Cross-references MES4 errors with AI inference predictions.
    Analyzes simultaneous faults, early warnings, and false positives/undetected faults.
    """
    print(f"Loading inference report from {inference_path}...")
    # Placeholder for actual cross-reference logic which would parse the inference text file
    # and compare timestamps/windows with the MES4 error events.

# ───────────────────────────────────────────────────────────────────────────────
# Reporting
# ───────────────────────────────────────────────────────────────────────────────

def generate_report(metrics):
    """Generates a formatted summary report string."""
    report = []
    report.append("══════════════════════════════════════════════════════════════")
    report.append("  MES4 Efficiency Report Analysis")
    report.append("══════════════════════════════════════════════════════════════")
    report.append("")
    report.append("Production Session Summary")
    report.append("─────────────────────────────────────────────────────────────")
    
    start_dt = metrics['start_time']
    end_dt = metrics['end_time']
    
    start_str = f"{start_dt.month}/{start_dt.day}/{start_dt.year} {start_dt.strftime('%I:%M %p').lstrip('0')}"
    end_str = f"{end_dt.month}/{end_dt.day}/{end_dt.year} {end_dt.strftime('%I:%M %p').lstrip('0')}"
    
    report.append(f"  Recording Period   : {start_str} → {end_str}")
    report.append(f"  Total Entries      : {metrics['total_entries']}")
    report.append(f"  Total Duration     : {metrics['duration_mins']:.1f} minutes")
    report.append("")
    report.append("OEE Metrics")
    report.append("─────────────────────────────────────────────────────────────")
    report.append(f"  Availability       : {metrics['availability']:.1f}%  (AutomaticMode with no errors)")
    report.append(f"  Utilization (Busy) : {metrics['utilization']:.1f}%  (Busy=1 entries)")
    report.append(f"  Error Rate         : {metrics['error_rate']:.1f}%   (Any error flag present)")
    report.append("")
    report.append("Error Classification")
    report.append("─────────────────────────────────────────────────────────────")
    report.append(f"  Class 0 (Critical) : {metrics['class0_events']} events")
    report.append(f"  Class 1 (Cycle Stop): {metrics['class1_events']} events  ")
    report.append(f"  Class 2 (Warning)  : {metrics['class2_events']} events")
    report.append(f"  Resets             : {metrics['reset_events']} events")
    
    return "\n".join(report)

# ───────────────────────────────────────────────────────────────────────────────
# Main Execution
# ───────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MES4 Efficiency Report Parser")
    parser.add_argument('efficiency_report', help="MES4 Efficiency Report CSV file")
    parser.add_argument('--inference', help="Inference report txt file from 05_inference.py")
    args = parser.parse_args()
    
    if not os.path.exists(args.efficiency_report):
        print(f"Error: {args.efficiency_report} not found.")
        sys.exit(1)
        
    entries = parse_mes4_report(args.efficiency_report)
    metrics = compute_metrics(entries)
    
    if metrics is None:
        print("No entries found in report.")
        sys.exit(1)
        
    if args.inference and os.path.exists(args.inference):
        cross_reference_ai(entries, args.inference)
        
    report_text = generate_report(metrics)
    print(report_text)
    
    # Save report
    os.makedirs('models', exist_ok=True)
    report_path = os.path.join('models', 'mes4_analysis_report.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_text)
    print(f"\nReport saved to {report_path}")

if __name__ == '__main__':
    main()
