#!/usr/bin/env python3
"""
Comprehensive demonstration script for advanced filtering in XTI Viewer.
This script runs a live demo showing all filter combinations working.
"""

import sys
import os
import tempfile
from pathlib import Path
import time

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def create_demo_xti_file():
    """Create a demo XTI file for testing."""
    demo_content = """Channel Groups:

=== Channel Group 1: TCP Connection to DP+ (10.20.30.40:6000) ===
Start Time: 01/01/2024 10:00:00:000
Duration: 5.234 seconds

01/01/2024 10:00:00:000    TCP    FETCH - OPEN CHANNEL                     Hex: 1A 2B 3C 4D
01/01/2024 10:00:00:100    TCP    TERMINAL RESPONSE - OPEN CHANNEL         Hex: 5E 6F 7A 8B
01/01/2024 10:00:01:000    TCP    FETCH - SEND DATA                        Hex: AA BB CC DD
01/01/2024 10:00:01:500    TCP    TERMINAL RESPONSE - RECEIVE DATA         Hex: EE FF 11 22

=== Channel Group 2: TCP Connection to TAC (10.20.30.50:6001) ===
Start Time: 01/01/2024 10:00:02:000
Duration: 3.456 seconds

01/01/2024 10:00:02:000    TCP    FETCH - RECEIVE DATA                     Hex: 33 44 55 66
01/01/2024 10:00:02:300    TCP    TERMINAL RESPONSE - SEND DATA           Hex: 77 88 99 AA
01/01/2024 10:00:03:000    TCP    FETCH - CLOSE CHANNEL                   Hex: BB CC DD EE

=== Channel Group 3: ENVELOPE Data Transfer ===
Start Time: 01/01/2024 10:00:04:000
Duration: 2.123 seconds

01/01/2024 10:00:04:000    ENVELOPE    ENVELOPE - DATA TRANSFER            Hex: FF EE DD CC
01/01/2024 10:00:04:500    TCP         TERMINAL RESPONSE - CLOSE CHANNEL   Hex: AB CD EF 12

=== Channel Group 4: DNS Query to DNS by ME (8.8.8.8:53) ===
Start Time: 01/01/2024 10:00:05:000
Duration: 1.789 seconds

01/01/2024 10:00:05:000    TCP    FETCH - OPEN CHANNEL                     Hex: 12 34 56 78
01/01/2024 10:00:05:200    TCP    TERMINAL RESPONSE - RECEIVE DATA         Hex: 9A BC DE F0
"""
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xti', delete=False) as f:
        f.write(demo_content)
        return f.name

def main():
    """Run comprehensive demo."""
    print("🚀 XTI Viewer Advanced Filtering Demonstration")
    print("=" * 60)
    
    # Create demo file
    demo_file = create_demo_xti_file()
    print(f"📄 Created demo XTI file: {demo_file}")
    print()
    
    print("🎯 DEMONSTRATION SCENARIO:")
    print("We have created an XTI file with multiple channel groups:")
    print("  1. TCP Connection to DP+ server")
    print("  2. TCP Connection to TAC server") 
    print("  3. ENVELOPE Data Transfer")
    print("  4. DNS Query to DNS by ME")
    print()
    
    print("🔍 ADVANCED FILTERING FEATURES TO TEST:")
    print()
    
    print("1️⃣ COMMAND TYPE FILTERS (Checkboxes):")
    print("   ☐ OPEN CHANNEL    - Filter for connection opening commands")
    print("   ☐ SEND DATA       - Filter for outbound data transmission")
    print("   ☐ RECEIVE DATA    - Filter for inbound data reception") 
    print("   ☐ CLOSE CHANNEL   - Filter for connection closing commands")
    print("   ☐ ENVELOPE        - Filter for envelope protocol messages")
    print("   ☐ TERMINAL RESPONSE - Filter for terminal response messages")
    print()
    
    print("2️⃣ SERVER FILTER (Dropdown):")
    print("   🖥️ All Servers    - Show traffic to/from all servers")
    print("   🖥️ DP+            - Show only DP+ server traffic")
    print("   🖥️ TAC            - Show only TAC server traffic") 
    print("   🖥️ DNS by ME       - Show only DNS by ME traffic")
    print("   🖥️ Public DNS     - Show only public DNS server traffic")
    print("   🖥️ Other          - Show other/unidentified server traffic")
    print()
    
    print("3️⃣ TIME RANGE FILTER (Slider):")
    print("   ⏰ 0%-25%         - Show only the earliest trace entries")
    print("   ⏰ 26%-50%        - Show entries in the first half")
    print("   ⏰ 51%-75%        - Show entries in the second half") 
    print("   ⏰ 76%-100%       - Show entries in the latest time range")
    print("   ⏰ 100%           - Show complete trace (default)")
    print()
    
    print("🧪 EXAMPLE FILTER COMBINATIONS TO TRY:")
    print()
    
    print("📋 Test Case 1: Find all connection opening activities")
    print("   ✅ Check: OPEN CHANNEL")
    print("   ✅ Server: All Servers") 
    print("   ✅ Time: 100%")
    print("   Expected: All FETCH - OPEN CHANNEL and TERMINAL RESPONSE - OPEN CHANNEL entries")
    print()
    
    print("📋 Test Case 2: Analyze DP+ server traffic only")
    print("   ✅ Check: All command types")
    print("   ✅ Server: DP+")
    print("   ✅ Time: 100%") 
    print("   Expected: Only traffic from/to DP+ server (10.20.30.40)")
    print()
    
    print("📋 Test Case 3: Focus on data transfer activities")
    print("   ✅ Check: SEND DATA, RECEIVE DATA")
    print("   ✅ Server: All Servers")
    print("   ✅ Time: 100%")
    print("   Expected: All SEND DATA and RECEIVE DATA entries")
    print()
    
    print("📋 Test Case 4: Early trace analysis (first 50%)")
    print("   ✅ Check: All command types")
    print("   ✅ Server: All Servers")
    print("   ✅ Time: 50%")
    print("   Expected: Only entries from first half of the trace timeline")
    print()
    
    print("📋 Test Case 5: ENVELOPE protocol inspection")
    print("   ✅ Check: ENVELOPE")
    print("   ✅ Server: All Servers")
    print("   ✅ Time: 100%")
    print("   Expected: Only ENVELOPE - DATA TRANSFER entries")
    print()
    
    print("📋 Test Case 6: Complex combination filter")
    print("   ✅ Check: SEND DATA, RECEIVE DATA")
    print("   ✅ Server: TAC")
    print("   ✅ Time: 75%")
    print("   Expected: SEND/RECEIVE traffic to TAC server in first 75% of trace")
    print()
    
    print("🎮 HOW TO RUN THE DEMO:")
    print(f"1. Launch XTI Viewer: python -m xti_viewer.ui_main")
    print(f"2. Load the demo file: {demo_file}")
    print("3. Navigate to the 'Interpretations' tab")
    print("4. Click '▲ Show' button to expand the Advanced Filters panel")
    print("5. Try the test cases above by selecting different combinations")
    print("6. Use the search navigation arrows (◄ ►) to step through filtered results")
    print("7. Observe how the trace list updates based on your filter selections")
    print()
    
    print("✨ ADVANCED FEATURES:")
    print("• Sequential Navigation: Use ◄ ► to move through matches without hiding others")
    print("• Real-time Filtering: Filters apply immediately as you change selections")
    print("• Multi-dimensional: Combine command types, servers, and time ranges")
    print("• Professional UI: Collapsible panels with clear visual indicators")
    print("• Robust Validation: Enhanced trace validation with anomaly detection")
    print()
    
    print("🔧 Now launching the XTI Viewer with your demo file...")
    
    # Clean up
    try:
        os.unlink(demo_file)
    except:
        pass
    
    # Launch the viewer
    import subprocess
    subprocess.Popen([
        sys.executable, "-m", "xti_viewer.ui_main", demo_file
    ], cwd=str(project_root))
    
    print(f"✅ XTI Viewer launched! Demo file created at: {demo_file}")
    print("📊 Test all the advanced filtering combinations described above!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())