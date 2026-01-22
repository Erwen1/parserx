# XTI Viewer Protocol Analyzer Enhancement

## Overview

The XTI viewer has been significantly enhanced with comprehensive protocol analysis capabilities specifically designed for SGP.32-style RSP traffic analysis. This enhancement adds deep packet inspection and protocol-aware analysis to SEND/RECEIVE DATA payloads.

## New Features

### 🔒 1. TLS Handshake Analyzer

**Capabilities:**
- **TLS Record Detection**: Recognizes TLS records (types 0x16, 0x17, 0x15, 0x14) with versions TLS 1.0-1.3
- **ClientHello Analysis**: Parses TLS version, cipher suites, extensions, and session information
- **SNI Extraction**: Extracts Server Name Indication hostnames from ClientHello messages
- **ServerHello Analysis**: Parses server responses including chosen cipher suite and extensions
- **Compliance Checking**: Validates against SGP.32 requirements (TLS ≥1.2, approved cipher suites)

**SGP.32 Compliance Features:**
- Marks TLS versions < 1.2 as non-compliant
- Validates cipher suites against SGP.32 approved list
- Reports compliance issues in the analysis warnings

### 🎯 2. SNI-Based Channel Role Auto-Detection

**Hostname Pattern Mapping:**
- `*smdp*`, `*smdpplus*` → **SM-DP+**
- `*smds*` → **SM-DS** 
- `*eim*`, `*dpplus*` → **eIM / DP+**
- `*tac.*` → **TAC**
- `*thales*` → **TAC**

**Integration:**
- Works alongside existing IP-based classification
- SNI-based detection takes priority over IP-based when both are available
- Automatically populates the new "Role" column in Channel Groups table
- Displays role information in the Analyze tab summary

### 🌐 3. DNS Decoder

**Features:**
- **Message Parsing**: Decodes DNS headers, questions, answers, nameservers, and additional records
- **Record Type Support**: A, AAAA, NS, CNAME, MX, TXT, SRV, PTR, SOA records
- **UDP 53 Detection**: Automatically applies DNS analysis to UDP port 53 channels
- **IP Resolution Display**: Shows resolved IPv4/IPv6 addresses with TTL information

**Analysis Output:**
- Transaction ID and message type (Query/Response)
- Question sections with domain names and query types
- Answer sections with resolved IPs and TTL values
- Integration with existing server mapping

### 📊 4. ASN.1/BER Structure Detection

**Detection Logic:**
- Identifies BER/DER structures starting with SEQUENCE (0x30), SET (0x31)
- Recognizes context-specific tags (A1, A2, etc.)
- Detects private tags (BF 39, BF 3A, BF 3B, BF 4F, etc.)

**Analysis Output:**
- Top-level tag enumeration with lengths
- Structured display of ASN.1 hierarchy
- Tag classification (SEQUENCE, Context-specific, Private)

### 📄 5. JSON Message Analysis

**Features:**
- **Auto-Detection**: Identifies JSON-like payloads starting with `{`
- **Validation**: Parses and validates JSON structure
- **Key Field Extraction**: Highlights important fields like `function`, `transactionId`, `resultCode`, `notificationType`
- **Pretty Display**: Formatted JSON output in the Analyze tab

### 🔐 6. X.509 Certificate Chain Parser

**Parsing Capabilities:**
- **Certificate Extraction**: Parses certificate chains from TLS Certificate handshake messages
- **Basic Info**: Extracts Subject CN, Issuer CN, validity periods
- **Public Key Info**: Identifies key types (RSA, EC P-256, etc.)
- **Chain Validation**: Checks certificate validity periods and chain length

**Validation Features:**
- Marks certificates outside validity period
- Identifies self-signed vs multi-level chains
- Reports certificate chain issues

### 🔍 7. Comprehensive Payload Classifier

**Supported Types:**
- **TLS**: ClientHello, ServerHello, Certificate, Application Data
- **DNS**: Query and Response messages
- **HTTP**: Requests and Responses with Content-Type extraction
- **JSON**: Structured message validation
- **ASN.1/BER**: Tag-based structure detection
- **Binary**: Unknown binary data classification

**Media Type Detection:**
- Extracts Content-Type from HTTP headers
- Infers media types from payload structure
- Supports SGP.32 media types (application/vnd.eim+asn1, etc.)

## UI Integration

### 📋 Enhanced Analyze Tab

**New Sections:**
- **Protocol Analysis**: Top-level protocol classification and role information
- **TLS Handshake**: Version, cipher suites, SNI, extensions, compliance status
- **DNS Message**: Questions, answers, transaction details
- **Certificate Chain**: Subject/issuer details, validity periods
- **JSON Message**: Parsed content with key field highlighting
- **ASN.1 Structure**: Tag hierarchy and structure analysis

**Enhanced Features:**
- Protocol information in summary header
- Compliance warnings integration
- Media type display
- Channel role indication

### 📊 Enhanced Channel Groups Table

**New Column:**
- **Role**: Auto-detected channel role (SM-DP+, TAC, DP+, eIM, SM-DS, Unknown)

**Role Detection Priority:**
1. **SNI-based**: From TLS ClientHello hostname analysis
2. **IP-based**: Existing IP pattern matching
3. **Unknown**: When no pattern matches

### ⚡ Performance Optimizations

- **Lazy Analysis**: Protocol analysis only performed on SEND/RECEIVE DATA items
- **Caching**: Results cached to avoid re-analysis
- **Selective Processing**: Only analyzes first 20 items per session for role detection
- **Error Handling**: Graceful fallback when analysis fails

## Technical Implementation

### Core Modules

1. **protocol_analyzer.py**: Main analysis engine with all protocol parsers
2. **Enhanced models.py**: Session analysis with role detection integration
3. **Enhanced ui_main.py**: UI integration and display logic

### Key Classes

- `ProtocolAnalyzer`: Main analysis coordinator
- `TlsAnalyzer`: TLS handshake and record parsing
- `DnsAnalyzer`: DNS message decoding
- `CertificateAnalyzer`: X.509 certificate parsing
- `ChannelRoleDetector`: SNI-based role detection
- `AnalysisResult`: Comprehensive analysis result container

### Integration Points

- **Payload Extraction**: From TLV structures in SEND/RECEIVE DATA APDUs
- **Channel Session Tracking**: Enhanced with role detection during analysis
- **UI Updates**: Real-time protocol analysis in Analyze tab
- **Channel Groups**: Automatic role population from detected sessions

## Usage Instructions

### 📁 Loading and Analysis

1. **Load XTI File**: Load any XTI file containing SEND/RECEIVE DATA commands
2. **Channel Groups**: Check the "Channel Groups" tab for auto-detected roles
3. **Item Selection**: Select any SEND/RECEIVE DATA item in the main trace
4. **Protocol Analysis**: View the "Analyze" tab for detailed protocol breakdown
5. **Role Information**: Look for channel role in summary and protocol sections

### 🔍 Analysis Features

- **TLS Traffic**: Automatic detection and analysis of TLS handshakes
- **DNS Traffic**: UDP port 53 traffic automatically analyzed as DNS
- **JSON Messages**: Plain JSON content parsed and validated
- **ASN.1 Structures**: BER/DER encoded data automatically detected
- **HTTP Traffic**: Basic HTTP request/response parsing

### 🛡️ Compliance Checking

- **TLS Version**: Warns if TLS version < 1.2
- **Cipher Suites**: Validates against SGP.32 approved cipher list
- **Certificate Validity**: Checks certificate expiration and chain structure
- **Protocol Recommendations**: Provides SGP.32 compliance guidance

## Benefits for SGP.32 Analysis

### 🎯 Improved Channel Classification

- **Automatic Role Detection**: No manual classification needed
- **SNI-Based Accuracy**: More reliable than IP-based classification alone
- **Multi-Source Validation**: Combines IP and SNI information

### 🔒 Security Analysis

- **TLS Configuration Review**: Validates TLS settings against SGP.32 requirements
- **Certificate Chain Analysis**: Ensures proper PKI setup
- **Compliance Monitoring**: Automatic flagging of non-compliant configurations

### 📊 Enhanced Debugging

- **Protocol-Aware Analysis**: Understanding of higher-layer protocols
- **Structured Data Display**: Clear presentation of complex protocol data
- **Error Detection**: Identification of malformed or non-compliant traffic

### ⚡ Workflow Efficiency

- **Automatic Analysis**: No manual protocol decoding needed
- **Integrated Display**: All analysis in unified interface
- **Export Capabilities**: Enhanced channel groups with role information

## Technical Notes

### Requirements

- No additional dependencies required
- Pure Python implementation
- Compatible with existing XTI viewer codebase

### Limitations

- **Simplified X.509 Parsing**: Basic certificate info only (no full ASN.1 decoder)
- **TLS Record Assembly**: Single-record analysis only (no fragmentation support)
- **DNS Compression**: Basic support for DNS name compression
- **ASN.1 Parsing**: Tag-level analysis only (no semantic decoding)

### Future Enhancements

- **Complete X.509 Parser**: Full certificate validation with cryptographic verification
- **TLS Session Reconstruction**: Multi-record TLS session analysis
- **APDU-Level Integration**: Direct integration with APDU command structure
- **Custom Role Patterns**: User-configurable hostname-to-role mapping

---

## Summary

This enhancement transforms the XTI viewer from a basic trace analyzer into a comprehensive SGP.32-aware protocol analysis tool. The automatic role detection, TLS compliance checking, and structured protocol analysis significantly improve the efficiency and accuracy of RSP traffic analysis.

The implementation maintains backward compatibility while adding powerful new analysis capabilities that integrate seamlessly with the existing workflow. Users can now quickly identify channel roles, validate TLS configurations, and analyze complex protocol interactions with minimal manual effort.