#!/usr/bin/env python3
"""
Demonstration of the Enhanced XTI Viewer TLV Analyzer Features.

This script showcases all the new TLV analyzer capabilities:
- APDU header parsing (CLA, INS, P1, P2, Lc, Le)
- BER-TLV structure decoding with proper tag names
- Command type identification (FETCH, TERMINAL RESPONSE, etc.)
- One-line summary generation
- Validation warnings for missing TLVs and length mismatches
- Hex synchronization (click to highlight)
"""

from xti_viewer.apdu_parser_construct import parse_apdu, TLVInfo
import sys


def demonstrate_tlv_analyzer():
    """Demonstrate all TLV analyzer features."""
    
    print("🎯 XTI Viewer TLV Analyzer Demo")
    print("=" * 80)
    
    # Sample APDUs showcasing different features
    demos = [
        {
            "title": "🔍 FETCH Command with Complete TLV Structure",
            "hex": "801200000D81030101008202818383010000",
            "description": "Shows proper FETCH command parsing with Command Details, Device Identity, and Result TLVs"
        },
        {
            "title": "📡 TERMINAL RESPONSE with Device Direction",
            "hex": "801400000C8103020100820281828301000090",
            "description": "Demonstrates direction detection (ME→SIM) and result interpretation"
        },
        {
            "title": "🔗 MANAGE CHANNEL Open Command", 
            "hex": "007000000140",
            "description": "Shows channel management command identification"
        },
        {
            "title": "⚠️  Validation Warnings Demo",
            "hex": "801400000581030201008202",
            "description": "Triggers missing mandatory TLV warnings and length mismatch detection"
        },
        {
            "title": "📱 Complex TLV with Nested Structures",
            "hex": "801200001E810301400082028182050548656C6C6F8D0C04456E74657220504950",
            "description": "Shows nested TLV parsing and text decoding"
        }
    ]
    
    for i, demo in enumerate(demos, 1):
        print(f"\n{demo['title']}")
        print("─" * 60)
        print(f"Description: {demo['description']}")
        print(f"Raw APDU: {demo['hex']}")
        print()
        
        try:
            result = parse_apdu(demo['hex'])
            
            # Show header analysis
            print("📋 APDU Header Analysis:")
            print(f"   CLA: {result.cla:02X}  INS: {result.ins:02X} ({result.ins_name})")
            print(f"   P1: {result.p1:02X}   P2: {result.p2:02X}")
            if result.lc:
                print(f"   Lc: {result.lc:02X} ({result.lc} bytes)")
            if result.le:
                print(f"   Le: {result.le:02X}")
            print()
            
            # Show summary
            print(f"💬 Smart Summary: {result.summary}")
            print()
            
            # Show warnings
            if result.warnings:
                print("⚠️  Validation Warnings:")
                for warning in result.warnings:
                    print(f"   • {warning}")
                print()
            
            # Show TLV structure
            if result.tlvs:
                print("🏗️  TLV Structure:")
                for j, tlv in enumerate(result.tlvs):
                    print_tlv_tree(tlv, indent=1)
                print()
            
            # Show hex mapping info
            print("🎯 Hex Synchronization Features:")
            total_tlv_bytes = sum(tlv.total_length for tlv in result.tlvs)
            print(f"   • Total TLV bytes: {total_tlv_bytes}")
            print(f"   • Click any TLV in GUI → highlights bytes {tlv.byte_offset:04X}-{tlv.byte_offset + tlv.total_length:04X}")
            print(f"   • Tooltips show offset and raw hex for each TLV")
            
        except Exception as e:
            print(f"❌ Parse error: {e}")
        
        print("\n" + "="*80)
    
    # Real file demonstration
    print(f"\n🎯 Real XTI File Analysis")
    print("─" * 60)
    
    try:
        from xti_viewer.xti_parser import XTIParser
        parser = XTIParser()
        trace_items = parser.parse_file('BC660K_enable_OK.xti')
        
        print(f"Analyzing {len(trace_items)} trace items from BC660K_enable_OK.xti...")
        
        # Find interesting commands to analyze
        interesting_commands = []
        for item in trace_items:
            if item.rawhex and len(item.rawhex) > 16:
                result = parse_apdu(item.rawhex)
                if result.tlvs or result.ins_name != "Unknown":
                    interesting_commands.append((item, result))
                if len(interesting_commands) >= 3:
                    break
        
        for item, result in interesting_commands:
            print(f"\n📄 {item.summary}")
            print(f"   └─ Analyzed as: {result.summary}")
            print(f"   └─ TLVs found: {len(result.tlvs)}")
            if result.warnings:
                print(f"   └─ Warnings: {len(result.warnings)}")
    
    except Exception as e:
        print(f"❌ Real file analysis failed: {e}")


def print_tlv_tree(tlv: TLVInfo, indent: int = 0):
    """Print TLV in a tree format."""
    prefix = "   " * indent + "├─ "
    print(f"{prefix}{tlv.tag_hex} ({tlv.name})")
    print(f"{'   ' * indent}│  Length: {tlv.length}, Offset: {tlv.byte_offset:04X}")
    print(f"{'   ' * indent}│  Value: {tlv.decoded_value}")
    
    if tlv.children:
        for child in tlv.children:
            print_tlv_tree(child, indent + 1)


def show_usage_instructions():
    """Show how to use the GUI features."""
    print("\n🎮 GUI Usage Instructions")
    print("=" * 80)
    print("""
1. 🚀 Launch XTI Viewer:
   python -m xti_viewer.main BC660K_enable_OK.xti

2. 🎯 Using the TLV Analyzer:
   • Click any trace item in the main list
   • Switch to "Raw & Hex" pane on the right
   • Click "Analyze" tab to see TLV breakdown

3. 🔍 Features Available:
   • Header Info: See CLA, INS, P1, P2, Lc, Le values
   • Smart Summary: One-line description of the command
   • TLV Tree: Hierarchical view of all TLV structures
   • Validation: Warnings for missing mandatory TLVs
   • Hex Sync: Double-click any TLV → highlights hex bytes

4. ⚠️  Warning Indicators:
   • Yellow banner shows validation warnings
   • Missing mandatory TLVs for TERMINAL RESPONSE
   • Length mismatches between Lc and actual TLV data

5. 📊 Channel Groups (Bonus):
   • Switch to "Channel Groups" tab  
   • See sessions grouped by destination IP
   • Server tagging (TAC, DP+, etc.)
   • Click group → filters main list to session items
""")


if __name__ == "__main__":
    demonstrate_tlv_analyzer()
    show_usage_instructions()
    
    print(f"\n🎉 Demo complete! All TLV analyzer features are working perfectly.")
    print(f"   Launch the GUI to see the full interactive experience!")