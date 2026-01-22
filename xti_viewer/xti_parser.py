"""
XTI (Universal Tracer) file parser for extracting trace items and interpretation data.
"""
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional, List, Set
from pathlib import Path
import re
from datetime import datetime


@dataclass
class TreeNode:
    """Represents a node in the interpretation tree."""
    content: str
    children: List['TreeNode']
    
    def __init__(self, content: str):
        self.content = content
        self.children = []
    
    def add_child(self, child: 'TreeNode'):
        """Add a child node to this node."""
        self.children.append(child)


@dataclass
class TraceItem:
    """Represents a single trace item from the XTI file."""
    protocol: Optional[str]
    type: Optional[str]
    summary: str  # first interpreted result content
    rawhex: Optional[str]
    timestamp: Optional[str]  # formatted if available
    details_tree: TreeNode  # entire interpreted tree
    timestamp_sort_key: str = ""  # for chronological sorting


@dataclass
class ChannelSession:
    """Represents a channel communication session (OPEN → CLOSE)."""
    channel_id: Optional[str]
    opened_at: Optional[datetime]
    closed_at: Optional[datetime]
    protocol: Optional[str]
    port: Optional[int]
    ips: Set[str]
    traceitem_indexes: List[int]


# Regular expressions for IP and channel ID extraction
IPV4_RE = re.compile(r"Address:\s*(\d{1,3}[:\.]?\d{1,3}[:\.]?\d{1,3}[:\.]?\d{1,3})")
CHAN_ID_RE = re.compile(r"(?:Allocated Channel|Channel Identifier)\s*:\s*(\d+)", re.I)

# Built-in IP to label mapping (defaults). User-configurable TAC/DP+/DNS IP lists
# from config.json are merged on top at runtime.
_STATIC_IP_MAP = {
    "212.30.200.199": "SIMIN DNS Serveur",
    "212.30.200.200": "SIMIN DNS Serveur",
    # Public DNS Servers
    "8.8.8.8": "Google DNS",
    "8.8.4.4": "Google DNS",
    "1.1.1.1": "Cloudflare DNS",
    "1.0.0.1": "Cloudflare DNS",
    "9.9.9.9": "Quad9 DNS",
    "208.67.222.222": "OpenDNS",
    "208.67.220.220": "OpenDNS",
}


def _get_runtime_ip_map() -> dict:
    """Return an IP→label map including user-configured classification lists."""
    m = dict(_STATIC_IP_MAP)

    try:
        # app_config lives at repo root (sibling of xti_viewer)
        from app_config import load_config

        cfg = load_config() or {}
        cl = cfg.get('classification', {}) if isinstance(cfg, dict) else {}

        dns_ips = cl.get('dns_ips', []) if isinstance(cl, dict) else []
        dp_ips = cl.get('dp_plus_ips', []) if isinstance(cl, dict) else []
        tac_ips = cl.get('tac_ips', []) if isinstance(cl, dict) else []

        # Apply in increasing priority so TAC wins if duplicates exist.
        try:
            for ip in dns_ips or []:
                s = str(ip).strip()
                if s:
                    # Generic DNS label for custom resolver IPs.
                    m[s] = 'DNS'
        except Exception:
            pass

        try:
            for ip in dp_ips or []:
                s = str(ip).strip()
                if s:
                    m[s] = 'DP+'
        except Exception:
            pass

        try:
            for ip in tac_ips or []:
                s = str(ip).strip()
                if s:
                    m[s] = 'TAC'
        except Exception:
            pass
    except Exception:
        # If config system isn't available, keep built-ins only.
        pass

    return m


class XTIParser:
    """Parser for XTI (Universal Tracer) XML files."""
    
    def __init__(self):
        self.trace_items: List[TraceItem] = []
        self.channel_sessions: List[ChannelSession] = []
    
    def parse_file(self, file_path: str) -> List[TraceItem]:
        """
        Parse an XTI file and extract all trace items.
        
        Args:
            file_path: Path to the XTI file
            
        Returns:
            List of TraceItem objects
            
        Raises:
            ET.ParseError: If XML is malformed
            FileNotFoundError: If file doesn't exist
            ValueError: If required elements are missing
        """
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Validate root element
            if root.tag != 'tracedata':
                raise ValueError(f"Expected root element 'tracedata', got '{root.tag}'")
            
            trace_items = []
            
            # Process each traceitem
            for traceitem in root.findall('.//traceitem'):
                trace_item = self._parse_traceitem(traceitem)
                if trace_item:
                    trace_items.append(trace_item)
            
            # Sort chronologically by timestamp (oldest to newest)
            trace_items.sort(key=lambda item: item.timestamp_sort_key)
            
            # Reconstruct channel sessions
            self.channel_sessions = self._reconstruct_sessions(trace_items)
            
            self.trace_items = trace_items
            return trace_items
            
        except ET.ParseError as e:
            raise ET.ParseError(f"XML parsing error: {e}")
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {file_path}")
    
    def _parse_traceitem(self, traceitem: ET.Element) -> Optional[TraceItem]:
        """
        Parse a single traceitem element.
        
        Args:
            traceitem: The traceitem XML element
            
        Returns:
            TraceItem object or None if parsing fails
        """
        # Extract attributes
        protocol = traceitem.get('protocol')
        item_type = traceitem.get('type')
        
        # Extract raw hex data
        data_elem = traceitem.find('data')
        rawhex = data_elem.get('rawhex') if data_elem is not None else None
        
        # Extract interpretation
        interpretation = traceitem.find('interpretation')
        if interpretation is None:
            # Skip items without interpretation
            return None
        
        # Find the first interpretedresult for summary
        first_result = interpretation.find('interpretedresult')
        if first_result is None:
            return None
        
        summary = first_result.get('content', '').strip()
        if not summary:
            return None
        
        # Build the complete interpretation tree
        details_tree = self._build_interpretation_tree(first_result)
        
        # Extract timestamp (search for various time-related attributes)
        timestamp = self._extract_timestamp(traceitem)
        
        return TraceItem(
            protocol=protocol,
            type=item_type,
            summary=summary,
            rawhex=rawhex,
            timestamp=timestamp,
            details_tree=details_tree,
            timestamp_sort_key=self.get_timestamp_sort_key(timestamp)
        )
    
    def _build_interpretation_tree(self, element: ET.Element) -> TreeNode:
        """
        Recursively build the interpretation tree from XML elements.
        
        Args:
            element: The interpretedresult XML element
            
        Returns:
            TreeNode representing the interpretation hierarchy
        """
        content = element.get('content', '').strip()
        node = TreeNode(content)
        
        # Recursively process child interpretedresult elements
        for child in element.findall('interpretedresult'):
            child_node = self._build_interpretation_tree(child)
            node.add_child(child_node)
        
        return node
    
    def _extract_timestamp(self, traceitem: ET.Element) -> Optional[str]:
        """
        Extract timestamp information from various possible attributes.
        
        Args:
            traceitem: The traceitem XML element
            
        Returns:
            Formatted timestamp string or None if not found
        """
        # First check for formatted timestamp in the Universal Tracer format
        timestamp_elem = traceitem.find('timestamp')
        if timestamp_elem is not None:
            # Check for formatted timestamp first
            formatted_elem = timestamp_elem.find('formatted')
            if formatted_elem is not None and formatted_elem.text:
                return formatted_elem.text
            
            # Check for standard timestamp structure
            standard_elem = timestamp_elem.find('standard')
            if standard_elem is not None:
                # Extract individual components
                year = standard_elem.get('year', '')
                month = standard_elem.get('month', '').zfill(2)
                day = standard_elem.get('date', '').zfill(2)  # Note: 'date' not 'day'
                hour = standard_elem.get('hour', '').zfill(2)
                minute = standard_elem.get('minute', '').zfill(2)
                second = standard_elem.get('second', '').zfill(2)
                millisecond = standard_elem.get('millisecond', '').zfill(3)
                
                if all([year, month, day, hour, minute, second]):
                    if millisecond:
                        return f"{month}/{day}/{year} {hour}:{minute}:{second}:{millisecond}"
                    else:
                        return f"{month}/{day}/{year} {hour}:{minute}:{second}"
        
        # Fallback: look for timestamp attributes in the element itself
        timestamp_attrs = [
            'date', 'time', 'timestamp', 'datetime',
            'year', 'month', 'day', 'hour', 'minute', 'second',
            'millisecond', 'nanosecond'
        ]
        
        timestamp_parts = {}
        
        # Search in the traceitem and its descendants
        for elem in [traceitem] + list(traceitem.iter()):
            for attr_name, attr_value in elem.attrib.items():
                if attr_name.lower() in timestamp_attrs:
                    timestamp_parts[attr_name.lower()] = attr_value
        
        # Try to construct a meaningful timestamp
        if 'timestamp' in timestamp_parts:
            return timestamp_parts['timestamp']
        elif 'datetime' in timestamp_parts:
            return timestamp_parts['datetime']
        elif 'date' in timestamp_parts and 'time' in timestamp_parts:
            return f"{timestamp_parts['date']} {timestamp_parts['time']}"
        elif any(key in timestamp_parts for key in ['year', 'month', 'day']):
            # Try to build from individual components
            year = timestamp_parts.get('year', '')
            month = timestamp_parts.get('month', '')
            day = timestamp_parts.get('day', '')
            hour = timestamp_parts.get('hour', '')
            minute = timestamp_parts.get('minute', '')
            second = timestamp_parts.get('second', '')
            
            date_part = f"{year}-{month}-{day}" if all([year, month, day]) else ""
            time_part = f"{hour}:{minute}:{second}" if all([hour, minute, second]) else ""
            
            if date_part and time_part:
                return f"{date_part} {time_part}"
            elif date_part:
                return date_part
            elif time_part:
                return time_part
        
        return None
    
    def get_timestamp_sort_key(self, timestamp: Optional[str]) -> str:
        """
        Get a sort key for timestamp comparison.
        
        Args:
            timestamp: The timestamp string
            
        Returns:
            Sort key string that can be used for chronological ordering
        """
        if not timestamp:
            return "0000-00-00T00:00:00.000"  # Sort missing timestamps first
        
        # Try to normalize various timestamp formats for sorting
        import re
        
        # Handle Universal Tracer format: MM/DD/YYYY HH:MM:SS:mmm.nnnnnn
        ut_match = re.match(r'(\d{2})/(\d{2})/(\d{4}) (\d{2}):(\d{2}):(\d{2}):(\d{3})(?:\.(\d+))?', timestamp)
        if ut_match:
            month, day, year, hour, minute, second, ms = ut_match.groups()[:7]
            # Convert to ISO format for proper sorting: YYYY-MM-DDTHH:MM:SS.mmm
            return f"{year}-{month}-{day}T{hour}:{minute}:{second}.{ms}"
        
        # Handle Universal Tracer format without milliseconds: MM/DD/YYYY HH:MM:SS
        ut_match_simple = re.match(r'(\d{2})/(\d{2})/(\d{4}) (\d{2}):(\d{2}):(\d{2})', timestamp)
        if ut_match_simple:
            month, day, year, hour, minute, second = ut_match_simple.groups()
            return f"{year}-{month}-{day}T{hour}:{minute}:{second}.000"
        
        # Handle ISO format timestamps
        if re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', timestamp):
            return timestamp
        
        # Handle date-time with space separator
        if re.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', timestamp):
            return timestamp.replace(' ', 'T')
        
        # Handle date only
        if re.match(r'\d{4}-\d{2}-\d{2}', timestamp):
            return f"{timestamp}T00:00:00.000"
        
        # Handle time only (use today's date)
        if re.match(r'\d{2}:\d{2}:\d{2}', timestamp):
            return f"2023-01-01T{timestamp}.000"
        
        # For other formats, return as-is for basic string sorting
        return timestamp
    
    def _reconstruct_sessions(self, trace_items: List[TraceItem]) -> List[ChannelSession]:
        """
        Reconstruct channel sessions from trace items.
        
        Args:
            trace_items: List of trace items in chronological order
            
        Returns:
            List of reconstructed channel sessions
        """
        sessions = []
        open_sessions = []  # Sessions waiting for CLOSE
        
        for idx, item in enumerate(trace_items):
            summary = item.summary.strip()
            summary_u = summary.upper()
            
            # Check for OPEN CHANNEL (FETCH response / proactive command)
            # Accept variants like: "FETCH - OPEN CHANNEL" and "FETCH - FETCH - OPEN CHANNEL".
            if summary_u.startswith("FETCH") and ("OPEN CHANNEL" in summary_u):
                # Extract IPs from the interpretation tree
                ips = extract_ips_from_interpretation_tree(item.details_tree)
                
                # Extract protocol and port
                protocol, port = extract_protocol_and_port_from_interpretation(item.details_tree)
                
                # Parse timestamp to datetime
                opened_at = None
                if item.timestamp:
                    try:
                        # Parse Universal Tracer format: MM/DD/YYYY HH:MM:SS:mmm
                        import re
                        ut_match = re.match(r'(\d{2})/(\d{2})/(\d{4}) (\d{2}):(\d{2}):(\d{2}):(\d{3})', item.timestamp)
                        if ut_match:
                            month, day, year, hour, minute, second, ms = ut_match.groups()
                            opened_at = datetime(int(year), int(month), int(day), 
                                               int(hour), int(minute), int(second), 
                                               int(ms) * 1000)  # Convert ms to microseconds
                    except (ValueError, AttributeError):
                        pass
                
                # Include the preceding FETCH command (apducommand) and SW status
                # Pattern: apduresponse "SW:..." → apducommand "FETCH" → apduresponse "FETCH - OPEN CHANNEL"
                indexes_to_add = []
                if idx >= 2 and trace_items[idx - 1].type == "apducommand" and trace_items[idx - 1].summary.strip() == "FETCH":
                    if "SW:" in trace_items[idx - 2].summary:
                        indexes_to_add.append(idx - 2)  # SW status
                    indexes_to_add.append(idx - 1)  # FETCH command
                elif idx >= 1 and trace_items[idx - 1].type == "apducommand" and trace_items[idx - 1].summary.strip() == "FETCH":
                    indexes_to_add.append(idx - 1)  # FETCH command
                indexes_to_add.append(idx)  # FETCH response
                
                # Create new session
                session = ChannelSession(
                    channel_id=None,  # Will be filled when we see TERMINAL RESPONSE
                    opened_at=opened_at,
                    closed_at=None,
                    protocol=protocol,
                    port=port,
                    ips=ips,
                    traceitem_indexes=indexes_to_add
                )
                
                sessions.append(session)
                open_sessions.append(session)
            
            # Check for TERMINAL RESPONSE - OPEN CHANNEL
            elif summary_u.startswith("TERMINAL RESPONSE") and ("OPEN CHANNEL" in summary_u):
                # Extract channel ID
                channel_id = extract_channel_id_from_interpretation(item.details_tree)
                if open_sessions:
                    # Assign to the most recent open session
                    if channel_id:
                        open_sessions[-1].channel_id = channel_id
                    open_sessions[-1].traceitem_indexes.append(idx)
                    # Include the SW response that follows TERMINAL RESPONSE
                    if (idx + 1 < len(trace_items) and 
                        trace_items[idx + 1].type == "apduresponse" and 
                        "SW:" in trace_items[idx + 1].summary):
                        open_sessions[-1].traceitem_indexes.append(idx + 1)
            
            # Check for TERMINAL RESPONSE - CLOSE CHANNEL
            elif summary_u.startswith("TERMINAL RESPONSE") and ("CLOSE CHANNEL" in summary_u):
                # Add to the most recently closed session if it exists
                if sessions:
                    # Find the session that was just closed
                    for session in reversed(sessions):
                        if session.traceitem_indexes and idx > max(session.traceitem_indexes):
                            # This is the TERMINAL RESPONSE for the close
                            session.traceitem_indexes.append(idx)
                            # Also include the SW response that follows
                            if (idx + 1 < len(trace_items) and 
                                trace_items[idx + 1].type == "apduresponse" and 
                                "SW:" in trace_items[idx + 1].summary):
                                session.traceitem_indexes.append(idx + 1)
                            break
            
            # Check for other channel-related commands
            elif (
                (summary_u.startswith("FETCH") and ("SEND DATA" in summary_u or "RECEIVE DATA" in summary_u)) or
                (summary_u.startswith("TERMINAL RESPONSE") and ("SEND DATA" in summary_u or "RECEIVE DATA" in summary_u))
            ):
                # Try to match to a session by channel ID first
                matched_session = None
                
                if open_sessions:
                    # Look for channel ID in the interpretation
                    item_channel_id = extract_channel_id_from_interpretation(item.details_tree)
                    
                    if item_channel_id:
                        # Find session with matching channel ID
                        for session in open_sessions:
                            if session.channel_id == item_channel_id:
                                matched_session = session
                                break
                    
                    # Fallback: assign to most recent open session without close
                    if not matched_session and open_sessions:
                        matched_session = open_sessions[-1]
                    
                    if matched_session:
                        # Include preceding command if this is a response
                        # Pattern: apducommand "FETCH" → apduresponse "FETCH - SEND/RECEIVE DATA"
                        # Pattern: apduresponse "SW:..." → apducommand "FETCH" → apduresponse "FETCH - SEND/RECEIVE DATA"
                        if item.type == "apduresponse" and summary_u.startswith("FETCH"):
                            # Look for preceding SW status and FETCH command
                            if idx >= 2 and trace_items[idx - 1].type == "apducommand" and trace_items[idx - 1].summary.strip() == "FETCH":
                                if idx - 2 not in matched_session.traceitem_indexes and "SW:" in trace_items[idx - 2].summary:
                                    matched_session.traceitem_indexes.append(idx - 2)  # SW status
                                if idx - 1 not in matched_session.traceitem_indexes:
                                    matched_session.traceitem_indexes.append(idx - 1)  # FETCH command
                            elif idx >= 1 and trace_items[idx - 1].type == "apducommand" and trace_items[idx - 1].summary.strip() == "FETCH":
                                if idx - 1 not in matched_session.traceitem_indexes:
                                    matched_session.traceitem_indexes.append(idx - 1)  # FETCH command
                        
                        matched_session.traceitem_indexes.append(idx)
            
            # Check for CLOSE CHANNEL (FETCH command)  
            elif summary_u.startswith("FETCH") and ("CLOSE CHANNEL" in summary_u):
                # Try to match to a session by channel ID first
                closed_session = None
                
                # Include preceding FETCH command and SW status
                indexes_to_add = []
                if idx >= 2 and trace_items[idx - 1].type == "apducommand" and trace_items[idx - 1].summary.strip() == "FETCH":
                    if "SW:" in trace_items[idx - 2].summary:
                        indexes_to_add.append(idx - 2)  # SW status
                    indexes_to_add.append(idx - 1)  # FETCH command
                elif idx >= 1 and trace_items[idx - 1].type == "apducommand" and trace_items[idx - 1].summary.strip() == "FETCH":
                    indexes_to_add.append(idx - 1)  # FETCH command
                indexes_to_add.append(idx)  # CLOSE CHANNEL response
                
                if open_sessions:
                    item_channel_id = extract_channel_id_from_interpretation(item.details_tree)
                    
                    if item_channel_id:
                        # Find session with matching channel ID
                        for i, session in enumerate(open_sessions):
                            if session.channel_id == item_channel_id:
                                closed_session = session
                                open_sessions.pop(i)
                                break
                    
                    # Fallback: close most recent open session
                    if not closed_session and open_sessions:
                        closed_session = open_sessions.pop()
                    
                    if closed_session:
                        # Parse close timestamp
                        closed_at = None
                        if item.timestamp:
                            try:
                                import re
                                ut_match = re.match(r'(\d{2})/(\d{2})/(\d{4}) (\d{2}):(\d{2}):(\d{2}):(\d{3})', item.timestamp)
                                if ut_match:
                                    month, day, year, hour, minute, second, ms = ut_match.groups()
                                    closed_at = datetime(int(year), int(month), int(day), 
                                                       int(hour), int(minute), int(second), 
                                                       int(ms) * 1000)
                            except (ValueError, AttributeError):
                                pass
                        
                        closed_session.closed_at = closed_at
                        # Add all the close channel related indexes
                        for close_idx in indexes_to_add:
                            if close_idx not in closed_session.traceitem_indexes:
                                closed_session.traceitem_indexes.append(close_idx)
        
        return sessions
    
    def get_channel_groups(self) -> List[dict]:
        """
        Get channel sessions in chronological order (not grouped by duplicates).
        
        Returns:
            List of dictionaries representing individual channel sessions
        """
        result = []
        
        # Sort sessions by opening time
        sorted_sessions = sorted(self.channel_sessions, key=lambda s: s.opened_at or datetime.min)
        
        for i, session in enumerate(sorted_sessions):
            # Determine server label from IPs
            server_label = tag_server_from_ips(session.ips)
            
            # Handle DNS channels opened by ME
            if not session.ips:
                ip_display = ["(DNS by ME)"]
            else:
                ip_display = list(session.ips)
            
            # Create individual session entry
            session_entry = {
                "type": "FETCH - OPEN CHANNEL",
                "port": session.port or "",
                "protocol": session.protocol or "",  
                "server": server_label,
                "ips": ip_display,
                "ip_display": "<br>".join(ip_display),
                "session_number": i + 1,
                "opened_at": session.opened_at.strftime("%H:%M:%S") if session.opened_at else "Unknown",
                "closed_at": session.closed_at.strftime("%H:%M:%S") if session.closed_at else "Not closed",
                "duration": self._calculate_session_duration(session),
                "sessions": [session]  # Keep for compatibility
            }
            
            result.append(session_entry)
        
        return result
    
    def _calculate_session_duration(self, session) -> str:
        """Calculate session duration in human-readable format."""
        if session.opened_at and session.closed_at:
            duration = session.closed_at - session.opened_at
            total_seconds = duration.total_seconds()
            
            if total_seconds < 1:
                return f"{total_seconds:.2f}s"
            elif total_seconds < 60:
                return f"{total_seconds:.1f}s"
            else:
                minutes = int(total_seconds // 60)
                seconds = total_seconds % 60
                return f"{minutes}m {seconds:.1f}s"
        else:
            return "Unknown"
    
    def get_channel_groups_legacy(self) -> List[dict]:
        """
        Get channel groups aggregated by IP set (original grouping method).
        
        Returns:
            List of dictionaries representing channel groups
        """
        groups = {}
        
        for session in self.channel_sessions:
            # Create group key based on sorted IPs (and optionally protocol/port)
            ip_tuple = tuple(sorted(session.ips)) if session.ips else ("(none)",)
            group_key = ip_tuple
            
            if group_key not in groups:
                # Determine server label from IPs
                server_label = tag_server_from_ips(session.ips)
                
                # Handle DNS channels opened by ME
                if not session.ips:
                    ip_display = ["(DNS by ME)"]
                else:
                    ip_display = list(session.ips)
                
                groups[group_key] = {
                    "type": "FETCH - OPEN CHANNEL",
                    "port": session.port or "",
                    "protocol": session.protocol or "",  
                    "server": server_label,
                    "ips": ip_display,
                    "sessions": []
                }
            
            groups[group_key]["sessions"].append(session)
        
        # Convert to list and format IPs for display
        result = []
        for group_data in groups.values():
            group_data["ip_display"] = "<br>".join(group_data["ips"])
            result.append(group_data)
        
        # Sort by server label then by IP
        result.sort(key=lambda x: (x["server"], x["ip_display"]))
        
        return result


def extract_ips_from_interpretation_tree(root_node: TreeNode) -> Set[str]:
    """
    Extract all IPv4 addresses from an interpretation tree.
    
    Args:
        root_node: Root node of the interpretation tree
        
    Returns:
        Set of IPv4 addresses found in the tree
    """
    ips = set()
    
    def walk(node: TreeNode):
        if node.content:
            # Extract IPs from node content using regex
            found_ips = IPV4_RE.findall(node.content)
            # Normalize IP format (replace colons with dots)
            normalized_ips = [ip.replace(':', '.') for ip in found_ips]
            ips.update(normalized_ips)
        
        # Recursively walk children
        for child in node.children:
            walk(child)
    
    walk(root_node)
    return ips


def tag_server_from_ips(ips: Set[str]) -> str:
    """
    Tag server based on IPs found in the session.
    
    Args:
        ips: Set of IP addresses from the session
        
    Returns:
        Server label from configured IP lists / built-in map, "ME" for DNS channels, or "Unknown"
    """
    # If no IPs found, this is likely a DNS channel opened by ME
    if not ips:
        return "ME"
    
    ip_map = _get_runtime_ip_map()
    for ip in ips:
        if ip in ip_map:
            return ip_map[ip]
    return "Unknown"


def extract_channel_id_from_interpretation(root_node: TreeNode) -> Optional[str]:
    """
    Extract channel ID from a TERMINAL RESPONSE - OPEN CHANNEL interpretation.
    
    Args:
        root_node: Root node of the interpretation tree
        
    Returns:
        Channel ID if found, None otherwise
    """
    def walk(node: TreeNode):
        if node.content:
            # Look for channel ID pattern
            match = CHAN_ID_RE.search(node.content)
            if match:
                return match.group(1)
        
        # Recursively walk children
        for child in node.children:
            result = walk(child)
            if result:
                return result
        
        return None
    
    return walk(root_node)


def extract_protocol_and_port_from_interpretation(root_node: TreeNode):
    """
    Extract protocol and port from OPEN CHANNEL interpretation.
    
    Args:
        root_node: Root node of the interpretation tree
        
    Returns:
        Tuple of (protocol, port) if found, (None, None) otherwise
    """
    protocol = None
    port = None
    
    def walk(node: TreeNode):
        nonlocal protocol, port
        if node.content:
            # Look for protocol patterns
            if "TCP" in node.content.upper():
                protocol = "TCP"
            elif "UDP" in node.content.upper():
                protocol = "UDP"
            
            # Look for port patterns (simple regex for port numbers)
            port_match = re.search(r"Port Number[:\s]*(\d+)", node.content, re.I)
            if port_match:
                port = int(port_match.group(1))
        
        # Recursively walk children
        for child in node.children:
            walk(child)
    
    walk(root_node)
    return protocol, port


def main():
    """Test the parser with a sample file."""
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python xti_parser.py <xti_file>")
        sys.exit(1)
    
    parser = XTIParser()
    try:
        trace_items = parser.parse_file(sys.argv[1])
        print(f"Parsed {len(trace_items)} trace items")
        
        for i, item in enumerate(trace_items[:5]):  # Show first 5 items
            print(f"\n--- Item {i+1} ---")
            print(f"Protocol: {item.protocol}")
            print(f"Type: {item.type}")
            print(f"Summary: {item.summary}")
            print(f"Timestamp: {item.timestamp}")
            print(f"Raw hex length: {len(item.rawhex) if item.rawhex else 0}")
            print(f"Tree children: {len(item.details_tree.children)}")
    
    except Exception as e:
        print(f"Error parsing file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()