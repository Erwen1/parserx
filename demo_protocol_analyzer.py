#!/usr/bin/env python3
"""
Demo script showcasing the enhanced XTI viewer protocol analysis capabilities.

This script demonstrates the new features added to the XTI viewer:
- TLS handshake analysis with ClientHello/ServerHello parsing
- SNI hostname extraction and channel role auto-detection  
- DNS message decoding for UDP 53 channels
- ASN.1/BER structure detection
- JSON message parsing and validation
- X.509 certificate chain analysis
- Payload classification and media type detection
- Enhanced Analyze tab with protocol sections
- Channel Groups table with Role column
"""

import sys
import os
from xti_viewer.protocol_analyzer import (
    ProtocolAnalyzer, TlsAnalyzer, DnsAnalyzer, ChannelRoleDetector,
    PayloadType, TlsHandshakeInfo, DnsInfo
)

def demo_tls_analysis():
    """Demo TLS ClientHello analysis and SNI extraction"""
    print("🔒 TLS Handshake Analysis Demo")
    print("=" * 50)
    
    # Sample TLS ClientHello (simplified for demo)
    # Real TLS ClientHello would be much longer
    sample_tls_data = bytes([
        0x16, 0x03, 0x03, 0x00, 0xCA,  # TLS Record Header (Handshake, TLS 1.2, Length)
        0x01, 0x00, 0x00, 0xC6,        # Handshake Header (ClientHello, Length)
        0x03, 0x03,                    # TLS Version (1.2)
        # 32 bytes random
        0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
        0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10,
        0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18,
        0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F, 0x20,
        0x00,  # Session ID length
        0x00, 0x08,  # Cipher suites length
        0xC0, 0x2F, 0xC0, 0x30, 0x13, 0x01, 0x13, 0x02,  # Some cipher suites
        0x01, 0x00,  # Compression methods (NULL)
        0x00, 0x30,  # Extensions length
        # SNI Extension
        0x00, 0x00, 0x00, 0x20,  # Extension type 0 (SNI), length
        0x00, 0x1E,  # Server name list length
        0x00,        # Server name type (hostname)
        0x00, 0x1B,  # Hostname length
    ])
    
    # Add hostname "tac.thalescloud.io"
    hostname = b"tac.thalescloud.io"
    sample_tls_data += hostname
    
    # Analyze the TLS data
    tls_info = TlsAnalyzer.parse_client_hello(sample_tls_data)
    
    if tls_info:
        print(f"✅ TLS Version: {tls_info.version}")
        print(f"📋 Cipher Suites: {len(tls_info.cipher_suites)} offered")
        for i, suite in enumerate(tls_info.cipher_suites[:3]):
            print(f"   {i+1}. {suite}")
        print(f"🌐 SNI Hostname: {tls_info.sni_hostname}")
        print(f"🔧 Extensions: {', '.join(tls_info.extensions)}")
        print(f"✅ SGP.32 Compliant: {'Yes' if tls_info.compliance_ok else 'No'}")
        if not tls_info.compliance_ok:
            print(f"⚠️  Issues: {', '.join(tls_info.compliance_issues)}")
        
        # Demo role detection
        if tls_info.sni_hostname:
            role = ChannelRoleDetector.detect_role_from_sni(tls_info.sni_hostname)
            print(f"🎯 Detected Channel Role: {role or 'Unknown'}")
    else:
        print("❌ Failed to parse TLS ClientHello")
    
    print()

def demo_dns_analysis():
    """Demo DNS message analysis"""
    print("🌐 DNS Message Analysis Demo")
    print("=" * 50)
    
    # Sample DNS query for "tac.thalescloud.io" (simplified)
    sample_dns_data = bytes([
        0x12, 0x34,  # Transaction ID
        0x01, 0x00,  # Flags (standard query)
        0x00, 0x01,  # Questions: 1
        0x00, 0x00,  # Answers: 0
        0x00, 0x00,  # Authority RRs: 0
        0x00, 0x00,  # Additional RRs: 0
        # Question: tac.thalescloud.io
        0x03, 0x74, 0x61, 0x63,  # "tac"
        0x0B, 0x74, 0x68, 0x61, 0x6C, 0x65, 0x73, 0x63, 0x6C, 0x6F, 0x75, 0x64,  # "thalescloud"
        0x02, 0x69, 0x6F,  # "io"
        0x00,  # End of name
        0x00, 0x01,  # Type A
        0x00, 0x01,  # Class IN
    ])
    
    dns_info = DnsAnalyzer.parse_dns_message(sample_dns_data, is_udp53=True)
    
    if dns_info:
        print(f"📨 Transaction ID: 0x{dns_info.transaction_id:04X}")
        print(f"❓ Message Type: {'Query' if dns_info.is_query else 'Response'}")
        print(f"❓ Questions ({len(dns_info.questions)}):")
        for q in dns_info.questions:
            print(f"   • {q['name']} ({q['type']})")
        
        if dns_info.answers:
            print(f"📋 Answers ({len(dns_info.answers)}):")
            for a in dns_info.answers:
                print(f"   • {a['name']} -> {a['data']} (TTL: {a['ttl']}s)")
    else:
        print("❌ Failed to parse DNS message")
    
    print()

def demo_channel_role_detection():
    """Demo channel role detection from hostnames"""
    print("🎯 Channel Role Detection Demo")
    print("=" * 50)
    
    test_hostnames = [
        "tac.thalescloud.io",
        "smdpplus.example.com", 
        "api.smdp.carrier.net",
        "smds.operator.com",
        "eim-service.provider.org",
        "dpplus.backend.net",
        "unknown.service.com"
    ]
    
    for hostname in test_hostnames:
        role = ChannelRoleDetector.detect_role_from_sni(hostname)
        print(f"🌐 {hostname:<25} → {role or 'Unknown'}")
    
    print()

def demo_payload_classification():
    """Demo comprehensive payload classification"""
    print("📊 Payload Classification Demo")
    print("=" * 50)
    
    test_payloads = [
        (b'{"function":"downloadOrder","transactionId":"123"}', "JSON Message"),
        (b'\x30\x82\x01\x23\x30\x82\x00\xAB', "ASN.1 Structure"),
        (b'GET /api/v1/orders HTTP/1.1\r\nHost: server.com\r\n', "HTTP Request"),
        (b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n', "HTTP Response"),
        (b'\x16\x03\x03\x00\x50\x01\x00\x00\x4C', "TLS Handshake"),
        (b'\x17\x03\x03\x00\x20', "TLS Application Data"),
        (b'\xDE\xAD\xBE\xEF\x12\x34', "Binary Data")
    ]
    
    for payload, expected_type in test_payloads:
        analysis = ProtocolAnalyzer.analyze_payload(payload)
        print(f"📦 {expected_type:<20} → {analysis.raw_classification}")
        if analysis.media_type:
            print(f"   📄 Media Type: {analysis.media_type}")
    
    print()

def demo_integration_features():
    """Demo integration features in XTI viewer"""
    print("🔗 XTI Viewer Integration Features")
    print("=" * 50)
    
    print("✨ Enhanced Analyze Tab:")
    print("   • TLS Handshake section with version, cipher suites, SNI")
    print("   • DNS Message section with queries and answers")
    print("   • Certificate Chain section with subject/issuer info")
    print("   • JSON Message section with key field extraction")
    print("   • ASN.1/BER Structure section with tag analysis")
    print("   • Protocol compliance warnings and recommendations")
    print()
    
    print("📋 Enhanced Channel Groups Table:")
    print("   • New 'Role' column showing detected channel role")
    print("   • Auto-detection from SNI hostnames in TLS handshakes") 
    print("   • Integration with existing IP-based classification")
    print("   • Role priority: SNI-based > IP-based > Unknown")
    print()
    
    print("🚀 SGP.32 Compliance Features:")
    print("   • TLS version validation (requires ≥ TLS 1.2)")
    print("   • Cipher suite compliance checking")
    print("   • Certificate chain validation")
    print("   • RSP traffic pattern recognition")
    print()

def main():
    """Run all protocol analyzer demos"""
    print("🔬 XTI Viewer Protocol Analyzer Demo")
    print("=" * 60)
    print("Showcasing enhanced protocol analysis capabilities")
    print("for SGP.32-style RSP traffic analysis.")
    print("=" * 60)
    print()
    
    try:
        demo_tls_analysis()
        demo_dns_analysis() 
        demo_channel_role_detection()
        demo_payload_classification()
        demo_integration_features()
        
        print("🎉 All demos completed successfully!")
        print()
        print("💡 To use these features:")
        print("   1. Load an XTI file with SEND/RECEIVE DATA commands")
        print("   2. Check the 'Channel Groups' tab for auto-detected roles")
        print("   3. Select a SEND/RECEIVE DATA item in the trace")
        print("   4. View the 'Analyze' tab for protocol analysis")
        print("   5. Look for TLS, DNS, JSON, or ASN.1 sections")
        
    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()