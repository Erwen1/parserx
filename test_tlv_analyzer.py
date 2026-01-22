#!/usr/bin/env python3
"""
Test script for the TLV Analyzer functionality.
"""

from xti_viewer.apdu_parser_construct import parse_apdu


def test_tlv_analyzer():
    """Test the TLV analyzer with sample APDUs."""
    
    # Test cases with different types of APDUs
    test_cases = [
        {
            "name": "Command APDU",
            "hex": "8100000003400101",
            "expected_tlvs": 1
        },
        {
            "name": "Response with TLVs",
            "hex": "81030140018201828083018000",
            "expected_contains": ["Command Details", "Device Identity", "Result"]
        },
        {
            "name": "FETCH command", 
            "hex": "801200000D81030101008202818383010000",
            "expected_ins": "FETCH"
        }
    ]
    
    print("🧪 Testing TLV Analyzer...")
    print("=" * 60)
    
    for test in test_cases:
        print(f"\n📋 Test: {test['name']}")
        print(f"   Hex: {test['hex']}")
        
        try:
            result = parse_apdu(test['hex'])
            
            print(f"   Summary: {result.summary}")
            print(f"   INS: {result.ins_name}")
            print(f"   TLVs found: {len(result.tlvs)}")
            
            if result.warnings:
                print(f"   ⚠️  Warnings: {', '.join(result.warnings)}")
            
            # Show TLV details
            for i, tlv in enumerate(result.tlvs):
                print(f"     TLV {i+1}: {tlv.tag_hex} ({tlv.name}) = {tlv.decoded_value}")
                if tlv.children:
                    for child in tlv.children:
                        print(f"       └─ {child.tag_hex} ({child.name}) = {child.decoded_value}")
            
            # Validate expected results
            if "expected_tlvs" in test:
                assert len(result.tlvs) >= test["expected_tlvs"], f"Expected at least {test['expected_tlvs']} TLVs, got {len(result.tlvs)}"
            
            if "expected_contains" in test:
                found_names = [tlv.name for tlv in result.tlvs]
                for expected in test["expected_contains"]:
                    assert any(expected in name for name in found_names), f"Expected to find '{expected}' in TLV names"
            
            if "expected_ins" in test:
                assert result.ins_name == test["expected_ins"], f"Expected INS '{test['expected_ins']}', got '{result.ins_name}'"
            
            print("   ✅ Test passed!")
            
        except Exception as e:
            print(f"   ❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
    
    # Test with real data from XTI file
    print(f"\n📋 Test: Real XTI file data")
    try:
        from xti_viewer.xti_parser import XTIParser
        parser = XTIParser()
        trace_items = parser.parse_file('BC660K_enable_OK.xti')
        
        tested_count = 0
        for item in trace_items[:10]:
            if item.rawhex and len(item.rawhex) > 8:
                print(f"\n   Testing: {item.summary}")
                print(f"   Hex: {item.rawhex[:20]}...")
                
                result = parse_apdu(item.rawhex)
                print(f"   Parsed as: {result.summary}")
                print(f"   TLVs: {len(result.tlvs)}")
                
                tested_count += 1
                if tested_count >= 3:  # Test first 3 valid items
                    break
        
        print("   ✅ Real data test passed!")
        
    except Exception as e:
        print(f"   ❌ Real data test failed: {e}")


if __name__ == "__main__":
    test_tlv_analyzer()
    print("\n🎉 TLV Analyzer testing complete!")