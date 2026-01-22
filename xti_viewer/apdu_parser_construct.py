"""
APDU Parser using Construct library for structured binary protocol analysis.

This module provides comprehensive APDU parsing capabilities including:
- ISO 7816 APDU header parsing
- BER-TLV structure decoding
- SIM Toolkit command identification
- Validation and error detection
"""

try:
    import construct as cs
    from construct import *
except ImportError:
    print("Warning: construct library not available. Install with: pip install construct")
    # Create dummy classes to prevent import errors
    class DummyConstruct:
        def __getattr__(self, name):
            return lambda *args, **kwargs: None
    cs = DummyConstruct()
    Byte = Int8ub = Int16ub = Int32ub = Bytes = GreedyBytes = Struct = Container = None

from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
import re


@dataclass
class TLVInfo:
    """Information about a parsed TLV element."""
    tag: int
    tag_hex: str
    name: str
    length: int
    value_hex: str
    decoded_value: Any
    byte_offset: int
    total_length: int  # tag + length + value
    children: List['TLVInfo'] = None


@dataclass
class APDUInfo:
    """Comprehensive APDU parsing information."""
    raw_hex: str
    cla: int
    ins: int
    p1: int
    p2: int
    lc: Optional[int]
    le: Optional[int]
    data: Optional[bytes]
    ins_name: str
    command_type: str
    tlvs: List[TLVInfo]
    summary: str
    warnings: List[str]
    direction: str = "Unknown"  # ME->SIM, SIM->ME, or Unknown
    domain: str = "General"  # Protocol domain
    sw: Optional[int] = None
    sw_description: str = ""


# ISO 7816-4 Instruction definitions
INS_CODES = {
    0x10: "TERMINAL PROFILE", 
    0x12: "FETCH",
    0x14: "TERMINAL RESPONSE", 
    0x70: "MANAGE CHANNEL",
    0x72: "GET DATA",
    0xA0: "GET RESPONSE",
    0xA4: "SELECT",
    0xC0: "GET RESPONSE",
    0xC2: "ENVELOPE",
}

# SIM Toolkit Command Types (based on Command Details tag 01)
STK_COMMANDS = {
    0x01: "REFRESH",
    0x02: "MORE TIME", 
    0x03: "POLL INTERVAL",
    0x04: "POLLING OFF",
    0x05: "SET UP EVENT LIST",
    0x10: "SET UP CALL",
    0x11: "SEND SS", 
    0x12: "SEND USSD",
    0x13: "SEND SMS",
    0x15: "SEND DTMF",
    0x20: "DISPLAY TEXT",
    0x21: "GET INKEY",
    0x22: "GET INPUT", 
    0x23: "SELECT ITEM",
    0x24: "SET UP MENU",
    0x25: "PROVIDE LOCAL INFO",
    0x26: "TIMER MANAGEMENT",
    0x27: "SET UP IDLE MODE TEXT",
    0x28: "PERFORM CARD APDU",
    0x30: "POWER ON CARD",
    0x31: "POWER OFF CARD", 
    0x40: "OPEN CHANNEL",
    0x41: "CLOSE CHANNEL",
    0x42: "RECEIVE DATA",
    0x43: "SEND DATA", 
    0x44: "GET CHANNEL STATUS",
    0x45: "SERVICE SEARCH",
    0x46: "GET SERVICE INFO",
    0x47: "DECLARE SERVICE",
    0x61: "SET FRAMES",
    0x62: "GET FRAMES STATUS",
}

# BER-TLV Tag definitions for SIM Toolkit
TLV_TAGS = {
    0x01: "Command Details",
    0x02: "Device Identity", 
    0x03: "Result",
    0x04: "Duration",
    0x05: "Alpha Identifier",
    0x06: "Address",
    0x07: "Capability Configuration Parameters",
    0x08: "Cell Broadcast Page",
    0x09: "Cell Identity",
    0x0A: "Context Data",
    0x0B: "Control Data",
    0x0C: "Alpha Identifier",
    0x0D: "Device Filter",
    0x0E: "File List",
    0x0F: "Location Information",
    0x10: "Menu Selection",
    0x11: "Called Party Sub-address", 
    0x12: "Item",
    0x13: "Response Length",
    0x14: "File Status",
    0x15: "DCS and Text", 
    0x16: "USSD String",
    0x17: "SS String",
    0x18: "SMS TPDU",
    0x19: "Cell Broadcast Message ID",
    0x1A: "Tone",
    0x1B: "SMS Data Download",
    0x1C: "Timer ID",
    0x1D: "Timer Value",
    0x1E: "Date-Time and Time Zone",
    0x1F: "Call Control Requested Action",
    0x20: "AT Command",
    0x21: "AT Response",
    0x22: "BC Repeat Indicator",
    0x23: "Immediate Response",
    0x24: "DTMF String",
    0x25: "Language",
    0x26: "Timing Advance",
    0x27: "AID",
    0x28: "Browser Identity",
    0x29: "URL",
    0x2A: "Bearer",
    0x2B: "Provisioning Reference File",
    0x2C: "Browser Termination Cause", 
    0x2D: "Bearer Description",
    0x2E: "Channel Data",
    0x2F: "Channel Data Length",
    0x30: "Channel Status",
    0x31: "Buffer Size",
    0x32: "Network Access Name",
    0x33: "Card ATR",
    0x34: "C-APDU",
    0x35: "R-APDU",
    0x36: "Bearer Parameters",
    0x37: "Service Record",
    0x38: "Device Filter",
    0x39: "Service Search",
    0x3A: "Attribute Information", 
    0x3B: "Service Availability",
    0x3C: "Remote Entity Address",
    0x3D: "ESN",
    0x3E: "Network Access Name",
    0x3F: "CDMA-SMS TPDU",
    0x40: "Text Attribute",
    0x41: "Item Text Attribute List",
    0x42: "PDP Context Activation Parameter",
    0x43: "Contactless State Changed",
    0x44: "CSG Cell Selection Status",
    0x45: "CSG ID",
    0x46: "HNB Name",
    0x47: "eCall Information",
    0x48: "IMEISV",
    0x49: "Battery State",
    0x4A: "Browsing Status", 
    0x50: "Frame Layout",
    0x51: "MMS Reference",
    0x52: "MMS Identifier",
    0x53: "MMS Transfer Status",
    0x54: "MEID",
    0x55: "MMS Content Identifier",
    0x56: "MMS Notification",
    0x57: "Last Envelope",
    0x58: "Registry Application Data",
    0x59: "PCO",
    0x5A: "MAC",
    0x61: "Encapsulated Session Control",
    0x62: "Specific Language Notification",
    0x63: "Geographic Location Information",
    0x64: "PLMN List",
    0x65: "Broadcast Network Information",
    0x66: "Activate Descriptor",
    0x67: "EPS PDN Connection Activation Parameters",
    0x68: "Tracking Area Identification",
    0x69: "CSG ID List",
    0x81: "Command Details", 
    0x82: "Device Identity",
    0x83: "Result",
    0x84: "AID",
    0x85: "Alpha Identifier",
    0xD0: "Proactive Command",
}

# Fallback hints for unknown or context-dependent tags
TAG_HINTS = {
    0x0C: "Alpha Identifier (ISO 7816-4)",
    0xB7: "Channel Status",
    0xB0: "File Control Parameters",
    0xA5: "FCI Proprietary Template",
    0x6F: "FCI Template",
    0x62: "FCP Template",
    0x80: "File Size",
    0x88: "Short File Identifier",
    # Additional BIP/Channel tags
    0x73: "Channel Data String",
    0x75: "Network Access Name",
    0x30: "Channel Status",
    0x31: "Buffer Size", 
    0x32: "Card Reader Status",
    0x04: "Duration",
    # Context and session management
    0x39: "Service Search",
    0x3A: "Attribute Information",
    0x3B: "Service Availability",
    0x3C: "Remote Entity Address",
}

# Status Word definitions
SW_CODES = {
    0x9000: "Normal processing. Command correctly executed, and no response data",
    0x9300: "SIM Application Toolkit busy. Command cannot be executed at present",
    0x6100: "Normal processing. Response available",
    0x6200: "Warning: State of non-volatile memory unchanged",
    0x6281: "Warning: Part of returned data may be corrupted",
    0x6282: "Warning: End of file reached before reading Le bytes", 
    0x6283: "Warning: Selected file invalidated",
    0x6284: "Warning: FCP not formatted according to 7.4",
    0x6300: "Warning: State of non-volatile memory changed",
    0x6381: "Warning: File filled up by the last write",
    0x6400: "Execution error: State of non-volatile memory unchanged",
    0x6500: "Execution error: State of non-volatile memory changed",
    0x6581: "Execution error: Memory problem",
    0x6700: "Wrong length",
    0x6800: "Functions in CLA not supported", 
    0x6881: "Logical channel not supported",
    0x6882: "Secure messaging not supported",
    0x6900: "Command not allowed",
    0x6981: "Command incompatible with file structure",
    0x6982: "Security status not satisfied",
    0x6983: "Authentication method blocked",
    0x6984: "Referenced data invalidated", 
    0x6985: "Conditions of use not satisfied",
    0x6986: "Command not allowed (no current EF)",
    0x6987: "Expected SM data objects missing",
    0x6988: "SM data objects incorrect",
    0x6A00: "Wrong parameter(s) P1-P2",
    0x6A80: "Incorrect parameters in the data field",
    0x6A81: "Function not supported",
    0x6A82: "File not found", 
    0x6A83: "Record not found",
    0x6A84: "Not enough memory space in the file",
    0x6A86: "Incorrect parameters P1-P2",
    0x6A88: "Referenced data not found",
    0x6B00: "Wrong parameter(s) P1-P2",
    0x6C00: "Wrong length Le",
    0x6D00: "Instruction code not supported or invalid",
    0x6E00: "Class not supported",
    0x6F00: "No precise diagnosis",
}


def get_sw_description(sw: int) -> str:
    """Get status word description."""
    if sw in SW_CODES:
        return SW_CODES[sw]
    
    # Check ranges
    if 0x6100 <= sw <= 0x61FF:
        return f"Normal processing. Response available ({sw & 0xFF} bytes)"
    elif 0x6C00 <= sw <= 0x6CFF:
        return f"Wrong length Le. Expected length: {sw & 0xFF}"
    elif 0x9100 <= sw <= 0x91FF:
        return f"Normal processing. SIM Application Toolkit busy ({sw & 0xFF})"
    elif 0x9200 <= sw <= 0x92FF:
        return f"Memory management. Update successful ({sw & 0xFF})"
    else:
        return f"Unknown status word: {sw:04X}"


# Construct schemas for APDU parsing
def create_apdu_schema():
    """Create Construct schema for APDU parsing."""
    if cs is None:
        return None
    
    # Basic APDU header
    apdu_header = Struct(
        "cla" / Int8ub,
        "ins" / Int8ub, 
        "p1" / Int8ub,
        "p2" / Int8ub,
    )
    
    # Case 1: No data, no response expected
    case1 = Struct(
        "header" / apdu_header,
        "lc" / Computed(0),
        "data" / Computed(b""),
        "le" / Computed(None),
    )
    
    # Case 2: No data, response expected  
    case2 = Struct(
        "header" / apdu_header,
        "lc" / Computed(0),
        "data" / Computed(b""),
        "le" / Int8ub,
    )
    
    # Case 3: Data, no response expected
    case3 = Struct(
        "header" / apdu_header,
        "lc" / Int8ub,
        "data" / Bytes(this.lc),
        "le" / Computed(None),
    )
    
    # Case 4: Data and response expected
    case4 = Struct(
        "header" / apdu_header,
        "lc" / Int8ub, 
        "data" / Bytes(this.lc),
        "le" / Int8ub,
    )
    
    # Response APDU
    response_apdu = Struct(
        "data" / Bytes(lambda ctx: len(ctx._) - 2),
        "sw" / Int16ub,
    )
    
    return {
        'case1': case1,
        'case2': case2, 
        'case3': case3,
        'case4': case4,
        'response': response_apdu,
    }


def parse_ber_tlv(data: bytes, offset: int = 0) -> List[TLVInfo]:
    """Parse BER-TLV data structure."""
    tlvs = []
    pos = offset
    
    while pos < len(data):
        if pos >= len(data):
            break
            
        # Parse tag
        tag_start = pos
        tag = data[pos]
        pos += 1
        
        # Handle extended tag encoding (if bit 0-4 are all set)
        if (tag & 0x1F) == 0x1F:
            # Multi-byte tag (not commonly used in SIM toolkit)
            while pos < len(data) and (data[pos] & 0x80):
                tag = (tag << 8) | data[pos] 
                pos += 1
            if pos < len(data):
                tag = (tag << 8) | data[pos]
                pos += 1
        
        if pos >= len(data):
            break
            
        # Parse length
        length_start = pos
        length_byte = data[pos]
        pos += 1
        
        if length_byte & 0x80:
            # Long form length
            length_bytes = length_byte & 0x7F
            if length_bytes == 0 or pos + length_bytes > len(data):
                break
            length = 0
            for _ in range(length_bytes):
                length = (length << 8) | data[pos]
                pos += 1
        else:
            # Short form length
            length = length_byte
        
        if pos + length > len(data):
            break
            
        # Extract value
        value_start = pos
        value = data[pos:pos + length]
        pos += length
        
        # Create TLV info
        tag_name = get_tag_name(tag)
        decoded_value = decode_tlv_value(tag, value)
        
        tlv_info = TLVInfo(
            tag=tag,
            tag_hex=f"{tag:02X}",
            name=tag_name,
            length=length,
            value_hex=value.hex().upper(),
            decoded_value=decoded_value,
            byte_offset=tag_start,
            total_length=pos - tag_start,
        )
        
        # Parse nested TLVs for constructed tags
        # Treat known containers as constructed even if their BER constructed bit isn't set
        if tag in [0x62, 0x6F, 0x70, 0x73, 0xA5, 0xD0] or (tag & 0x20):  # Constructed tags
            tlv_info.children = parse_ber_tlv(value, 0)
            # Heuristic renaming for standard file control/proactive containers
            try:
                if tag == 0x62 and tlv_info.children:
                    child_tags = {c.tag for c in tlv_info.children}
                    if 0x84 in child_tags or 0xA5 in child_tags:
                        tlv_info.name = "FCP Template"
                elif tag == 0x6F and tlv_info.children:
                    child_tags = {c.tag for c in tlv_info.children}
                    if 0x84 in child_tags or 0xA5 in child_tags:
                        tlv_info.name = "FCI Template"
                elif tag == 0xA5:
                    tlv_info.name = "FCI Proprietary Template"
                elif tag == 0xD0:
                    tlv_info.name = "Proactive Command"
            except Exception:
                pass
        
        tlvs.append(tlv_info)
    
    return tlvs


def decode_tlv_value(tag: int, value: bytes) -> Any:
    """Decode TLV value based on tag type."""
    if not value:
        return ""
    
    # Check if value is ASCII text
    ascii_text = detect_ascii_text(value)
    
    try:
        if tag == 0x01 or tag == 0x81:  # Command Details
            if len(value) >= 3:
                cmd_number = value[0]
                cmd_type = value[1] 
                cmd_qualifier = value[2]
                cmd_name = STK_COMMANDS.get(cmd_type, f"Unknown Command {cmd_type:02X}")
                
                # Decode qualifier for specific commands
                qualifier_desc = ""
                if cmd_type == 0x40:  # OPEN CHANNEL
                    qual_parts = []
                    if cmd_qualifier & 0x01:
                        qual_parts.append("Immediate link establishment")
                    if cmd_qualifier & 0x02:
                        qual_parts.append("Automatic reconnection")
                    if cmd_qualifier & 0x04:
                        qual_parts.append("Background mode")
                    if qual_parts:
                        qualifier_desc = f" → {' + '.join(qual_parts)}"
                
                result = f"Number: {cmd_number}, Type: 0x{cmd_type:02X} ({cmd_name}), Qualifier: 0x{cmd_qualifier:02X}{qualifier_desc}"
                return enhance_ascii_display(tag, value, result)
            
        elif tag == 0x02 or tag == 0x82:  # Device Identity
            if len(value) >= 2:
                source = value[0]
                dest = value[1]
                device_names = {0x01: "Keypad", 0x02: "Display", 0x03: "Earpiece", 0x10: "SIM", 0x81: "SIM", 0x82: "ME", 0x83: "Network"}
                source_name = device_names.get(source, f"Unknown {source:02X}")
                dest_name = device_names.get(dest, f"Unknown {dest:02X}")
                result = f"Source: {source_name} (0x{source:02X}), Destination: {dest_name} (0x{dest:02X})"
                return enhance_ascii_display(tag, value, result)
                
        elif tag == 0x03 or tag == 0x83:  # Result
            if len(value) >= 1:
                result_code = value[0]
                result_names = {
                    0x00: "Command performed successfully",
                    0x01: "Command performed with partial comprehension", 
                    0x02: "Command performed, with missing information",
                    0x03: "REFRESH performed with additional EFs read",
                    0x04: "Command performed successfully, but requested icon could not be displayed",
                    0x05: "Command performed, but modified by call control by SIM",
                    0x06: "Command performed successfully, limited service",
                    0x07: "Command performed with modification",
                    0x10: "Proactive SIM session terminated by the user",
                    0x11: "Backward move in the proactive SIM session requested by the user",
                    0x12: "No response from user",
                    0x13: "Help information required by the user",
                    0x14: "USSD or SS transaction terminated by the user",
                    0x20: "ME currently unable to process command",
                    0x21: "Network currently unable to process command",
                    0x22: "User did not accept the proactive command",
                    0x23: "User cleared down call before connection or network release",
                    0x24: "Action in contradiction with the current timer state",
                    0x25: "Interaction with call control by SIM, temporary problem",
                    0x26: "Launch browser generic error code",
                    0x30: "Command beyond ME's capabilities",
                    0x31: "Command type not understood by ME",
                    0x32: "Command data not understood by ME", 
                    0x33: "Command number not known by ME",
                    0x34: "SS Return Error",
                    0x35: "SMS RP-ERROR",
                    0x36: "Error, required values are missing",
                    0x37: "USSD Return Error",
                    0x38: "MultipleCard commands error",
                    0x39: "Interaction with call control by SIM or MO SMS control by SIM, permanent problem",
                }
                result_name = result_names.get(result_code, f"Unknown result {result_code:02X}")
                result = f"Result: {result_name} ({result_code:02X})"
                return enhance_ascii_display(tag, value, result)
                
        elif tag == 0x05 or tag == 0x85:  # Alpha Identifier
            try:
                # Try to decode as text
                text = value.decode('utf-8', errors='ignore').strip()
                if text:
                    enhanced = detect_domain_or_url(text)
                    return f'"{text}"' if not enhanced or enhanced.startswith('Text:') else enhanced
                else:
                    return "(empty text)"
            except:
                return value.hex().upper()
                
        elif tag == 0x06:  # Address
            # Phone number or network address
            try:
                if len(value) >= 1:
                    ton_npi = value[0]  # Type of Number / Numbering Plan
                    digits = value[1:].hex().upper()
                    result = f"TON/NPI: {ton_npi:02X}, Number: {digits}"
                    return enhance_ascii_display(tag, value, result)
            except:
                pass
                
        elif tag == 0x36:  # Bearer Parameters (was Timer Expiration)
            return decode_bearer_parameters(value)
            
        elif tag == 0x04:  # Duration
            return decode_duration(value)
            
        elif tag in [0x30, 0xB7]:  # Channel Status
            return decode_channel_status(value)
            
        elif tag == 0x31:  # Buffer Size
            return decode_buffer_size(value)
            
        elif tag in [0x32, 0x3E]:  # Network Access Name (APN)
            return decode_network_access_name(value)
            
        elif tag == 0x73:  # Channel Data String
            return decode_channel_data_string(value)
            
        elif tag == 0x0C:  # Alpha Identifier (ISO 7816-4)
            return decode_alpha_identifier(value)
            
        elif tag == 0x35:  # R-APDU / Bearer Description
            return decode_r_apdu_bearer_description(value)
            
        elif tag == 0x39:  # Service Search / Buffer Size
            return decode_service_search_buffer_size(value)
            
        elif tag == 0x3C:  # Remote Entity Address / SIM/ME Interface Transport
            return decode_sim_me_interface_transport(value)
        
        # Check for Location Status patterns in raw data
        if len(value) >= 3:
            hex_value = value.hex().upper()
            if hex_value.startswith('1B00'):
                status_code = hex_value[4:6]
                if status_code == '00':
                    return f"Location Status: Normal Services (1B0000) - Full network connectivity"
                elif status_code == '01':
                    return f"Location Status: Limited Services (1B0001) - ⚠️ Restricted network access"
                elif status_code == '02':
                    return f"Location Status: No Services (1B0002) - ❌ No network connectivity"
                else:
                    return f"Location Status: Unknown status code 1B00{status_code}"
            
    except:
        pass
    
    # Default: return hex representation with enhanced ASCII detection
    if len(value) <= 16:
        hex_str = value.hex().upper()
    else:
        hex_str = f"{value[:8].hex().upper()}...{value[-8:].hex().upper()} ({len(value)} bytes)"
    
    return enhance_ascii_display(tag, value, hex_str)


def get_tag_name(tag: int) -> str:
    """Get tag name with fallback to hints for unknown tags."""
    # First try main tag dictionary
    if tag in TLV_TAGS:
        return TLV_TAGS[tag]
    
    # Then try fallback hints
    if tag in TAG_HINTS:
        return TAG_HINTS[tag]
    
    # Default unknown tag format
    return f"Unknown Tag {tag:02X}"


def detect_ascii_text(data: bytes) -> str:
    """Detect if bytes contain printable ASCII text and return it."""
    try:
        # Check if all bytes are printable ASCII (32-126) or whitespace
        if all(32 <= b <= 126 or b in [9, 10, 13] for b in data):
            text = data.decode('ascii').strip()
            # Only return if it has reasonable length and content
            if len(text) >= 2 and any(c.isalnum() for c in text):
                return text
    except:
        pass
    
    # Try UTF-8 decode for extended characters
    try:
        text = data.decode('utf-8', errors='ignore').strip()
        if len(text) >= 2 and any(c.isalnum() for c in text):
            # Check if it's mostly printable characters
            printable_ratio = sum(1 for c in text if c.isprintable()) / len(text)
            if printable_ratio >= 0.8:  # At least 80% printable
                return text
    except:
        pass
    
    return ""


def detect_domain_or_url(text: str) -> str:
    """Detect if text contains domain names or URLs and add context."""
    if not text:
        return ""
    
    # Domain patterns
    domain_indicators = ['.com', '.net', '.org', '.fr', '.co.uk', '.de', '.mobile', '.data']
    url_indicators = ['http://', 'https://', 'www.', 'ftp://']
    
    # Check for URLs
    for indicator in url_indicators:
        if indicator in text.lower():
            return f"URL: {text}"
    
    # Check for domain names
    for indicator in domain_indicators:
        if text.lower().endswith(indicator) or indicator in text.lower():
            return f"Domain: {text}"
    
    # Check for email-like patterns
    if '@' in text and '.' in text:
        return f"Email: {text}"
    
    # Check for APN patterns (contains dots and alphanumeric)
    if '.' in text and text.replace('.', '').replace('-', '').isalnum():
        return f"APN: {text}"
    
    # Check for common protocol indicators
    protocol_indicators = ['tcp://', 'udp://', 'sms:', 'tel:', 'sip:']
    for indicator in protocol_indicators:
        if text.lower().startswith(indicator):
            return f"Protocol: {text}"
    
    return f"Text: {text}"


def enhance_ascii_display(tag: int, value_bytes: bytes, base_result: str) -> str:
    """Enhance ASCII display with domain/URL detection and context."""
    ascii_text = detect_ascii_text(value_bytes)
    
    if ascii_text:
        # Get enhanced domain/URL detection
        enhanced_text = detect_domain_or_url(ascii_text)
        
        # Add appropriate context based on tag
        if tag in [0x75, 0x3E]:  # Network Access Name, APN
            if "APN:" not in enhanced_text and "Domain:" not in enhanced_text:
                enhanced_text = f"APN: {ascii_text}"
        elif tag in [0x29]:  # URL
            if "URL:" not in enhanced_text:
                enhanced_text = f"URL: {ascii_text}"
        elif tag in [0x05, 0x85]:  # Alpha Identifier
            enhanced_text = f"Text: {ascii_text}"
        elif tag in [0x73]:  # Channel Data String
            # Check for HTTP patterns
            if ascii_text.startswith(('GET ', 'POST ', 'PUT ', 'DELETE ', 'HTTP/')):
                enhanced_text = f"HTTP: {ascii_text}"
            elif 'Content-Length:' in ascii_text or 'Host:' in ascii_text:
                enhanced_text = f"HTTP Header: {ascii_text}"
            else:
                enhanced_text = detect_domain_or_url(ascii_text)
        
        # Append to base result
        if enhanced_text:
            return f"{base_result} | {enhanced_text}"
        else:
            return f"{base_result} | ASCII: '{ascii_text}'"
    
    return base_result


def decode_timer_expiration(value_bytes: bytes) -> str:
    """Decode Timer Expiration tag 0x36 according to SIM Toolkit specification."""
    if len(value_bytes) == 0:
        return "Empty Timer Expiration"
    
    try:
        # First byte is Timer ID
        if len(value_bytes) >= 1:
            timer_id = value_bytes[0]
            result = f"Timer ID: {timer_id}"
            
            # If more bytes available, they should be the time value in HHMMSS format
            if len(value_bytes) >= 4:
                # Bytes 1-3 are typically BCD encoded time (HHMMSS)
                hours = value_bytes[1]
                minutes = value_bytes[2] 
                seconds = value_bytes[3]
                
                # Try to interpret as BCD first
                try:
                    hours_bcd = (hours >> 4) * 10 + (hours & 0x0F)
                    minutes_bcd = (minutes >> 4) * 10 + (minutes & 0x0F)
                    seconds_bcd = (seconds >> 4) * 10 + (seconds & 0x0F)
                    
                    # Validate BCD values are reasonable
                    if hours_bcd <= 23 and minutes_bcd <= 59 and seconds_bcd <= 59:
                        result += f", Expired at: {hours_bcd:02d}:{minutes_bcd:02d}:{seconds_bcd:02d}"
                    else:
                        # Fall back to binary interpretation
                        result += f", Time: {hours:02d}:{minutes:02d}:{seconds:02d} (binary)"
                except:
                    # Fallback to binary values
                    result += f", Time: {hours:02d}:{minutes:02d}:{seconds:02d}"
            
            elif len(value_bytes) == 2:
                # Sometimes only Timer ID + status byte
                status = value_bytes[1]
                result += f", Status: 0x{status:02X}"
            
            # Add hex representation
            hex_str = ' '.join(f"{b:02X}" for b in value_bytes)
            result += f" | Hex: {hex_str}"
            
            return result
    
    except Exception as e:
        # Fallback to hex representation
        hex_str = ' '.join(f"{b:02X}" for b in value_bytes)
        return f"Timer Expiration: {hex_str}"


def decode_duration(value_bytes: bytes) -> str:
    """Decode Duration tag 0x04 according to SIM Toolkit specification."""
    if len(value_bytes) == 0:
        return "Empty Duration"
    
    try:
        # Duration format: Units (1 byte) + Time Interval (1-3 bytes)
        if len(value_bytes) >= 1:
            units = value_bytes[0]
            unit_names = {
                0x00: "minutes",
                0x01: "seconds", 
                0x02: "tenths of seconds"
            }
            unit_name = unit_names.get(units, f"unit 0x{units:02X}")
            
            if len(value_bytes) >= 2:
                # Time interval in the specified units
                if len(value_bytes) == 2:
                    interval = value_bytes[1]
                elif len(value_bytes) == 3:
                    interval = (value_bytes[1] << 8) | value_bytes[2]
                else:
                    interval = int.from_bytes(value_bytes[1:], 'big')
                
                # Convert to HH:MM:SS format
                if units == 0x00:  # minutes
                    hours = interval // 60
                    minutes = interval % 60
                    result = f"{hours:02d}:{minutes:02d}:00 ({interval} {unit_name})"
                elif units == 0x01:  # seconds
                    hours = interval // 3600
                    minutes = (interval % 3600) // 60
                    seconds = interval % 60
                    result = f"{hours:02d}:{minutes:02d}:{seconds:02d} ({interval} {unit_name})"
                else:  # tenths or other
                    result = f"{interval} {unit_name}"
                
                # Add ASCII if detected
                ascii_text = detect_ascii_text(value_bytes)
                if ascii_text:
                    result += f" | ASCII: '{ascii_text}'"
                
                return result
            else:
                return f"Units: {unit_name}"
    
    except Exception as e:
        # Fallback to hex
        hex_str = ' '.join(f"{b:02X}" for b in value_bytes)
        return f"Duration: {hex_str}"


def decode_channel_status(value_bytes: bytes) -> str:
    """Decode Channel Status (0x30/0xB7) with bit-by-bit analysis."""
    if len(value_bytes) == 0:
        return "Empty Channel Status"
    
    try:
        if len(value_bytes) >= 2:
            channel_id = value_bytes[0]
            status_byte = value_bytes[1]
            
            # Decode status bits
            is_open = (status_byte & 0x80) == 0x80
            tcp_in_established = (status_byte & 0x40) == 0x40
            tcp_out_established = (status_byte & 0x20) == 0x20
            
            status_text = "Open" if is_open else "Closed"
            connection_details = []
            
            if tcp_in_established:
                connection_details.append("TCP-IN")
            if tcp_out_established:
                connection_details.append("TCP-OUT")
            
            if connection_details:
                status_text += f" ({', '.join(connection_details)})"
            
            # Color badge for status
            if is_open and (tcp_in_established or tcp_out_established):
                badge = "[ACTIVE]"
            elif is_open:
                badge = "[READY]"
            else:
                badge = "[CLOSED]"
            
            result = f"Channel {channel_id}: {status_text} {badge}"
            
            # Add raw hex
            hex_str = ' '.join(f"{b:02X}" for b in value_bytes)
            result += f" | Hex: {hex_str}"
            
            return result
        else:
            # Single byte status
            status_byte = value_bytes[0]
            hex_str = ' '.join(f"{b:02X}" for b in value_bytes)
            return f"Channel Status: 0x{status_byte:02X} | Hex: {hex_str}"
    
    except Exception as e:
        hex_str = ' '.join(f"{b:02X}" for b in value_bytes)
        return f"Channel Status: {hex_str}"


def decode_buffer_size(value_bytes: bytes) -> str:
    """Decode Buffer Size tag 0x31."""
    if len(value_bytes) == 0:
        return "Empty Buffer Size"
    
    try:
        if len(value_bytes) >= 2:
            buffer_size = int.from_bytes(value_bytes, 'big')
            
            # Format in human-readable units
            if buffer_size >= 1024:
                kb_size = buffer_size / 1024
                if kb_size >= 1024:
                    mb_size = kb_size / 1024
                    result = f"{buffer_size} bytes ({mb_size:.1f} MB)"
                else:
                    result = f"{buffer_size} bytes ({kb_size:.1f} KB)"
            else:
                result = f"{buffer_size} bytes"
            
            # Add ASCII if detected
            ascii_text = detect_ascii_text(value_bytes)
            if ascii_text:
                result += f" | ASCII: '{ascii_text}'"
                
            return result
        else:
            buffer_size = value_bytes[0]
            return f"{buffer_size} bytes"
    
    except Exception as e:
        hex_str = ' '.join(f"{b:02X}" for b in value_bytes)
        return f"Buffer Size: {hex_str}"


def decode_network_access_name(value_bytes: bytes) -> str:
    """Decode Network Access Name (APN) tag 0x75 or Other Address tag 0x3E."""
    if len(value_bytes) == 0:
        return "Empty Network Access Name"
    
    try:
        # Check if it's an IPv4 address format (starts with 0x21)
        if len(value_bytes) == 5 and value_bytes[0] == 0x21:
            # IPv4 address: 0x21 followed by 4 bytes
            ip_bytes = value_bytes[1:5]
            ip_addr = '.'.join(str(b) for b in ip_bytes)
            return f"Type: 0x21 → IPv4, IP: {ip_addr}"
        
        # Check if it's an IPv6 address format (starts with 0x57)
        elif len(value_bytes) == 17 and value_bytes[0] == 0x57:
            # IPv6 address: 0x57 followed by 16 bytes
            ip_bytes = value_bytes[1:17]
            ip_parts = [f"{ip_bytes[i]:02x}{ip_bytes[i+1]:02x}" for i in range(0, 16, 2)]
            ip_addr = ':'.join(ip_parts)
            return f"Type: 0x57 → IPv6, IP: {ip_addr}"
        
        # Try to decode as ASCII text (APN)
        ascii_text = detect_ascii_text(value_bytes)
        if ascii_text:
            # Check if it looks like a domain/APN
            if '.' in ascii_text or ascii_text.endswith('.com') or ascii_text.endswith('.net'):
                return f"APN: {ascii_text} [DOMAIN]"
            else:
                return f"APN: {ascii_text}"
        else:
            # Try UTF-8 decode
            try:
                utf8_text = value_bytes.decode('utf-8', errors='ignore').strip()
                if utf8_text and len(utf8_text) > 1:
                    return f"APN: {utf8_text}"
            except:
                pass
            
            # Fallback to hex
            hex_str = ' '.join(f"{b:02X}" for b in value_bytes)
            return f"Network Access: {hex_str}"
    
    except Exception as e:
        hex_str = ' '.join(f"{b:02X}" for b in value_bytes)
        return f"Network Access Name: {hex_str}"


def decode_channel_data_string(value_bytes: bytes) -> str:
    """Decode Channel Data String tag 0x73."""
    if len(value_bytes) == 0:
        return "Empty Channel Data"
    
    try:
        # Check for ASCII content
        ascii_text = detect_ascii_text(value_bytes)
        if ascii_text:
            # If it looks like HTTP or protocol data
            if ascii_text.startswith(('HTTP/', 'GET ', 'POST ', 'PUT ', 'DELETE ')):
                return f"HTTP Data: {ascii_text}"
            elif ascii_text.startswith('Host:') or 'Content-Length:' in ascii_text:
                return f"HTTP Header: {ascii_text}"
            else:
                return f"Text Data: {ascii_text}"
        else:
            # Show hex with length
            hex_str = value_bytes[:16].hex().upper()
            if len(value_bytes) > 16:
                hex_str += f"... ({len(value_bytes)} bytes total)"
            return f"Binary Data: {hex_str}"
    
    except Exception as e:
        hex_str = ' '.join(f"{b:02X}" for b in value_bytes[:8])
        if len(value_bytes) > 8:
            hex_str += f"... ({len(value_bytes)} bytes)"
        return f"Channel Data: {hex_str}"


def decode_bearer_parameters(value_bytes: bytes) -> str:
    """Decode Bearer Parameters tag 0x36."""
    if len(value_bytes) == 0:
        return "Empty Bearer Parameters"
    
    try:
        result_parts = []
        pos = 0
        
        # Bearer parameters contain multiple sub-TLVs or structured data
        if len(value_bytes) >= 1:
            bearer_type = value_bytes[0]
            bearer_types = {
                0x01: "Circuit Switched Data (CSD)",
                0x02: "GPRS",
                0x03: "Default bearer for requested transport",
                0x04: "Local bearer for requested transport",
                0x05: "Bluetooth",
                0x06: "IRDA",
                0x07: "RS232",
                0x08: "USB"
            }
            bearer_name = bearer_types.get(bearer_type, f"Unknown Bearer {bearer_type:02X}")
            result_parts.append(f"Bearer: {bearer_name}")
            pos += 1
        
        # Look for DNS names or APNs in the data
        ascii_text = detect_ascii_text(value_bytes[pos:])
        if ascii_text:
            # Parse DNS labels format (length-prefixed strings)
            dns_parts = []
            data = value_bytes[pos:]
            i = 0
            while i < len(data):
                if data[i] == 0:  # End of domain
                    break
                if i + data[i] + 1 <= len(data):
                    label_len = data[i]
                    if label_len > 0 and label_len <= 63:  # Valid DNS label length
                        try:
                            label = data[i+1:i+1+label_len].decode('ascii')
                            dns_parts.append(label)
                            i += label_len + 1
                        except:
                            break
                    else:
                        break
                else:
                    break
            
            if dns_parts:
                domain = '.'.join(dns_parts)
                result_parts.append(f"APN/Domain: {domain}")
            elif ascii_text:
                result_parts.append(f"Text: {ascii_text}")
        
        # Add hex representation
        hex_str = ' '.join(f"{b:02X}" for b in value_bytes[:16])
        if len(value_bytes) > 16:
            hex_str += f"... ({len(value_bytes)} bytes)"
        result_parts.append(f"Hex: {hex_str}")
        
        return " | ".join(result_parts)
    
    except Exception as e:
        hex_str = ' '.join(f"{b:02X}" for b in value_bytes)
        return f"Bearer Parameters: {hex_str}"


def decode_alpha_identifier(value_bytes: bytes) -> str:
    """Decode Alpha Identifier tag 0x0C (ISO 7816-4 format)."""
    if len(value_bytes) == 0:
        return "Empty Alpha Identifier"
    
    try:
        # Try different text encodings
        # First try ASCII
        try:
            ascii_text = value_bytes.decode('ascii', errors='ignore').strip()
            if ascii_text and all(c.isprintable() for c in ascii_text):
                enhanced = detect_domain_or_url(ascii_text)
                return enhanced if enhanced and not enhanced.startswith('Text:') else f'Alpha: "{ascii_text}"'
        except:
            pass
        
        # Try UTF-8
        try:
            utf8_text = value_bytes.decode('utf-8', errors='ignore').strip()
            if utf8_text and len(utf8_text) >= 2:
                enhanced = detect_domain_or_url(utf8_text)
                return enhanced if enhanced and not enhanced.startswith('Text:') else f'Alpha: "{utf8_text}"'
        except:
            pass
        
        # Check for UCS2 encoding (starts with 0x80)
        if len(value_bytes) >= 3 and value_bytes[0] == 0x80:
            try:
                ucs2_text = value_bytes[1:].decode('utf-16be', errors='ignore').strip()
                if ucs2_text:
                    return f'Alpha (UCS2): "{ucs2_text}"'
            except:
                pass
        
        # Fallback to hex
        hex_str = ' '.join(f"{b:02X}" for b in value_bytes)
        return f"Alpha Identifier: {hex_str}"
    
    except Exception as e:
        hex_str = ' '.join(f"{b:02X}" for b in value_bytes)
        return f"Alpha Identifier: {hex_str}"


def decode_r_apdu_bearer_description(value_bytes: bytes) -> str:
    """Decode R-APDU/Bearer Description tag 0x35."""
    if len(value_bytes) == 0:
        return "Empty Bearer Description"
    
    try:
        if len(value_bytes) == 1:
            bearer_code = value_bytes[0]
            bearer_types = {
                0x01: "Circuit Switched Data (CSD)",
                0x02: "GPRS", 
                0x03: "Default bearer for requested transport layer",
                0x04: "Local bearer for requested transport layer",
                0x05: "Bluetooth",
                0x06: "IrDA",
                0x07: "RS232",
                0x08: "USB"
            }
            bearer_name = bearer_types.get(bearer_code, f"Unknown bearer {bearer_code:02X}")
            return f"0x{bearer_code:02X} → {bearer_name}"
        else:
            # Multi-byte R-APDU
            hex_str = ' '.join(f"{b:02X}" for b in value_bytes)
            return f"R-APDU: {hex_str}"
    
    except Exception as e:
        hex_str = ' '.join(f"{b:02X}" for b in value_bytes)
        return f"Bearer Description: {hex_str}"


def decode_service_search_buffer_size(value_bytes: bytes) -> str:
    """Decode Service Search/Buffer Size tag 0x39."""
    if len(value_bytes) == 0:
        return "Empty Buffer Size"
    
    try:
        if len(value_bytes) == 2:
            buffer_size = int.from_bytes(value_bytes, 'big')
            hex_repr = f"{value_bytes[0]:02X}{value_bytes[1]:02X}"
            return f"0x{hex_repr} → {buffer_size} bytes"
        else:
            hex_str = ' '.join(f"{b:02X}" for b in value_bytes)
            return f"Service Search: {hex_str}"
    
    except Exception as e:
        hex_str = ' '.join(f"{b:02X}" for b in value_bytes)
        return f"Buffer Size: {hex_str}"


def decode_sim_me_interface_transport(value_bytes: bytes) -> str:
    """Decode SIM/ME Interface Transport tag 0x3C."""
    if len(value_bytes) == 0:
        return "Empty Transport Info"
    
    try:
        if len(value_bytes) >= 3:
            protocol = value_bytes[0]
            port = int.from_bytes(value_bytes[1:3], 'big')
            
            protocol_names = {
                0x01: "UDP",
                0x02: "TCP", 
                0x03: "TCP Server mode",
                0x04: "UDP Server mode"
            }
            protocol_name = protocol_names.get(protocol, f"Protocol {protocol:02X}")
            
            hex_repr = ' '.join(f"{b:02X}" for b in value_bytes)
            return f"Protocol: 0x{protocol:02X} → {protocol_name}, Port: 0x{port:04X} → {port}"
        else:
            hex_str = ' '.join(f"{b:02X}" for b in value_bytes)
            return f"Transport: {hex_str}"
    
    except Exception as e:
        hex_str = ' '.join(f"{b:02X}" for b in value_bytes)
        return f"SIM/ME Interface Transport: {hex_str}"


def determine_apdu_case(data: bytes) -> str:
    """Determine APDU case based on structure."""
    if len(data) < 4:
        return "invalid"
    elif len(data) == 4:
        return "case1"
    elif len(data) == 5:
        return "case2"
    else:
        # Check if it has Lc field
        lc = data[4]
        expected_length = 5 + lc
        
        if len(data) == expected_length:
            return "case3"
        elif len(data) == expected_length + 1:
            return "case4"
        elif len(data) == expected_length + 2 and data[-2:] == data[-2:]:
            # Likely response with SW1 SW2
            return "response"
        else:
            # If it doesn't match expected patterns, try as response
            if len(data) >= 2:
                # Check if last 2 bytes look like status word
                sw = (data[-2] << 8) | data[-1]
                if sw in SW_CODES or (sw & 0xFF00) in [0x6100, 0x6C00, 0x9100, 0x9200]:
                    return "response"
            return "case3"  # Default to case 3 if unsure


def parse_apdu(hex_data: str) -> APDUInfo:
    """Parse APDU hex data using Construct schemas."""
    warnings = []
    
    try:
        # Clean hex data
        clean_hex = ''.join(c for c in hex_data if c.isalnum())
        if len(clean_hex) % 2 != 0:
            warnings.append("Odd hex string length - truncating last character")
            clean_hex = clean_hex[:-1]
        
        data = bytes.fromhex(clean_hex)
        
        if len(data) < 4:
            return APDUInfo(
                raw_hex=hex_data,
                cla=0, ins=0, p1=0, p2=0, 
                lc=None, le=None, data=None,
                ins_name="Invalid APDU",
                command_type="Invalid",
                tlvs=[],
                summary="Invalid APDU - too short",
                warnings=["APDU too short (< 4 bytes)"],
                direction="Unknown",
                domain="Invalid"
            )
        
        # Determine APDU structure
        apdu_case = determine_apdu_case(data)
        schemas = create_apdu_schema()
        
        if schemas is None:
            # Fallback parsing without construct
            return parse_apdu_fallback(data, hex_data)
        
        # Parse based on case
        parsed = None
        sw = None
        sw_desc = ""
        
        if apdu_case == "response":
            # Response APDU - use manual parsing to avoid construct issues
            try:
                # Manual parsing: last 2 bytes are always SW
                sw = (data[-2] << 8) | data[-1]
                response_data = data[:-2] if len(data) > 2 else b""
                
                sw_desc = get_sw_description(sw)
                
                # Try to parse any data as TLVs
                tlvs = []
                if response_data:
                    # Check if this is a proactive command response (starts with D0)
                    if len(response_data) >= 2 and response_data[0] == 0xD0:
                        # This is a proactive command (FETCH response)
                        # D0 = tag, then BER-TLV length (short or long form), then TLVs.
                        pos = 1
                        length = None
                        try:
                            if pos < len(response_data):
                                length_byte = response_data[pos]
                                pos += 1
                                if length_byte & 0x80:
                                    length_bytes = length_byte & 0x7F
                                    if length_bytes == 0 or pos + length_bytes > len(response_data):
                                        length = None
                                    else:
                                        length = 0
                                        for _ in range(length_bytes):
                                            length = (length << 8) | response_data[pos]
                                            pos += 1
                                else:
                                    length = length_byte
                        except Exception:
                            length = None

                        if length is not None and pos + length <= len(response_data):
                            proactive_tlv_data = response_data[pos:pos + length]
                        elif length is not None and pos < len(response_data):
                            # Truncated capture: best-effort parse remaining bytes
                            proactive_tlv_data = response_data[pos:]
                        else:
                            proactive_tlv_data = b""

                        if proactive_tlv_data:
                            tlvs = parse_ber_tlv(proactive_tlv_data)
                            
                            # Override summary for proactive commands
                            summary = "FETCH Response: Proactive Command"
                            
                            # Extract command type from Command Details if present
                            for tlv in tlvs:
                                if tlv.tag in [0x01, 0x81]:  # Command Details
                                    if "OPEN CHANNEL" in tlv.decoded_value:
                                        summary = "FETCH Response: OPEN CHANNEL Command"
                                    elif "SEND DATA" in tlv.decoded_value:
                                        summary = "FETCH Response: SEND DATA Command"
                                    elif "CLOSE CHANNEL" in tlv.decoded_value:
                                        summary = "FETCH Response: CLOSE CHANNEL Command"
                                    break
                            
                            return APDUInfo(
                                raw_hex=hex_data,
                                cla=0, ins=0x12, p1=0, p2=0,  # Simulate FETCH response
                                lc=None, le=None, data=proactive_tlv_data,
                                ins_name="FETCH RESPONSE",
                                command_type="Proactive Command Response",
                                tlvs=tlvs,
                                summary=summary,
                                warnings=warnings,
                                direction="SIM->ME", 
                                domain="SIM Toolkit",
                                sw=sw,
                                sw_description=sw_desc
                            )
                    else:
                        # Regular response data
                        tlvs = parse_ber_tlv(response_data)
                
                return APDUInfo(
                    raw_hex=hex_data,
                    cla=0, ins=0, p1=0, p2=0,
                    lc=None, le=None, data=response_data,
                    ins_name="RESPONSE",
                    command_type="Response",
                    tlvs=tlvs,
                    summary=f"Response: {sw_desc}",
                    warnings=warnings,
                    direction="SIM->ME", 
                    domain="Response",
                    sw=sw,
                    sw_description=sw_desc
                )
            except:
                return parse_apdu_fallback(data, hex_data)
        
        # Command APDU
        try:
            if apdu_case == "case1":
                parsed = schemas['case1'].parse(data)
            elif apdu_case == "case2":
                parsed = schemas['case2'].parse(data) 
            elif apdu_case == "case3":
                parsed = schemas['case3'].parse(data)
            elif apdu_case == "case4": 
                parsed = schemas['case4'].parse(data)
            else:
                return parse_apdu_fallback(data, hex_data)
        except:
            return parse_apdu_fallback(data, hex_data)
        
        # Extract header info
        header = parsed.header
        cla = header.cla
        ins = header.ins
        p1 = header.p1
        p2 = header.p2
        lc = parsed.lc if parsed.lc > 0 else None
        le = parsed.le
        apdu_data = parsed.data if hasattr(parsed, 'data') and len(parsed.data) > 0 else None
        
        # Get instruction name
        ins_name = INS_CODES.get(ins, f"Unknown INS {ins:02X}")
        
        # Parse TLVs from data field
        tlvs = []
        if apdu_data:
            tlvs = parse_ber_tlv(apdu_data)
        
        # Validate TLV lengths
        if lc and apdu_data:
            tlv_total = sum(tlv.total_length for tlv in tlvs)
            if tlv_total != lc:
                warnings.append(f"TLV total length ({tlv_total}) ≠ Lc ({lc})")
        
        # Check for mandatory TLVs in TERMINAL RESPONSE
        if ins == 0x14:  # TERMINAL RESPONSE
            mandatory_tags = {0x81, 0x82, 0x83}
            found_tags = {tlv.tag for tlv in tlvs}
            missing_tags = mandatory_tags - found_tags
            if missing_tags:
                missing_names = [TLV_TAGS.get(tag, f"{tag:02X}") for tag in missing_tags]
                warnings.append(f"Missing mandatory TLVs: {', '.join(missing_names)}")
        
        # Generate summary
        summary = generate_summary(ins, ins_name, tlvs, cla, p1, p2)
        
        # Determine command type and direction
        command_type, direction = infer_command_type_and_direction(ins, tlvs)
        
        # Detect domain
        domain = detect_protocol_domain(ins, tlvs, apdu_data)
        
        return APDUInfo(
            raw_hex=hex_data,
            cla=cla, ins=ins, p1=p1, p2=p2,
            lc=lc, le=le, data=apdu_data,
            ins_name=ins_name,
            command_type=command_type,
            direction=direction,
            tlvs=tlvs,
            summary=summary,
            warnings=warnings,
            domain=domain,
            sw=sw,
            sw_description=sw_desc
        )
        
    except Exception as e:
        return APDUInfo(
            raw_hex=hex_data,
            cla=0, ins=0, p1=0, p2=0,
            lc=None, le=None, data=None,
            ins_name="Parse Error",
            command_type="Error",
            tlvs=[],
            summary=f"Parse error: {str(e)}",
            warnings=[f"Parse error: {str(e)}"],
            direction="Unknown",
            domain="Error"
        )


def parse_apdu_fallback(data: bytes, hex_data: str) -> APDUInfo:
    """Fallback APDU parser without Construct library."""
    warnings = []
    
    # Basic header parsing
    cla = data[0]
    ins = data[1] 
    p1 = data[2]
    p2 = data[3]
    
    ins_name = INS_CODES.get(ins, f"Unknown INS {ins:02X}")
    
    # Try to extract data portion
    apdu_data = None
    lc = None
    le = None
    
    if len(data) > 4:
        if len(data) >= 6:
            # Could be Case 3 or 4
            potential_lc = data[4]
            if len(data) >= 5 + potential_lc:
                lc = potential_lc
                apdu_data = data[5:5 + lc]
                if len(data) > 5 + lc:
                    le = data[5 + lc]
        elif len(data) == 5:
            # Case 2
            le = data[4]
    
    # Parse TLVs
    tlvs = []
    if apdu_data:
        tlvs = parse_ber_tlv(apdu_data)
    
    # Detect domain
    domain = detect_protocol_domain(ins, tlvs, apdu_data)
    
    summary = generate_summary(ins, ins_name, tlvs, cla, p1, p2)
    
    return APDUInfo(
        raw_hex=hex_data,
        cla=cla, ins=ins, p1=p1, p2=p2,
        lc=lc, le=le, data=apdu_data,
        ins_name=ins_name,
        command_type="Command",
        tlvs=tlvs,
        summary=summary,
        warnings=warnings,
        direction="ME->SIM",  # Fallback parser assumes ME to SIM
        domain=domain
    )


def infer_command_type_and_direction(ins: int, tlvs: list) -> tuple[str, str]:
    """Infer command type and direction based on INS and TLV content."""
    # Direction inference
    direction = "Unknown"
    command_type = "Command"
    
    # Basic command type mapping
    if ins == 0x12:
        command_type = "FETCH"
        direction = "ME->SIM"  # ME requests command from SIM
    elif ins == 0x14:
        command_type = "TERMINAL RESPONSE"  
        direction = "ME->SIM"  # ME responds to SIM command
    elif ins == 0x70:
        command_type = "MANAGE CHANNEL"
        direction = "ME->SIM"  # ME manages channel with SIM
    elif ins == 0x10:
        command_type = "TERMINAL PROFILE"
        direction = "ME->SIM"  # ME sends capabilities to SIM
    elif ins in [0xC0, 0xC2]:
        command_type = "GET RESPONSE"
        direction = "ME->SIM"  # ME requests response data
    
    # Refine based on TLV content
    for tlv in tlvs:
        if tlv.tag in [0x02, 0x82]:  # Device Identity
            # Check source/destination to infer direction
            if len(tlv.value_hex) >= 4:
                try:
                    source = int(tlv.value_hex[0:2], 16)
                    dest = int(tlv.value_hex[2:4], 16)
                    if source == 0x82 and dest == 0x81:  # ME to SIM
                        direction = "ME->SIM"
                    elif source == 0x81 and dest == 0x82:  # SIM to ME
                        direction = "SIM->ME"
                    elif source == 0x82:  # ME is source
                        direction = "ME->SIM"
                    elif dest == 0x82:   # ME is destination
                        direction = "SIM->ME"
                except:
                    pass
        
        elif tlv.tag in [0x01, 0x81]:  # Command Details
            # Proactive commands from SIM typically have Command Details
            if ins == 0x12:  # If this is FETCH with Command Details
                direction = "SIM->ME"  # SIM sends proactive command
    
    return command_type, direction


def detect_protocol_domain(ins: int, tlvs: list, apdu_data: bytes = None) -> str:
    """Detect the protocol domain based on command and TLV content."""
    
    # Domain detection based on INS code
    if ins == 0x12:  # FETCH
        # Look for command details TLV to determine proactive command type
        for tlv in tlvs:
            if tlv.tag in [0x01, 0x81]:  # Command Details
                if len(tlv.value_hex) >= 2:
                    try:
                        cmd_type = int(tlv.value_hex[2:4], 16) if len(tlv.value_hex) >= 4 else 0
                        if cmd_type in [0x10, 0x11, 0x12, 0x13, 0x14]:  # Display commands
                            return "User Interface"
                        elif cmd_type in [0x20, 0x21, 0x22, 0x23]:  # Input commands
                            return "User Interface"  
                        elif cmd_type in [0x30, 0x31]:  # Sound commands
                            return "Audio"
                        elif cmd_type in [0x40, 0x41, 0x42]:  # Channel management
                            return "Bearer Independent Protocol (BIP)"
                        elif cmd_type in [0x43, 0x44]:  # Communication
                            return "Bearer Independent Protocol (BIP)"
                        elif cmd_type == 0x25:  # Timer management
                            return "Timer Management"
                        elif cmd_type in [0x01, 0x02, 0x03, 0x04]:  # Refresh, polling
                            return "Card Management"
                    except:
                        pass
        return "SIM Toolkit"
    
    elif ins == 0x14:  # TERMINAL RESPONSE
        return "SIM Toolkit Response"
    
    elif ins == 0x10:  # TERMINAL PROFILE
        return "Terminal Capabilities"
        
    elif ins == 0x70:  # MANAGE CHANNEL
        return "Bearer Independent Protocol (BIP)"
        
    elif ins in [0xA4]:  # SELECT FILE
        return "File Management"
        
    elif ins in [0xB0, 0xB2]:  # READ BINARY/RECORD
        return "File I/O"
        
    elif ins in [0xD0, 0xD2]:  # WRITE BINARY/RECORD  
        return "File I/O"
        
    elif ins in [0x20, 0x24]:  # VERIFY PIN, CHANGE PIN
        return "Authentication"
        
    elif ins == 0x88:  # GET CHALLENGE
        return "Authentication"
    
    # Domain detection based on TLV content
    for tlv in tlvs:
        if tlv.tag in [0x18]:  # SMS TPDU
            return "Short Message Service (SMS)"
        elif tlv.tag in [0x17]:  # SS String  
            return "Supplementary Services"
        elif tlv.tag in [0x06]:  # Address (often phone numbers)
            return "Call Control"
        elif tlv.tag in [0x29]:  # URL
            return "Browser/WAP"
        elif tlv.tag in [0x2A, 0x2D]:  # Bearer related
            return "Bearer Independent Protocol (BIP)"
        elif tlv.tag in [0x2E, 0x2F]:  # Channel Data
            return "Bearer Independent Protocol (BIP)"
        elif tlv.tag in [0x30]:  # Channel Status
            return "Bearer Independent Protocol (BIP)"
        elif tlv.tag in [0x36, 0x1C, 0x1D]:  # Timer related
            return "Timer Management"
        elif tlv.tag in [0x3E]:  # Network Access Name (APN)
            return "Packet Data"
        elif tlv.tag in [0x42, 0x67]:  # PDP Context
            return "Packet Data"
        elif tlv.tag in [0x20, 0x21]:  # AT Command/Response
            return "Modem Control"
    
    # Default categorization
    return "General"


def generate_summary(ins: int, ins_name: str, tlvs: List[TLVInfo], cla: int, p1: int, p2: int) -> str:
    """Generate a one-line summary of the APDU."""
    
    # Extract key information from TLVs
    command_details = None
    device_identity = None
    result = None
    
    for tlv in tlvs:
        if tlv.tag in [0x01, 0x81]:  # Command Details
            command_details = tlv.decoded_value
        elif tlv.tag in [0x02, 0x82]:  # Device Identity  
            device_identity = tlv.decoded_value
        elif tlv.tag in [0x03, 0x83]:  # Result
            result = tlv.decoded_value
    
    # Build summary based on instruction
    if ins == 0x12:  # FETCH
        if command_details:
            return f"FETCH – {command_details}"
        return f"FETCH command"
        
    elif ins == 0x14:  # TERMINAL RESPONSE
        cmd_info = ""
        if command_details:
            # Extract command name from command details
            if "Type:" in command_details:
                parts = command_details.split("Type:")
                if len(parts) > 1:
                    cmd_part = parts[1].split("(")[0].strip()
                    cmd_info = cmd_part
        
        direction = ""
        if device_identity:
            if "ME" in device_identity and "SIM" in device_identity:
                if device_identity.index("ME") < device_identity.index("SIM"):
                    direction = " (ME→SIM)"
                else:
                    direction = " (SIM→ME)"
        
        status = ""
        if result:
            if "successfully" in result.lower():
                status = " executed successfully"
            elif "error" in result.lower() or "unable" in result.lower():
                status = " failed"
        
        if cmd_info:
            return f"TERMINAL RESPONSE – {cmd_info}{status}{direction}"
        else:
            return f"TERMINAL RESPONSE{status}{direction}"
            
    elif ins == 0x70:  # MANAGE CHANNEL
        if p1 == 0x00:
            return f"MANAGE CHANNEL – Open Channel (P2: {p2:02X})"
        elif p1 == 0x80:
            return f"MANAGE CHANNEL – Close Channel {p2}"
        else:
            return f"MANAGE CHANNEL (P1: {p1:02X}, P2: {p2:02X})"
    
    # Default summary
    return f"{ins_name} (CLA: {cla:02X}, P1: {p1:02X}, P2: {p2:02X})"


# Test function
if __name__ == "__main__":
    # Test with sample APDU
    test_apdu = "D01E8103014003820281820500350103390205783C030100353E0521080808089000"
    result = parse_apdu(test_apdu)
    
    print(f"Summary: {result.summary}")
    print(f"Command: {result.ins_name}")
    print(f"Warnings: {result.warnings}")
    print(f"TLVs found: {len(result.tlvs)}")
    
    for tlv in result.tlvs:
        print(f"  {tlv.tag_hex}: {tlv.name} = {tlv.decoded_value}")