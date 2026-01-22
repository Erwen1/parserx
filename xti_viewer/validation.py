"""
Validation and anomaly detection for XTI trace parsing.
"""
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import re


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    INFO = "INFO"       # Blue - informational
    WARNING = "WARNING" # Orange - potential issues
    CRITICAL = "CRITICAL"  # Red - serious violations


@dataclass
class ValidationIssue:
    """Represents a validation issue found during parsing."""
    severity: ValidationSeverity
    category: str
    message: str
    trace_index: int
    timestamp: Optional[str]
    raw_data: Optional[str]
    channel_id: Optional[str] = None
    command_details: Optional[str] = None

    @property
    def trace_item_index(self) -> int:
        """Backward-compatible alias used by some UI/export code."""
        return self.trace_index
    
    def __str__(self):
        return f"[{self.severity.value}] {self.category}: {self.message}"


@dataclass
class ChannelState:
    """State tracking for a channel."""
    channel_id: str
    opened_at_index: int
    opened_timestamp: Optional[str]
    is_open: bool = True
    close_reason: Optional[str] = None


@dataclass
class PendingFetch:
    """Tracking for FETCH commands awaiting TERMINAL RESPONSE."""
    fetch_index: int
    fetch_timestamp: Optional[str]
    command_type: str
    timeout_threshold: float = 5.0  # 5 seconds


class ValidationManager:
    """Manages validation and anomaly detection during XTI parsing."""
    
    def __init__(self):
        self.issues: List[ValidationIssue] = []
        self.open_channels: Dict[str, ChannelState] = {}
        self.pending_fetches: List[PendingFetch] = []
        self.processed_count = 0
        
        # Service status patterns (matches BER-TLV: 1B=tag, 01=length, xx=value)
        self.location_status_patterns = {
            "1B0100": ("Normal Services", "Normal", ValidationSeverity.INFO),
            "1B0101": ("Limited Services", "Orange", ValidationSeverity.WARNING),
            # Adjusted per request: 'No Services' should be a Warning, not Critical
            "1B0102": ("No Services", "Red", ValidationSeverity.WARNING),
        }
        
        # Track ICCID file selection for subsequent READ BINARY
        self.pending_iccid_read = False
        self.iccid_select_index = -1
        self.iccid_read_binary_seen = False
    
    def validate_trace_item(self, trace_item, index: int):
        """Validate a single trace item and detect anomalies."""
        self.processed_count += 1
        
        # Extract key information from trace item
        summary = getattr(trace_item, 'summary', '').upper()
        raw_hex = getattr(trace_item, 'rawhex', '')
        timestamp = getattr(trace_item, 'timestamp', None)
        
        # Validate channel operations
        self._validate_channel_operations(trace_item, index, summary)
        
        # Validate FETCH/TERMINAL RESPONSE patterns
        self._validate_fetch_response_patterns(trace_item, index, summary)
        
        # Check for location status events
        self._check_location_status(trace_item, index, raw_hex)
        
        # Check for missing IP in OPEN CHANNEL
        self._check_open_channel_ip(trace_item, index, summary, raw_hex)
        
        # Check for card power events (reboot/refresh/power off)
        self._check_card_power_events(trace_item, index, summary)
        
        # Check for ICCID read operations
        self._check_iccid_read(trace_item, index, summary, raw_hex)
        
        # Check for dropped links
        self._check_dropped_link(trace_item, index, summary, raw_hex)
        
        # Check for status word 5023 (technical problem)
        self._check_sw_5023(trace_item, index, summary, raw_hex)
        
        # Check for Bearer Independent Protocol errors
        self._check_bip_errors(trace_item, index, summary, raw_hex)
        
        # Check for TERMINAL RESPONSE errors
        self._check_terminal_response_errors(trace_item, index, summary)
        
        # Validate state machine violations
        self._validate_state_machines(trace_item, index, summary)
    
    def _validate_channel_operations(self, trace_item, index: int, summary: str):
        """Validate OPEN/CLOSE channel operations."""
        # Extract channel ID from summary or raw data
        channel_id = self._extract_channel_id(trace_item, summary)
        
        if "OPEN CHANNEL" in summary and "SW: 9000" in summary:
            # Successful OPEN CHANNEL
            if channel_id:
                if channel_id in self.open_channels:
                    # Multiple opens on same channel
                    old_state = self.open_channels[channel_id]
                    self.add_issue(
                        ValidationSeverity.CRITICAL,
                        "State Machine Violation",
                        f"Multiple OPEN CHANNEL commands using same Channel ID {channel_id}. "
                        f"Previous open at index {old_state.opened_at_index}",
                        index,
                        getattr(trace_item, 'timestamp', None),
                        getattr(trace_item, 'rawhex', ''),
                        channel_id
                    )
                    # Also mark the original open as problematic
                    self.add_issue(
                        ValidationSeverity.CRITICAL,
                        "Resource Leak",
                        f"Channel {channel_id} was opened but never properly closed before reuse",
                        old_state.opened_at_index,
                        old_state.opened_timestamp,
                        None,
                        channel_id
                    )
                
                # Track new open
                self.open_channels[channel_id] = ChannelState(
                    channel_id=channel_id,
                    opened_at_index=index,
                    opened_timestamp=getattr(trace_item, 'timestamp', None)
                )
        
        elif "CLOSE CHANNEL" in summary:
            # CLOSE CHANNEL operation
            if channel_id:
                if channel_id not in self.open_channels:
                    # Close without open
                    self.add_issue(
                        ValidationSeverity.CRITICAL,
                        "State Machine Violation",
                        f"CLOSE CHANNEL for Channel ID {channel_id} without preceding OPEN CHANNEL",
                        index,
                        getattr(trace_item, 'timestamp', None),
                        getattr(trace_item, 'rawhex', ''),
                        channel_id
                    )
                else:
                    # Valid close, remove from tracking
                    del self.open_channels[channel_id]
    
    def _validate_fetch_response_patterns(self, trace_item, index: int, summary: str):
        """Validate FETCH commands have corresponding TERMINAL RESPONSE."""
        # In XTI traces, TERMINAL RESPONSE entries are usually legitimate responses
        # to proactive commands. Only flag as issues in specific problematic patterns.
        
        # Look for actual proactive command fetches (outgoing commands from SIM)
        if any(cmd in summary.upper() for cmd in ["OPEN CHANNEL", "CLOSE CHANNEL", "SEND DATA", "RECEIVE DATA"]):
            # These are legitimate command/response pairs
            return
        
        # Look for genuine fetch patterns that need responses
        if "FETCH" in summary.upper() and ("SW: 91" in summary or "COMMAND PERFORMED" in summary.upper()):
            # This indicates a successful fetch that should have a response
            command_type = self._extract_command_type(summary)
            self.pending_fetches.append(
                PendingFetch(
                    fetch_index=index,
                    fetch_timestamp=getattr(trace_item, 'timestamp', None),
                    command_type=command_type
                )
            )
        
        # Only flag unexpected responses if they truly appear orphaned
        # This is now much more conservative to avoid false positives
        elif "TERMINAL RESPONSE" in summary and "UNEXPECTED" in summary.upper():
            # Only flag if explicitly marked as unexpected in the trace
            self.add_issue(
                ValidationSeverity.INFO,  # Reduced severity
                "Trace Analysis",
                f"Terminal response marked as unexpected in trace: {summary[:50]}...",
                index,
                getattr(trace_item, 'timestamp', None),
                getattr(trace_item, 'rawhex', ''),
                command_details=summary
            )
        
        # Check for timeouts (this would need timestamp parsing)
        self._check_fetch_timeouts(trace_item, index)
    
    def _check_location_status(self, trace_item, index: int, raw_hex: str):
        """Check for location status events and decode service level."""
        if not raw_hex:
            return
        
        # Look for location status patterns in raw hex
        clean_hex = raw_hex.replace(' ', '').upper()
        
        for pattern, (status_name, color_code, severity) in self.location_status_patterns.items():
            if pattern in clean_hex:
                # Simplify message: show only short status label (e.g., 'No Service')
                try:
                    simple_name = status_name.replace('Services', 'Service')
                except Exception:
                    simple_name = status_name
                self.add_issue(
                    severity,
                    "Location Status",
                    simple_name,
                    index,
                    getattr(trace_item, 'timestamp', None),
                    raw_hex,
                    command_details=f"Status code: {pattern}"
                )
                break
    
    def _check_open_channel_ip(self, trace_item, index: int, summary: str, raw_hex: str):
        """Check if OPEN CHANNEL contains IP address."""
        if "OPEN CHANNEL" in summary:
            # Check if this is a DNS channel opened by ME
            if raw_hex and not self._contains_ip_pattern(raw_hex):
                # This is likely a DNS channel opened by ME, not an error
                self.add_issue(
                    ValidationSeverity.INFO,  # Changed from WARNING to INFO
                    "Channel Analysis",
                    "OPEN CHANNEL without IP address - likely DNS channel opened by ME",
                    index,
                    getattr(trace_item, 'timestamp', None),
                    raw_hex,
                    command_details=summary
                )
    
    def _check_card_power_events(self, trace_item, index: int, summary: str):
        """Detect card power events (reboot, refresh, power off)."""
        item_type = getattr(trace_item, 'type', '').upper()
        
        # Check for Card Powered Off Event
        if "CARD POWERED OFF" in summary or item_type == "MSC_EVENT":
            raw_hex = getattr(trace_item, 'rawhex', '').replace(' ', '').upper()
            if raw_hex == "1900":
                self.add_issue(
                    ValidationSeverity.INFO,
                    "Card Event",
                    "Card Powered Off Event",
                    index,
                    getattr(trace_item, 'timestamp', None),
                    raw_hex,
                    command_details="Card power removed"
                )
        
        # Check for COLD RESET (card power on/refresh)
        if "COLD RESET" in summary or ("CARD EVENT" in summary and "RESET" in summary):
            self.add_issue(
                ValidationSeverity.INFO,
                "Card Event",
                "Card Event: COLD RESET (Power On/Refresh)",
                index,
                getattr(trace_item, 'timestamp', None),
                getattr(trace_item, 'rawhex', ''),
                command_details=summary
            )
    
    def _check_iccid_read(self, trace_item, index: int, summary: str, raw_hex: str):
        """Detect ICCID read operations and decode the ICCID."""
        trace_type = getattr(trace_item, 'type', '').lower()
        
        # Check for SELECT FILE - EF_ICCID
        if "SELECT FILE" in summary and "EF_ICCID" in summary:
            # Mark that we're expecting an ICCID read next
            self.pending_iccid_read = True
            self.iccid_select_index = index
            self.iccid_read_binary_seen = False
        
        # Look for READ BINARY command after SELECT FILE - EF_ICCID
        elif self.pending_iccid_read and "READ BINARY" in summary and trace_type == "apducommand":
            # Mark that we've seen READ BINARY and are now waiting for the response
            self.iccid_read_binary_seen = True
        
        # Check for APDU response with ICCID data (comes after READ BINARY command)
        elif self.pending_iccid_read and self.iccid_read_binary_seen and trace_type == "apduresponse" and "SW: 9000" in summary:
            # Try to extract ICCID data from the response
            iccid = None
            
            # Try to extract from raw hex (data + SW 9000)
            clean_hex = raw_hex.replace(' ', '').upper()
            # Look for 10-byte BCD data (20 hex chars) ending with 9000
            if clean_hex.endswith("9000") and len(clean_hex) >= 24:
                data_hex = clean_hex[:-4]  # Remove SW
                if len(data_hex) == 20:  # Exactly 10 bytes
                    iccid = self._decode_bcd_iccid(data_hex)
            
            # Fallback: look for Data field in the trace item tree
            if not iccid:
                data_hex = self._extract_apdu_data_field(trace_item)
                if data_hex and len(data_hex) == 20:  # Exactly 10 bytes (20 hex chars)
                    iccid = self._decode_bcd_iccid(data_hex)
            
            if iccid:
                self.add_issue(
                    ValidationSeverity.INFO,
                    "ICCID Detection",
                    iccid,
                    self.iccid_select_index,  # Use the SELECT FILE index, not READ BINARY index
                    getattr(trace_item, 'timestamp', None),
                    raw_hex,
                    command_details=f"ICCID: {iccid}"
                )
            
            # Reset the flags
            self.pending_iccid_read = False
            self.iccid_select_index = -1
            self.iccid_read_binary_seen = False
    
    def _check_dropped_link(self, trace_item, index: int, summary: str, raw_hex: str):
        """Detect dropped link events."""
        if "ENVELOPE" in summary and "CHANNEL STATUS" in summary:
            if "LINK DROPPED" in summary or "LINK OFF" in summary:
                self.add_issue(
                    ValidationSeverity.CRITICAL,
                    "Channel Status",
                    "Link Dropped - Channel connection lost",
                    index,
                    getattr(trace_item, 'timestamp', None),
                    raw_hex,
                    command_details=summary
                )
        # Also check details tree for Link Dropped status
        def _check_details_tree(node) -> bool:
            if not node:
                return False
            name = getattr(node, 'name', '') or ''
            val = getattr(node, 'value', '') or ''
            content = getattr(node, 'content', '') or ''
            if 'link dropped' in f"{name} {val} {content}".lower() or 'link off' in f"{name} {val} {content}".lower():
                return True
            for ch in getattr(node, 'children', []) or []:
                if _check_details_tree(ch):
                    return True
            return False
        if _check_details_tree(getattr(trace_item, 'details_tree', None)):
            self.add_issue(
                ValidationSeverity.CRITICAL,
                "Channel Status",
                "Link Dropped - Channel connection lost",
                index,
                getattr(trace_item, 'timestamp', None),
                raw_hex,
                command_details=summary
            )
    
    def _check_sw_5023(self, trace_item, index: int, summary: str, raw_hex: str):
        """Detect Status Word 5023 (technical problem)."""
        if "SW: 5023" in summary or "5023" in summary:
            clean_hex = raw_hex.replace(' ', '').upper()
            if "5023" in clean_hex:
                self.add_issue(
                    ValidationSeverity.CRITICAL,
                    "Status Word Error",
                    "SW: 5023 - Technical problem, no precise diagnosis",
                    index,
                    getattr(trace_item, 'timestamp', None),
                    raw_hex,
                    command_details=summary
                )
    
    def _check_bip_errors(self, trace_item, index: int, summary: str, raw_hex: str):
        """Detect Bearer Independent Protocol errors."""
        # Check for Terminal Response with BIP error (supports tags 03 or 83)
        if "TERMINAL RESPONSE" in summary:
            clean_hex = raw_hex.replace(' ', '').upper()

            # Look for Result TLV indicating Bearer Independent Protocol error
            # 03 = Result tag (simple TLV), 83 = Result tag (comprehension TLV)
            # Pattern: [03|83] 02 3A xx (xx = cause)
            if "03023A00" in clean_hex or "83023A00" in clean_hex or ("BEARER INDEPENDENT PROTOCOL ERROR" in summary and "NO SPECIFIC CAUSE" in summary):
                self.add_issue(
                    ValidationSeverity.CRITICAL,
                    "BIP Error",
                    "Bearer Independent Protocol Error - No specific cause",
                    index,
                    getattr(trace_item, 'timestamp', None),
                    raw_hex,
                    command_details=summary
                )
            else:
                # Extract any specific cause byte
                m = re.search(r'(?:03|83)023A([0-9A-F]{2})', clean_hex)
                if m:
                    cause_code = m.group(1)
                    self.add_issue(
                        ValidationSeverity.CRITICAL,
                        "BIP Error",
                        f"Bearer Independent Protocol Error - Cause: 0x{cause_code}",
                        index,
                        getattr(trace_item, 'timestamp', None),
                        raw_hex,
                        command_details=summary
                    )
    
    def _check_terminal_response_errors(self, trace_item, index: int, summary: str):
        """Detect TERMINAL RESPONSE with error results."""
        if "TERMINAL RESPONSE" not in summary:
            return
        
        # Check if details_tree contains a Result with "Error" or "ME unable to process command"
        try:
            if hasattr(trace_item, 'details_tree') and trace_item.details_tree:
                result_text = self._find_result_in_tree(trace_item.details_tree)
                if result_text and ("ERROR" in result_text.upper() or "ME UNABLE TO PROCESS COMMAND" in result_text.upper()):
                    # Extract command name from summary
                    command_name = "Unknown"
                    if "-" in summary:
                        parts = summary.split("-", 1)
                        if len(parts) > 1:
                            command_name = parts[1].strip()
                    
                    self.add_issue(
                        ValidationSeverity.WARNING,
                        "Terminal Response Error",
                        f"{command_name}: {result_text}",
                        index,
                        getattr(trace_item, 'timestamp', None),
                        getattr(trace_item, 'rawhex', ''),
                        command_details=summary
                    )
        except Exception:
            pass
    
    def _find_result_in_tree(self, node) -> Optional[str]:
        """Recursively search for Result > General Result in tree."""
        # Check if this node is "Result" and has children
        if hasattr(node, 'content') and node.content:
            if 'Result' in node.content and hasattr(node, 'children'):
                # Look for "General Result" child
                for child in node.children:
                    if hasattr(child, 'content') and 'General Result' in child.content:
                        # The value is part of the content string after ": "
                        if ': ' in child.content:
                            return child.content.split(': ', 1)[1]
                        return child.content
        
        # Recursively search children
        if hasattr(node, 'children'):
            for child in node.children:
                result = self._find_result_in_tree(child)
                if result:
                    return result
        return None
    
    def _extract_apdu_data_field(self, trace_item) -> Optional[str]:
        """Extract the Data field from APDU response."""
        try:
            # Navigate the details_tree to find Data field
            if hasattr(trace_item, 'details_tree') and trace_item.details_tree:
                return self._find_data_in_tree(trace_item.details_tree)
            return None
        except Exception:
            return None
    
    def _find_data_in_tree(self, node) -> Optional[str]:
        """Recursively search for Data field in tree."""
        if hasattr(node, 'name') and node.name and 'Data' in node.name:
            if hasattr(node, 'value') and node.value:
                return node.value.replace(' ', '').upper()
        
        if hasattr(node, 'children'):
            for child in node.children:
                result = self._find_data_in_tree(child)
                if result:
                    return result
        return None
    
    def _decode_bcd_iccid(self, hex_data: str) -> Optional[str]:
        """Decode BCD ICCID with swapped nibbles."""
        try:
            iccid = ""
            for i in range(0, len(hex_data), 2):
                byte = hex_data[i:i+2]
                # Swap nibbles
                swapped = byte[1] + byte[0]
                iccid += swapped
            
            # Remove any trailing 'F' padding
            iccid = iccid.rstrip('F')
            
            # Validate ICCID format (should be 19-20 digits starting with 89)
            if len(iccid) >= 18 and iccid.startswith('89'):
                return iccid
            return None
        except Exception:
            return None
    
    def _check_missing_terminal_response(self, trace_item, index: int, summary: str):
        """Detect missing TERMINAL RESPONSE after proactive OPEN/SEND/RECEIVE CHANNEL commands."""
        # Track proactive commands that require TERMINAL RESPONSE
        if "FETCH" in summary and any(cmd in summary for cmd in ["OPEN CHANNEL", "SEND DATA", "RECEIVE DATA", "CLOSE CHANNEL"]):
            # Store this as a pending command
            if not hasattr(self, 'pending_proactive_commands'):
                self.pending_proactive_commands = []
            self.pending_proactive_commands.append({
                'index': index,
                'timestamp': getattr(trace_item, 'timestamp', None),
                'command': summary
            })
        
        # Check if we got a TERMINAL RESPONSE
        if "TERMINAL RESPONSE" in summary:
            # Clear pending commands
            if hasattr(self, 'pending_proactive_commands'):
                self.pending_proactive_commands = []
    
    def _validate_state_machines(self, trace_item, index: int, summary: str):
        """Additional state machine validations."""
        # Check for envelope download without proper setup
        if "ENVELOPE" in summary and "EVENT DOWNLOAD" in summary:
            # Could add checks for proper event setup
            pass
    
    def _extract_channel_id(self, trace_item, summary: str) -> Optional[str]:
        """Extract channel ID from trace item."""
        # Look for channel ID patterns in summary
        import re
        match = re.search(r'channel\s*[:=]?\s*(\w+)', summary.lower())
        if match:
            return match.group(1)
        
        # Could also parse from raw data if needed
        return None
    
    def _extract_command_type(self, summary: str) -> str:
        """Extract command type from summary."""
        # Extract meaningful command description
        if "FETCH" in summary:
            return summary.strip()
        return "Unknown Command"
    
    def _contains_ip_pattern(self, raw_hex: str) -> bool:
        """Check if raw hex contains IP address patterns."""
        # Simple heuristic - look for patterns that might be IP addresses
        # This is a basic implementation, could be enhanced
        clean_hex = raw_hex.replace(' ', '')
        
        # Look for IPv4 patterns (4 bytes that could be IP)
        # More sophisticated parsing could be added here
        return len(clean_hex) >= 8  # At least 4 bytes
    
    def _check_fetch_timeouts(self, trace_item, index: int):
        """Check for FETCH commands that haven't received responses."""
        # Disabled - this was generating too many false positives
        # XTI traces typically have legitimate command/response patterns
        # that don't need this type of timeout validation
        pass
    
    def add_issue(self, severity: ValidationSeverity, category: str, message: str,
                  trace_index: int, timestamp: Optional[str] = None,
                  raw_data: Optional[str] = None, channel_id: Optional[str] = None,
                  command_details: Optional[str] = None):
        """Add a validation issue."""
        issue = ValidationIssue(
            severity=severity,
            category=category,
            message=message,
            trace_index=trace_index,
            timestamp=timestamp,
            raw_data=raw_data,
            channel_id=channel_id,
            command_details=command_details
        )
        self.issues.append(issue)
    
    def finalize_validation(self):
        """Finalize validation and check for unclosed channels."""
        # Check for unclosed channels
        for channel_id, state in self.open_channels.items():
            self.add_issue(
                ValidationSeverity.CRITICAL,
                "Resource Leak",
                f"Channel {channel_id} was opened but never closed",
                state.opened_at_index,
                state.opened_timestamp,
                None,
                channel_id
            )
        
        # Check for pending fetches - Disabled due to false positives
        # The XTI trace format has legitimate command/response patterns
        # that don't match simple FETCH/TERMINAL RESPONSE pairing
        # for fetch in self.pending_fetches:
        #     self.add_issue(
        #         ValidationSeverity.WARNING,
        #         "Missing Response",
        #         f"FETCH command did not receive TERMINAL RESPONSE: {fetch.command_type}",
        #         fetch.fetch_index,
        #         fetch.fetch_timestamp,
        #         None,
        #         command_details=fetch.command_type
        #     )
    
    def get_issues_by_severity(self, severity: ValidationSeverity) -> List[ValidationIssue]:
        """Get all issues of a specific severity."""
        return [issue for issue in self.issues if issue.severity == severity]
    
    def get_critical_issues(self) -> List[ValidationIssue]:
        """Get all critical issues."""
        return self.get_issues_by_severity(ValidationSeverity.CRITICAL)
    
    def get_warning_issues(self) -> List[ValidationIssue]:
        """Get all warning issues."""
        return self.get_issues_by_severity(ValidationSeverity.WARNING)
    
    def get_info_issues(self) -> List[ValidationIssue]:
        """Get all informational issues."""
        return self.get_issues_by_severity(ValidationSeverity.INFO)

    def get_all_issues(self) -> List[ValidationIssue]:
        """Return all collected validation issues (any severity).

        Kept for backward compatibility with export/report helpers.
        """
        return list(self.issues)
    
    def get_summary(self) -> str:
        """Get validation summary."""
        critical_count = len(self.get_critical_issues())
        warning_count = len(self.get_warning_issues())
        info_count = len(self.get_info_issues())
        
        return (f"Validation complete: {self.processed_count} items processed. "
                f"Critical: {critical_count}, Warnings: {warning_count}, Info: {info_count}")