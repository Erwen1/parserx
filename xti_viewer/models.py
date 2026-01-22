"""
Qt models for the XTI Viewer application.
"""
from PySide6.QtCore import Qt, QAbstractItemModel, QModelIndex, Signal, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem, QBrush, QColor
from typing import List, Optional, Any, Set, Dict, Tuple
from dataclasses import dataclass
from .xti_parser import TraceItem, TreeNode


@dataclass
class SessionNavigator:
    """Gestionnaire pour la navigation rapide entre sessions/channels/commands."""
    
    def __init__(self):
        self.sessions_by_protocol: Dict[str, List[TraceItem]] = {}
        self.sessions_by_channel: Dict[str, List[TraceItem]] = {}
        self.sessions_by_command_type: Dict[str, List[TraceItem]] = {}
        self.session_index_cache: List[TraceItem] = []
        
    def analyze_sessions(self, trace_items: List[TraceItem]):
        """Analyse les trace items pour créer les groupes de navigation."""
        self.sessions_by_protocol.clear()
        self.sessions_by_channel.clear()
        self.sessions_by_command_type.clear()
        self.session_index_cache = sorted(trace_items, key=lambda x: x.timestamp_sort_key)
        
        for item in trace_items:
            # Grouper par protocole
            protocol = item.protocol or "Unknown"
            if protocol not in self.sessions_by_protocol:
                self.sessions_by_protocol[protocol] = []
            self.sessions_by_protocol[protocol].append(item)
            
            # Grouper par channel (extraire depuis summary)
            channel = self._extract_channel_info(item)
            if channel:
                if channel not in self.sessions_by_channel:
                    self.sessions_by_channel[channel] = []
                self.sessions_by_channel[channel].append(item)
            
            # Grouper par type de commande
            command_type = self._extract_command_type(item)
            if command_type:
                if command_type not in self.sessions_by_command_type:
                    self.sessions_by_command_type[command_type] = []
                self.sessions_by_command_type[command_type].append(item)
    
    def _extract_channel_info(self, item: TraceItem) -> Optional[str]:
        """Extrait l'info de channel depuis le summary."""
        import re
        
        # Chercher patterns de channel
        patterns = [
            r'Channel\s*[#:]?\s*(\d+)',
            r'Ch\s*(\d+)',
            r'OPEN CHANNEL.*(\d+)',
            r'CLOSE CHANNEL.*(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, item.summary, re.IGNORECASE)
            if match:
                return f"Channel {match.group(1)}"
        
        # Chercher dans les protocols BIP
        if item.protocol and "BIP" in item.protocol.upper():
            return "BIP Session"
            
        return None
    
    def _extract_command_type(self, item: TraceItem) -> Optional[str]:
        """Extrait le type de commande depuis le summary."""
        import re
        
        # Types de commandes STK/BIP communs
        command_types = [
            "FETCH", "TERMINAL RESPONSE", "OPEN CHANNEL", "CLOSE CHANNEL",
            "SEND DATA", "RECEIVE DATA", "GET CHANNEL STATUS", "DISPLAY TEXT", 
            "GET INKEY", "GET INPUT", "SELECT ITEM", "SET UP MENU", "PROVIDE LOCAL INFO"
        ]
        
        summary_upper = item.summary.upper()
        
        for cmd_type in command_types:
            if cmd_type in summary_upper:
                return cmd_type
        
        # Fallback: extraire depuis pattern "Type: XXX"
        type_match = re.search(r'Type:\s*([^,\(]+)', item.summary)
        if type_match:
            return type_match.group(1).strip()
            
        return "Other"
    
    def get_next_in_same_session(self, current_item: TraceItem) -> Optional[TraceItem]:
        """Trouve le prochain item dans la même session (même protocole et même channel si possible)."""
        try:
            current_index = self.session_index_cache.index(current_item)
        except ValueError:
            return None
        
        # Commencer par chercher dans le même channel si possible
        channel = self._extract_channel_info(current_item)
        if channel and channel in self.sessions_by_channel:
            channel_items = self.sessions_by_channel[channel]
            if len(channel_items) > 1:
                try:
                    channel_index = channel_items.index(current_item)
                    next_channel_index = (channel_index + 1) % len(channel_items)
                    return channel_items[next_channel_index]
                except ValueError:
                    pass
        
        # Sinon chercher dans le même protocole
        protocol = current_item.protocol
        if protocol and protocol in self.sessions_by_protocol:
            protocol_items = self.sessions_by_protocol[protocol]
            if len(protocol_items) > 1:
                try:
                    protocol_index = protocol_items.index(current_item)
                    next_protocol_index = (protocol_index + 1) % len(protocol_items)
                    return protocol_items[next_protocol_index]
                except ValueError:
                    pass
        
        # Fallback: item suivant chronologique
        if current_index + 1 < len(self.session_index_cache):
            return self.session_index_cache[current_index + 1]
        
        return None
    
    def get_previous_in_same_session(self, current_item: TraceItem) -> Optional[TraceItem]:
        """Trouve l'item précédent dans la même session (même protocole et même channel si possible)."""
        try:
            current_index = self.session_index_cache.index(current_item)
        except ValueError:
            return None
        
        # Commencer par chercher dans le même channel si possible
        channel = self._extract_channel_info(current_item)
        if channel and channel in self.sessions_by_channel:
            channel_items = self.sessions_by_channel[channel]
            if len(channel_items) > 1:
                try:
                    channel_index = channel_items.index(current_item)
                    prev_channel_index = (channel_index - 1) % len(channel_items)
                    return channel_items[prev_channel_index]
                except ValueError:
                    pass
        
        # Sinon chercher dans le même protocole
        protocol = current_item.protocol
        if protocol and protocol in self.sessions_by_protocol:
            protocol_items = self.sessions_by_protocol[protocol]
            if len(protocol_items) > 1:
                try:
                    protocol_index = protocol_items.index(current_item)
                    prev_protocol_index = (protocol_index - 1) % len(protocol_items)
                    return protocol_items[prev_protocol_index]
                except ValueError:
                    pass
        
        # Fallback: item précédent chronologique  
        if current_index > 0:
            return self.session_index_cache[current_index - 1]
        
        return None


@dataclass
class CommandResponsePair:
    """Représente une paire commande/réponse FETCH ↔ TERMINAL RESPONSE."""
    fetch_item: TraceItem
    response_item: Optional[TraceItem] = None
    command_number: Optional[int] = None
    command_type: Optional[str] = None
    response_result: Optional[str] = None
    is_complete: bool = False
    duration_ms: Optional[float] = None
    
    def get_status(self) -> str:
        """Retourne le statut de la paire."""
        if not self.response_item:
            return "⏳ Pending"
        elif self.response_result and "9000" in self.response_result:
            return "✅ Success"
        elif self.response_result and ("91" in self.response_result or "9000" in self.response_result):
            return "✅ OK"
        else:
            return "❌ Error"
    
    def get_duration_display(self) -> str:
        """Retourne la durée formatée."""
        if self.duration_ms is None:
            return "N/A"
        if self.duration_ms < 1000:
            return f"{self.duration_ms:.0f}ms"
        else:
            return f"{self.duration_ms/1000:.2f}s"


class CommandResponsePairingManager:
    """Gestionnaire pour le pairing automatique FETCH ↔ TERMINAL RESPONSE."""
    
    def __init__(self):
        self.pairs: List[CommandResponsePair] = []
        self.pending_fetches: Dict[int, CommandResponsePair] = {}  # command_number -> pair
        
    def analyze_trace_items(self, trace_items: List[TraceItem]) -> List[CommandResponsePair]:
        """Analyse les trace items et crée les paires commande/réponse."""
        self.pairs.clear()
        self.pending_fetches.clear()
        
        # Trier par timestamp pour analyse séquentielle
        sorted_items = sorted(trace_items, key=lambda item: item.timestamp_sort_key)
        
        for item in sorted_items:
            if self._is_fetch_command(item):
                self._process_fetch_command(item)
            elif self._is_terminal_response(item):
                self._process_terminal_response(item)
        
        # Calculer les durées pour les paires complètes
        self._calculate_durations()
        
        return self.pairs
    
    def _is_fetch_command(self, item: TraceItem) -> bool:
        """Vérifie si l'item est une commande FETCH."""
        return (item.type and item.type.upper() == "COMMAND" and
                "FETCH" in item.summary.upper())
    
    def _is_terminal_response(self, item: TraceItem) -> bool:
        """Vérifie si l'item est une réponse TERMINAL RESPONSE."""
        return (item.type and item.type.upper() == "COMMAND" and
                "TERMINAL RESPONSE" in item.summary.upper())
    
    def _extract_command_info(self, item: TraceItem) -> Tuple[Optional[int], Optional[str]]:
        """Extrait le numéro de commande et le type depuis le summary."""
        import re
        
        # Chercher pattern "Number: X, Type: Y"
        number_match = re.search(r'Number:\s*(\d+)', item.summary)
        type_match = re.search(r'Type:\s*([^,\(]+)', item.summary)
        
        command_number = int(number_match.group(1)) if number_match else None
        command_type = type_match.group(1).strip() if type_match else None
        
        return command_number, command_type
    
    def _extract_response_result(self, item: TraceItem) -> Optional[str]:
        """Extrait le résultat depuis une réponse TERMINAL RESPONSE."""
        import re
        
        # Chercher pattern de résultat (ex: "Result: 9000", "SW: 9100")
        result_patterns = [
            r'Result:\s*([0-9A-Fa-f]{4})',
            r'SW:\s*([0-9A-Fa-f]{4})',
            r'Status:\s*([0-9A-Fa-f]{4})',
            r'([0-9A-Fa-f]{4})'  # Fallback pour tout code hexa 4 digits
        ]
        
        for pattern in result_patterns:
            match = re.search(pattern, item.summary)
            if match:
                return match.group(1).upper()
        
        return None
    
    def _process_fetch_command(self, item: TraceItem):
        """Traite une commande FETCH."""
        command_number, command_type = self._extract_command_info(item)
        
        if command_number is not None:
            pair = CommandResponsePair(
                fetch_item=item,
                command_number=command_number,
                command_type=command_type
            )
            
            self.pairs.append(pair)
            self.pending_fetches[command_number] = pair
    
    def _process_terminal_response(self, item: TraceItem):
        """Traite une réponse TERMINAL RESPONSE."""
        command_number, _ = self._extract_command_info(item)
        response_result = self._extract_response_result(item)
        
        if command_number is not None and command_number in self.pending_fetches:
            pair = self.pending_fetches[command_number]
            pair.response_item = item
            pair.response_result = response_result
            pair.is_complete = True
            
            # Retirer de la liste des pending
            del self.pending_fetches[command_number]
    
    def _calculate_durations(self):
        """Calcule les durées pour les paires complètes."""
        for pair in self.pairs:
            if pair.is_complete and pair.response_item:
                try:
                    fetch_time = self._parse_timestamp(pair.fetch_item.timestamp)
                    response_time = self._parse_timestamp(pair.response_item.timestamp)
                    
                    if fetch_time is not None and response_time is not None:
                        duration_seconds = response_time - fetch_time
                        pair.duration_ms = duration_seconds * 1000
                except:
                    pair.duration_ms = None
    
    def _parse_timestamp(self, timestamp_str: str) -> Optional[float]:
        """Parse timestamp string vers float (secondes depuis epoch)."""
        if not timestamp_str:
            return None
        
        try:
            import datetime
            import re
            
            # Pattern pour "10/23/2025 16:16:21:272.000000"
            match = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{2}):(\d{2}):(\d{2}):(\d{3})\.(\d+)', timestamp_str)
            if match:
                month, day, year, hour, minute, second, millisecond, microsecond = match.groups()
                
                dt = datetime.datetime(
                    int(year), int(month), int(day),
                    int(hour), int(minute), int(second),
                    int(millisecond) * 1000 + int(microsecond[:3])
                )
                
                return dt.timestamp()
                
        except Exception:
            pass
        
        return None
    
    def get_pair_for_item(self, item: TraceItem) -> Optional[CommandResponsePair]:
        """Retourne la paire contenant cet item."""
        for pair in self.pairs:
            if pair.fetch_item == item or pair.response_item == item:
                return pair
        return None
    
    def get_paired_item(self, item: TraceItem) -> Optional[TraceItem]:
        """Retourne l'item pairé (fetch pour response, response pour fetch)."""
        pair = self.get_pair_for_item(item)
        if not pair:
            return None
        
        if pair.fetch_item == item:
            return pair.response_item
        else:
            return pair.fetch_item


class TraceTreeItem:
    """Tree item for the main interpretation tree."""
    
    def __init__(self, trace_item: Optional[TraceItem] = None, content: str = "", parent=None):
        self.trace_item = trace_item
        self.content = content
        self.parent_item = parent
        self.child_items: List['TraceTreeItem'] = []
        self.is_highlighted = False
        # For combined entries (FETCH-TERMINAL RESPONSE pairs)
        self.response_item: Optional[TraceItem] = None
    
    def add_child(self, child: 'TraceTreeItem'):
        """Add a child item."""
        child.parent_item = self
        self.child_items.append(child)
    
    def child(self, row: int) -> Optional['TraceTreeItem']:
        """Get child at row."""
        if 0 <= row < len(self.child_items):
            return self.child_items[row]
        return None
    
    def child_count(self) -> int:
        """Get number of children."""
        return len(self.child_items)
    
    def row(self) -> int:
        """Get row index in parent."""
        if self.parent_item:
            return self.parent_item.child_items.index(self)
        return 0
    
    def get_display_text(self, column: int) -> str:
        """Get display text for column."""
        if column == 0:  # Summary/Content
            # Use the Universal Tracer formatted content for display
            # Fall back to trace_item.summary if content is empty
            if self.content:
                return self.content
            elif self.trace_item:
                return self.trace_item.summary
            return ""
        elif column == 1:  # Protocol
            return self.trace_item.protocol if self.trace_item else ""
        elif column == 2:  # Type
            return self.trace_item.type if self.trace_item else ""
        elif column == 3:  # Timestamp (time only)
            if self.trace_item and self.trace_item.timestamp:
                # Extract just the time part from timestamp like "10/23/2025 16:16:21:272.000000"
                import re
                time_match = re.search(r'(\d{2}:\d{2}:\d{2}:\d{3})', self.trace_item.timestamp)
                if time_match:
                    return time_match.group(1)
                return self.trace_item.timestamp
            return ""
        return ""


class TimelineItem:
        """Item for Flow Timeline with optional children (milestones)."""
        def __init__(self, data: dict, parent: Optional['TimelineItem'] = None):
            self.data = data  # contains keys for columns
            self.parent = parent
            self.children: List['TimelineItem'] = []

        def add_child(self, child: 'TimelineItem'):
            child.parent = self
            self.children.append(child)

        def child(self, row: int) -> Optional['TimelineItem']:
            if 0 <= row < len(self.children):
                return self.children[row]
            return None

        def child_count(self) -> int:
            return len(self.children)

        def row(self) -> int:
            if self.parent:
                return self.parent.children.index(self)
            return 0


class FlowTimelineModel(QAbstractItemModel):
    """Hierarchical model for Flow Overview timeline supporting sessions and events."""
    HEADERS = [
        "Type",
        "Label",
        "Time",
        "Port",
        "Protocol",
        "Targeted Server",
        "IP",
        "Opened",
        "Closed",
        "Duration",
    ]

    def __init__(self, items: Optional[List[dict]] = None, parent=None):
        super().__init__(parent)
        self.root = TimelineItem({})
        self._all_items: List[TimelineItem] = []
        self._filter_kind: Optional[str] = None  # None for both, or "Session"/"Event"
        if items:
            self.set_items(items)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def rowCount(self, parent=QModelIndex()):
        node = self._node_from_index(parent)
        return node.child_count()

    def index(self, row, column, parent=QModelIndex()):
        parent_node = self._node_from_index(parent)
        child = parent_node.child(row)
        if child:
            return self.createIndex(row, column, child)
        return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        node: TimelineItem = index.internalPointer()
        if node and node.parent and node.parent != self.root:
            return self.createIndex(node.parent.row(), 0, node.parent)
        return QModelIndex()

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        node: TimelineItem = index.internalPointer()
        if role == Qt.DisplayRole:
            col = index.column()
            key = [
                "kind","label","time","port","protocol",
                "server","ips","opened","closed","duration"
            ][col]
            if key == "ips":
                ips = node.data.get("ips", [])
                return ", ".join(ips) if ips else ""
            return node.data.get(key, "")
        elif role == Qt.BackgroundRole:
            # Hardcode a light gray background for Event rows
            try:
                if node.data.get("kind") == "Event":
                    from PySide6.QtGui import QColor, QBrush
                    return QBrush(QColor(235, 235, 235))
            except Exception:
                pass
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.HEADERS[section]
        return None

    def set_items(self, items: List[dict]):
        self.beginResetModel()
        self.root = TimelineItem({})
        self._all_items = []
        # Build nodes and attach milestones as children for sessions
        for it in items:
            node = TimelineItem(it, self.root)
            self.root.add_child(node)
            self._all_items.append(node)
            if it.get("kind") == "Session":
                for m in it.get("milestones", []):
                    child = TimelineItem(m, node)
                    node.add_child(child)
        self.endResetModel()

    def set_kind_filter(self, kind: Optional[str]):
        self._filter_kind = kind
        # Rebuild children under root according to filter
        self.beginResetModel()
        self.root.children.clear()
        for node in self._all_items:
            if not self._filter_kind or node.data.get("kind") == self._filter_kind:
                self.root.add_child(node)
        self.endResetModel()

    def _node_from_index(self, index: QModelIndex) -> TimelineItem:
        if index.isValid():
            return index.internalPointer()
        return self.root


class InterpretationTreeModel(QAbstractItemModel):
    """Tree model for the main interpretation list to match Universal Tracer interface."""
    
    # Signal emitted when selection changes
    selectionChanged = Signal(TraceItem)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.root_item = TraceTreeItem()
        self.trace_items: List[TraceItem] = []
        self.highlighted_summaries: Set[str] = set()
        self.highlight_color = QColor(255, 255, 0, 100)  # Light yellow
        
        # Pairing manager for FETCH ↔ TERMINAL RESPONSE
        self.pairing_manager = CommandResponsePairingManager()
        self.command_pairs: List[CommandResponsePair] = []
        
        # Session navigator for quick navigation
        self.session_navigator = SessionNavigator()
        
        self.pair_colors = {
            "fetch": QColor(173, 216, 230, 80),      # Light blue for FETCH
            "response": QColor(144, 238, 144, 80),   # Light green for RESPONSE  
            "pending": QColor(255, 218, 185, 80),    # Peach for pending
            "error": QColor(255, 182, 193, 80)       # Light pink for errors
        }
    
    def load_trace_items(self, trace_items: List[TraceItem]):
        """Load trace items into the tree model with Universal Tracer format."""
        self.beginResetModel()
        
        # Clear existing data and store items
        self.root_item = TraceTreeItem()
        self.trace_items = trace_items
        
        # Ensure items are sorted chronologically before loading
        sorted_items = sorted(trace_items, key=lambda item: item.timestamp_sort_key)

        # Initialize managers and analyze trace items
        self.pairing_manager = CommandResponsePairingManager()
        self.command_pairs = self.pairing_manager.analyze_trace_items(sorted_items)
        
        self.session_navigator = SessionNavigator()
        self.session_navigator.analyze_sessions(sorted_items)
        
        # Create combined entries like Universal Tracer instead of individual items
        self._create_combined_entries(sorted_items)

        self.endResetModel()
    
    def get_pair_info_for_item(self, item: TraceItem) -> Optional[CommandResponsePair]:
        """Retourne les infos de pairing pour un item."""
        return self.pairing_manager.get_pair_for_item(item)
    
    def get_paired_item(self, item: TraceItem) -> Optional[TraceItem]:
        """Retourne l'item pairé."""
        return self.pairing_manager.get_paired_item(item)
    
    def get_next_in_same_session(self, current_item: TraceItem) -> Optional[TraceItem]:
        """Navigue vers le prochain item dans la même session."""
        return self.session_navigator.get_next_in_same_session(current_item)
    
    def get_previous_in_same_session(self, current_item: TraceItem) -> Optional[TraceItem]:
        """Navigue vers l'item précédent dans la même session."""
        return self.session_navigator.get_previous_in_same_session(current_item)
    
    def _create_combined_entries(self, trace_items: List[TraceItem]):
        """Create combined entries following Universal Tracer format."""
        sorted_items = sorted(trace_items, key=lambda x: x.timestamp_sort_key)
        processed_indices = set()
        
        for i, current in enumerate(sorted_items):
            if i in processed_indices:
                continue
                
            # Look for FETCH command - check if it has a paired TERMINAL RESPONSE
            if self._is_fetch_command(current):
                # Look for the immediate FETCH response (apduresponse) that contains the detailed interpretation
                fetch_response = None
                terminal_response = None
                command_type = ""
                
                # First, find the immediate FETCH response with detailed interpretation
                if (i + 1 < len(sorted_items) and 
                    sorted_items[i + 1].type == "apduresponse"):
                    fetch_response = sorted_items[i + 1]
                    # Extract command type from the FETCH response interpretation
                    if fetch_response.summary.startswith("FETCH - "):
                        command_type = fetch_response.summary.replace("FETCH - ", "")
                        # Mark the fetch response as processed so it doesn't appear separately
                        processed_indices.add(i + 1)
                
                # Also look for the paired TERMINAL RESPONSE for fallback
                if not command_type:
                    for j in range(i + 1, len(sorted_items)):
                        if self._is_terminal_response_command(sorted_items[j]):
                            terminal_response = sorted_items[j]
                            terminal_summary = sorted_items[j].summary
                            command_type = terminal_summary.replace("TERMINAL RESPONSE - ", "").replace("TERMINAL RESPONSE", "").strip()
                            if command_type.startswith("- "):
                                command_type = command_type[2:]
                            break
                
                combined_summary = f"FETCH - FETCH - {command_type}" if command_type else "FETCH - FETCH"
                
                # Create combined tree item with both fetch and response
                tree_item = TraceTreeItem(trace_item=current, content=combined_summary)
                # Store the FETCH response (which has the detailed interpretation) for inspector use
                tree_item.response_item = fetch_response if fetch_response else terminal_response
                self.root_item.add_child(tree_item)
                processed_indices.add(i)
                continue
            
            # Look for TERMINAL RESPONSE pattern: TERMINAL RESPONSE (apducommand) -> SW response (apduresponse)  
            elif self._is_terminal_response_command(current):
                # Check if this TERMINAL RESPONSE is already processed as part of a FETCH pair
                is_paired_with_fetch = False
                if hasattr(self, 'pairing_manager'):
                    pair = self.pairing_manager.get_pair_for_item(current)
                    if pair and pair.fetch_item and self._is_fetch_command(pair.fetch_item):
                        is_paired_with_fetch = True
                
                # Only show TERMINAL RESPONSE if it's not already shown as part of FETCH
                if not is_paired_with_fetch:
                    # Extract command type from summary
                    command_type = current.summary.replace("TERMINAL RESPONSE - ", "").replace("TERMINAL RESPONSE", "").strip()
                    if command_type.startswith("- "):
                        command_type = command_type[2:]
                    
                    combined_summary = f"TERMINAL RESPONSE - {command_type}" if command_type else "TERMINAL RESPONSE"
                    
                    # Look for SW response
                    if (i + 1 < len(sorted_items) and
                        self._is_apdu_response(sorted_items[i + 1])):
                        sw_response = sorted_items[i + 1]
                        if "SW:" in sw_response.summary.upper():
                            combined_summary += f" - {sw_response.summary}"
                            processed_indices.add(i + 1)
                    
                    tree_item = TraceTreeItem(trace_item=current, content=combined_summary)
                    self.root_item.add_child(tree_item)
                
                processed_indices.add(i)
                continue
            
            # Check for ENVELOPE command + response pattern
            elif self._is_envelope_command(current):
                combined_summary = current.summary
                
                # Look for response
                if (i + 1 < len(sorted_items) and
                    self._is_apdu_response(sorted_items[i + 1])):
                    response = sorted_items[i + 1]
                    if "SW:" in response.summary.upper():
                        combined_summary += f" - {response.summary}"
                        processed_indices.add(i + 1)
                
                tree_item = TraceTreeItem(trace_item=current, content=combined_summary)
                self.root_item.add_child(tree_item)
                processed_indices.add(i)
                continue
            
            # Regular APDU command + response pattern
            elif self._is_apdu_command(current):
                combined_summary = current.summary
                
                # Look for response
                if (i + 1 < len(sorted_items) and
                    self._is_apdu_response(sorted_items[i + 1])):
                    response = sorted_items[i + 1]
                    # Combine with response, preferring SW info if available
                    if "SW:" in response.summary.upper():
                        combined_summary += f" - {response.summary}"
                    elif response.summary.strip() and response.summary.strip().upper() != "APDU RESPONSE":
                        # Use specific response text if available
                        combined_summary += f" - {response.summary}"
                    else:
                        # Generic response - just add "APDU Response" 
                        combined_summary += " - APDU Response"
                    processed_indices.add(i + 1)
                
                tree_item = TraceTreeItem(trace_item=current, content=combined_summary)
                self.root_item.add_child(tree_item)
                processed_indices.add(i)
                continue
            
            # Other items - add as-is
            else:
                tree_item = TraceTreeItem(trace_item=current)
                self.root_item.add_child(tree_item)
                processed_indices.add(i)

    def _create_fetch_summary(self, item: TraceItem) -> str:
        """Create FETCH summary like Universal Tracer: 'FETCH - FETCH - TYPE'."""
        summary = item.summary
        
        # Extract the command type from FETCH
        import re
        
        # Look for patterns like "FETCH – OPEN CHANNEL", "FETCH - SEND DATA", etc.
        type_patterns = [
            r'FETCH\s*[-–]\s*(.+)',
            r'FETCH\s*(.+)',
        ]
        
        for pattern in type_patterns:
            match = re.search(pattern, summary, re.IGNORECASE)
            if match:
                command_type = match.group(1).strip()
                # Clean up the command type
                command_type = command_type.replace("FETCH", "").strip()
                if command_type:
                    return f"FETCH - FETCH - {command_type.upper()}"
        
        return "FETCH - FETCH - UNKNOWN"
    
    def _create_terminal_response_summary(self, pair: CommandResponsePair) -> str:
        """Create TERMINAL RESPONSE summary like Universal Tracer."""
        if not pair.response_item:
            return "TERMINAL RESPONSE - UNKNOWN"
            
        response_summary = pair.response_item.summary
        
        # Extract command type from the FETCH item
        command_type = "UNKNOWN"
        if pair.fetch_item:
            fetch_summary = pair.fetch_item.summary
            import re
            type_patterns = [
                r'FETCH\s*[-–]\s*(.+)',
                r'FETCH\s*(.+)',
            ]
            
            for pattern in type_patterns:
                match = re.search(pattern, fetch_summary, re.IGNORECASE)
                if match:
                    command_type = match.group(1).strip()
                    command_type = command_type.replace("FETCH", "").strip().upper()
                    break
        
        # Extract SW code and description from response
        import re
        sw_match = re.search(r'SW:\s*([0-9A-Fa-f]{4})', response_summary)
        if sw_match:
            sw_code = sw_match.group(1).upper()
            sw_desc = self._get_status_description(sw_code)
            return f"TERMINAL RESPONSE - {command_type} - SW: {sw_code} - {sw_desc}"
        else:
            # Look for other status patterns in response
            return f"TERMINAL RESPONSE - {command_type} - {response_summary}"
    
    def _is_envelope_command(self, item: TraceItem) -> bool:
        """Check if item is an ENVELOPE command."""
        return (item.type and item.type.upper() == "APDUCOMMAND" and 
                "ENVELOPE" in item.summary.upper())
    
    def _create_envelope_summary(self, command: TraceItem, response: TraceItem) -> str:
        """Create ENVELOPE summary like Universal Tracer."""
        cmd_summary = command.summary
        resp_summary = response.summary if response else ""
        
        # Extract SW code from response
        import re
        sw_match = re.search(r'SW:\s*([0-9A-Fa-f]{4})', resp_summary)
        if sw_match:
            sw_code = sw_match.group(1).upper()
            sw_desc = self._get_status_description(sw_code)
            return f"{cmd_summary} - SW: {sw_code} - {sw_desc}"
        else:
            return f"{cmd_summary} - {resp_summary}"
    
    def _is_fetch_command(self, item: TraceItem) -> bool:
        """Check if item is a FETCH command (initial command)."""
        return (item.type and item.type.upper() == "APDUCOMMAND" and 
                item.summary.strip().upper() == "FETCH")
    
    def _is_fetch_response(self, item: TraceItem) -> bool:
        """Check if item is a FETCH response (with command details)."""
        return (item.type and item.type.upper() == "APDURESPONSE" and 
                "FETCH" in item.summary.upper() and 
                " - " in item.summary)
    
    def _is_terminal_response_command(self, item: TraceItem) -> bool:
        """Check if item is a TERMINAL RESPONSE command."""
        return (item.type and item.type.upper() == "APDUCOMMAND" and
                "TERMINAL RESPONSE" in item.summary.upper())
    
    def _is_terminal_response(self, item: TraceItem) -> bool:
        """Check if item is a TERMINAL RESPONSE command."""
        return self._is_terminal_response_command(item)
    
    def _is_apdu_command(self, item: TraceItem) -> bool:
        """Check if item is a regular APDU command."""
        return (item.type and item.type.upper() == "APDUCOMMAND" and 
                item.summary.strip().upper() != "FETCH" and
                "TERMINAL RESPONSE" not in item.summary.upper() and
                "ENVELOPE" not in item.summary.upper())
    
    def _is_apdu_response(self, item: TraceItem) -> bool:
        """Check if item is an APDU response."""
        return (item.type and item.type.upper() == "APDURESPONSE")
    
    def _find_next_apdu_response(self, command_item: TraceItem, trace_items: List[TraceItem]) -> Optional[TraceItem]:
        """Find the APDU response immediately following a command."""
        try:
            command_index = trace_items.index(command_item)
            if command_index + 1 < len(trace_items):
                next_item = trace_items[command_index + 1]
                if (next_item.type and next_item.type.upper() == "APDURESPONSE"):
                    return next_item
        except (ValueError, IndexError):
            pass
        return None
    
    def _create_apdu_combined_summary(self, command: TraceItem, response: TraceItem) -> str:
        """Create combined summary for APDU command/response pair."""
        cmd_summary = command.summary
        resp_summary = response.summary if response else ""
        
        # Extract SW code from response
        import re
        sw_match = re.search(r'SW:\s*([0-9A-Fa-f]{4})', resp_summary)
        if sw_match:
            sw_code = sw_match.group(1).upper()
            sw_desc = self._get_status_description(sw_code)
            return f"{cmd_summary} - SW: {sw_code} - {sw_desc}"
        else:
            return f"{cmd_summary} - {resp_summary}"
    
    def _get_status_description(self, status_code: str) -> str:
        """Get description for status code."""
        status_descriptions = {
            "9000": "Normal processing. Command correctly executed, and no response data",
            "6132": "File structure error",
            "6145": "File not found", 
            "6125": "Security condition not satisfied",
            "611F": "File not found",
            "63C3": "Number of retries left = 3",
            "63CA": "Number of retries left = 10",
            "910B": "Command correctly executed, and 11 byte(s) Proactive Command is available",
            "910D": "Command correctly executed, and 13 byte(s) Proactive Command is available", 
            "910F": "Command correctly executed, and 15 byte(s) Proactive Command is available",
            "9110": "Command correctly executed, and 16 byte(s) Proactive Command is available",
            "9120": "Command correctly executed, and 32 byte(s) Proactive Command is available",
            "912C": "Command correctly executed, and 44 byte(s) Proactive Command is available",
            "912E": "Command correctly executed, and 46 byte(s) Proactive Command is available",
            "9131": "Command correctly executed, and 49 byte(s) Proactive Command is available",
            "9143": "Command correctly executed, and 67 byte(s) Proactive Command is available",
            "9160": "Command correctly executed, and 96 byte(s) Proactive Command is available",
            "917E": "Command correctly executed, and 126 byte(s) Proactive Command is available",
            "9188": "Command correctly executed, and 136 byte(s) Proactive Command is available",
            "918E": "Command correctly executed, and 142 byte(s) Proactive Command is available",
            "9191": "Command correctly executed, and 145 byte(s) Proactive Command is available",
            "91CF": "Command correctly executed, and 207 byte(s) Proactive Command is available",
            "91F6": "Command correctly executed, and 246 byte(s) Proactive Command is available",
            "6C45": "Wrong length; correct length is 45",
        }
        
        return status_descriptions.get(status_code.upper(), f"Status {status_code}")
    
    def get_display_text_for_item(self, tree_item: TraceTreeItem, column: int) -> str:
        """Get display text for tree item at column (for combined entries)."""
        if not tree_item.trace_item and tree_item.content:
            # This is a combined entry
            if column == 0:
                return tree_item.content
            elif column == 1:  # Protocol
                return tree_item.trace_item.protocol if tree_item.trace_item else ""
            elif column == 2:  # Type
                return "Combined" 
            elif column == 3:  # Time
                if tree_item.trace_item and tree_item.trace_item.timestamp:
                    import re
                    time_match = re.search(r'(\d{2}:\d{2}:\d{2}:\d{3})', tree_item.trace_item.timestamp)
                    if time_match:
                        return time_match.group(1)
                return ""
        else:
            # Regular single item
            return tree_item.get_display_text(column)
    
    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        """Create an index for the given row and column."""
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        
        if not parent.isValid():
            # Top-level item
            child_item = self.root_item.child(row)
        else:
            parent_item = parent.internalPointer()
            child_item = parent_item.child(row)
        
        if child_item:
            return self.createIndex(row, column, child_item)
        return QModelIndex()
    
    def parent(self, index: QModelIndex) -> QModelIndex:
        """Get the parent of the given index."""
        if not index.isValid():
            return QModelIndex()
        
        child_item = index.internalPointer()
        parent_item = child_item.parent_item
        
        if parent_item is None or parent_item == self.root_item:
            return QModelIndex()
        
        return self.createIndex(parent_item.row(), 0, parent_item)
    
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Get the number of rows under the given parent."""
        if not parent.isValid():
            # Root level
            return self.root_item.child_count()
        
        parent_item = parent.internalPointer()
        return parent_item.child_count()
    
    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Get the number of columns."""
        return 4  # Summary, Protocol, Type, Time
    
    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """Get data for the given index and role."""
        if not index.isValid():
            return None
        
        item = index.internalPointer()
        
        if role == Qt.DisplayRole:
            display_text = item.get_display_text(index.column())
            
            # Ajouter les infos de pairing dans la colonne Summary (0)
            if index.column() == 0 and item.trace_item:
                pair = self.get_pair_info_for_item(item.trace_item)
                if pair:
                    status = pair.get_status()
                    duration = pair.get_duration_display()
                    
                    if pair.fetch_item == item.trace_item:
                        # C'est la commande FETCH
                        if pair.is_complete:
                            pairing_info = f" → {status} ({duration})"
                        else:
                            pairing_info = " → ⏳ Waiting for response"
                        display_text += pairing_info
                    elif pair.response_item == item.trace_item:
                        # C'est la réponse TERMINAL RESPONSE
                        # Afficher la ligne FETCH associée au-dessus
                        fetch_summary = pair.fetch_item.summary.replace("FETCH – ", "")
                        if len(fetch_summary) > 50:
                            fetch_summary = fetch_summary[:47] + "..."
                        
                        correlation_info = f"\n  ↳ Response to: {fetch_summary}"
                        pairing_info = f" ← Cmd#{pair.command_number} ({duration})"
                        display_text = display_text + pairing_info + correlation_info
            
            return display_text
            
        elif role == Qt.UserRole:
            return item.trace_item
            
        elif role == Qt.UserRole + 1:
            # Custom role to return the TreeModelItem itself
            return item
            
        elif role == Qt.BackgroundRole:
            # Couleurs pour les événements Location Status dans les enveloppes (priorité haute)
            if item.trace_item and item.trace_item.type == "apducommand":
                # Chercher "Location Status" dans le summary et dans l'arbre d'interprétation
                has_location_status = False
                if item.trace_item.summary and "Location Status" in item.trace_item.summary:
                    has_location_status = True
                elif item.trace_item.details_tree:
                    # Chercher récursivement dans l'arbre
                    def search_tree_for_location_status(node):
                        if "Location Status" in node.content:
                            return True
                        return any(search_tree_for_location_status(child) for child in node.children)
                    has_location_status = search_tree_for_location_status(item.trace_item.details_tree)
                
                if has_location_status:
                    # Chercher les patterns hex de service status
                    hex_data = item.trace_item.rawhex or ""
                    if "1B0102" in hex_data:
                        # No service - rouge BRIGHT pour test
                        return QBrush(QColor(255, 0, 0))  # Rouge vif
                    elif "1B0101" in hex_data:
                        # Limited service - orange BRIGHT pour test  
                        return QBrush(QColor(255, 165, 0))  # Orange vif
            
            # Couleurs de highlighting existantes
            if item.is_highlighted:
                return QBrush(self.highlight_color)
            
            # Couleurs de pairing
            if item.trace_item:
                pair = self.get_pair_info_for_item(item.trace_item)
                if pair:
                    if pair.fetch_item == item.trace_item:
                        # Commande FETCH
                        if pair.is_complete:
                            if "Error" in pair.get_status():
                                return QBrush(self.pair_colors["error"])
                            else:
                                return QBrush(self.pair_colors["fetch"])
                        else:
                            return QBrush(self.pair_colors["pending"])
                    elif pair.response_item == item.trace_item:
                        # Réponse TERMINAL RESPONSE
                        if "Error" in pair.get_status():
                            return QBrush(self.pair_colors["error"])
                        else:
                            return QBrush(self.pair_colors["response"])
                            
        elif role == Qt.ToolTipRole and index.column() == 0:
            tooltip = item.get_display_text(0)
            
            # Ajouter les détails de pairing au tooltip
            if item.trace_item:
                pair = self.get_pair_info_for_item(item.trace_item)
                if pair:
                    tooltip += f"\n\n📋 Command/Response Pairing:"
                    tooltip += f"\n• Command: #{pair.command_number} - {pair.command_type}"
                    tooltip += f"\n• Status: {pair.get_status()}"
                    if pair.duration_ms is not None:
                        tooltip += f"\n• Duration: {pair.get_duration_display()}"
                    
                    if pair.is_complete:
                        tooltip += f"\n• Result: {pair.response_result}"
                        
                        # Ajouter info complète de corrélation
                        if pair.fetch_item == item.trace_item:
                            tooltip += f"\n\n🔗 Paired Response:"
                            tooltip += f"\n• {pair.response_item.summary}"
                        else:
                            tooltip += f"\n\n🔗 Paired Command:"
                            tooltip += f"\n• {pair.fetch_item.summary}"
                    else:
                        tooltip += "\n• ⏳ Waiting for response..."
                        
            return tooltip
        
        return None
    
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        """Get header data."""
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            headers = ["Interpretation", "Protocol", "Type", "Time"]
            if 0 <= section < len(headers):
                return headers[section]
        return None
    
    def get_trace_item(self, index: QModelIndex) -> Optional[TraceItem]:
        """Get the TraceItem associated with the given index."""
        if not index.isValid():
            return None
        
        item = index.internalPointer()
        return item.trace_item
    
    def get_tree_item(self, index: QModelIndex) -> Optional['TraceTreeItem']:
        """Get the TraceTreeItem associated with the given index."""
        if not index.isValid():
            return None
        
        return index.internalPointer()
    
    def highlight_command_family(self, summary: str):
        """Highlight all items with the same summary text."""
        # Clear previous highlights
        self.clear_highlights()
        
        # Find all matching summaries
        matching_summaries = set()
        for trace_item in self.trace_items:
            if trace_item.summary == summary:
                matching_summaries.add(summary)
        
        self.highlighted_summaries = matching_summaries
        
        # Update the display
        self.refresh_highlighting()
    
    def clear_highlights(self):
        """Clear all highlighting."""
        self.highlighted_summaries.clear()
        self.refresh_highlighting()
    
    def refresh_highlighting(self):
        """Refresh the highlighting display for all items."""
        # Update highlighting for all tree items
        self._update_item_highlighting(self.root_item)
        
        # Emit data changed to refresh display
        self.dataChanged.emit(self.index(0, 0), 
                            self.index(self.rowCount() - 1, self.columnCount() - 1))
    
    def _update_item_highlighting(self, parent_item: TraceTreeItem):
        """Recursively update highlighting for tree items."""
        for child in parent_item.child_items:
            if child.trace_item:
                child.is_highlighted = child.trace_item.summary in self.highlighted_summaries
            self._update_item_highlighting(child)


class TraceItemFilterModel(QSortFilterProxyModel):
    """Proxy model for filtering trace items by search text and command family."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_text = ""
        self.command_family_filter = ""
        self.session_filter_indexes = []  # List of trace item indexes to show
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        # Disable dynamic sorting to preserve chronological order
        self.setDynamicSortFilter(False)
        
        # Session tracking for server filtering
        self.active_sessions = {}  # Maps session_id to server_name
        self.session_items = {}    # Maps session_id to list of item indices
        self.sessions_analyzed = False
    
    def set_search_text(self, text: str):
        """Set the search text for filtering."""
        self.search_text = text.lower()
        self.invalidateFilter()
    
    def set_command_family_filter(self, summary: str):
        """Filter to show only items with matching summary."""
        self.command_family_filter = summary
        self.invalidateFilter()
    
    def clear_command_family_filter(self):
        """Clear the command family filter."""
        self.command_family_filter = ""
        self.invalidateFilter()
    
    def set_session_filter(self, indexes: List[int]):
        """Filter to show only items from specific sessions by trace item indexes."""
        self.session_filter_indexes = indexes
        # Clear other filters when session filtering is active
        self.command_family_filter = ""
        self.search_text = ""
        self.invalidateFilter()
    
    def clear_session_filter(self):
        """Clear the session filter."""
        self.session_filter_indexes = []
        self.invalidateFilter()
    
    def clear_all_filters(self):
        """Clear all filters and reset to show all items."""
        self.session_filter_indexes = []
        self.command_family_filter = ""
        self.search_text = ""
        # None means "filter disabled (show all)"; empty list means "user selected none (show none)"
        self.command_type_filter = None
        self.server_filter = ""
        self.time_range_start = None
        self.time_range_end = None
        self.sessions_analyzed = False
        self.active_sessions = {}
        self.session_items = {}
        self.invalidateFilter()
        # Force a complete refresh
        self.setSourceModel(self.sourceModel())
    
    def set_command_type_filter(self, command_types: List[str]):
        """Filter by command types (OPEN, SEND, RECEIVE, etc.)."""
        # Accept None to disable filtering entirely (all types shown)
        # Accept [] (empty list) to indicate user explicitly selected none (show nothing)
        self.command_type_filter = command_types
        self.invalidateFilter()
    
    def set_server_filter(self, server_name: str):
        """Filter by server name (DP+, TAC, etc.)."""
        self.server_filter = server_name
        self.sessions_analyzed = False  # Force re-analysis when server filter changes
        self.invalidateFilter()
    
    def analyze_channel_sessions(self):
        """Analyze channel sessions to track which items belong to which servers using parser's channel sessions"""
        if self.sessions_analyzed:
            return
            
        source_model = self.sourceModel()
        if not source_model or not hasattr(source_model, 'trace_items'):
            return
            
        self.active_sessions.clear()
        self.session_items.clear()
        
        # Get the parser instance to access its channel sessions
        # The parser should be available through the main window
        from .xti_parser import tag_server_from_ips
        
        # Try to get parser from source model or global state
        parser = getattr(source_model, 'parser', None)
        if not parser:
            # Fallback: analyze sessions ourselves
            self._analyze_sessions_fallback()
            return
        
        # Use the parser's already-analyzed channel sessions
        for session_idx, session in enumerate(parser.channel_sessions):
            session_id = f"session_{session_idx}"
            
            # Determine server label from IPs
            server_label = tag_server_from_ips(session.ips)
            
            # Store session info
            self.active_sessions[session_id] = server_label
            self.session_items[session_id] = session.traceitem_indexes
        
        self.sessions_analyzed = True
    
    def _analyze_sessions_fallback(self):
        """Fallback session analysis when parser is not available"""
        source_model = self.sourceModel()
        current_sessions = {}
        session_counter = 0
        
        # Import protocol analyzer for role detection
        try:
            from .protocol_analyzer import ProtocolAnalyzer, ChannelRoleDetector
        except ImportError:
            ProtocolAnalyzer = None
            ChannelRoleDetector = None
        
        trace_items = source_model.trace_items
        
        for trace_item_index, trace_item in enumerate(trace_items):
            summary_lower = trace_item.summary.lower()
            
            # Check for channel operations
            if "open channel" in summary_lower:
                # Extract server info from IP addresses
                from .xti_parser import extract_ips_from_interpretation_tree, tag_server_from_ips, extract_channel_id_from_interpretation
                ips = extract_ips_from_interpretation_tree(trace_item.details_tree)
                server_label = tag_server_from_ips(ips)
                
                # Try to extract channel ID (from TERMINAL RESPONSE - OPEN CHANNEL)
                channel_id = None
                if "terminal response" in summary_lower:
                    channel_id = extract_channel_id_from_interpretation(trace_item.details_tree)
                
                if server_label and server_label != "Unknown":
                    session_counter += 1
                    session_id = f"session_{session_counter}"
                    
                    # Start tracking this session
                    current_sessions[session_id] = {
                        'server': server_label,
                        'start_trace_idx': trace_item_index,
                        'items': [trace_item_index],
                        'role': None,  # Will be detected from SNI
                        'ips': ips,
                        'protocol': None,
                        'port': None,
                        'channel_id': channel_id  # Track channel ID for proper item matching
                    }
                    
                    self.active_sessions[session_id] = server_label
                    
            elif "close channel" in summary_lower:
                # Extract channel ID to match the correct session
                from .xti_parser import extract_channel_id_from_interpretation
                close_channel_id = extract_channel_id_from_interpretation(trace_item.details_tree)
                
                # Find the session with matching channel ID, or fall back to most recent
                matched_session_id = None
                if close_channel_id:
                    for session_id, session_info in current_sessions.items():
                        if session_info.get('channel_id') == close_channel_id:
                            matched_session_id = session_id
                            break
                
                # If no channel ID match, close the most recent session
                if not matched_session_id and current_sessions:
                    matched_session_id = list(current_sessions.keys())[-1]
                
                if matched_session_id:
                    session_info = current_sessions[matched_session_id]
                    session_info['items'].append(trace_item_index)
                    
                    # Store the complete session
                    self.session_items[matched_session_id] = session_info['items']
                    
                    # Remove from active sessions
                    del current_sessions[matched_session_id]
                    
            else:
                # Match items to sessions by channel ID (if available)
                from .xti_parser import extract_channel_id_from_interpretation
                item_channel_id = extract_channel_id_from_interpretation(trace_item.details_tree)
                
                matched = False
                if item_channel_id:
                    # Try to match by channel ID
                    for session_id, session_info in current_sessions.items():
                        if session_info.get('channel_id') == item_channel_id:
                            session_info['items'].append(trace_item_index)
                            matched = True
                            break
                
                # If no channel ID or no match, add to most recent session (fallback)
                if not matched and current_sessions:
                    # Add to most recently opened session
                    most_recent_session_id = list(current_sessions.keys())[-1]
                    current_sessions[most_recent_session_id]['items'].append(trace_item_index)
                    session_info = current_sessions[most_recent_session_id]
                    
                    # Analyze SEND/RECEIVE DATA for role detection if not already detected
                    if (not session_info['role'] and ProtocolAnalyzer and
                        ("send data" in summary_lower or "receive data" in summary_lower)):
                        
                        try:
                            # Try to extract and analyze payload
                            if trace_item.rawhex:
                                from .apdu_parser_construct import parse_apdu
                                parsed = parse_apdu(trace_item.rawhex)
                                payload = self._extract_payload_for_role_detection(parsed)
                                
                                if payload:
                                    analysis = ProtocolAnalyzer.analyze_payload(payload)
                                    if analysis.tls_info and analysis.tls_info.sni_hostname:
                                        detected_role = ChannelRoleDetector.detect_role_from_sni(
                                            analysis.tls_info.sni_hostname
                                        )
                                        if detected_role:
                                            session_info['role'] = detected_role
                                            # Update the server label if role provides better info
                                            if detected_role in ['SM-DP+', 'DP+', 'eIM']:
                                                session_info['server'] = f"{session_info['server']} ({detected_role})"
                        except:
                            pass  # Continue without role detection if analysis fails
        
        # Handle sessions that never closed
        for session_id, session_info in current_sessions.items():
            self.session_items[session_id] = session_info['items']
        
        self.sessions_analyzed = True
    
    def _extract_payload_for_role_detection(self, parsed_apdu) -> bytes:
        """Extract payload for role detection from parsed APDU"""
        try:
            # Look for data TLVs that contain the actual payload
            for tlv in parsed_apdu.tlvs:
                if hasattr(tlv, 'raw_value') and len(tlv.raw_value) > 20:  # Minimum size for TLS handshake
                    return tlv.raw_value
                elif hasattr(tlv, 'children'):
                    for child in tlv.children:
                        if hasattr(child, 'raw_value') and len(child.raw_value) > 20:
                            return child.raw_value
        except:
            pass
        return None
    
    def set_time_range_filter(self, start_time=None, end_time=None):
        """Filter by time range using QTime objects."""
        self.time_range_start = start_time
        self.time_range_end = end_time
        self.invalidateFilter()
    
    def is_command_family_filtered(self) -> bool:
        """Check if command family filter is active."""
        return bool(self.command_family_filter)
    
    def is_session_filtered(self) -> bool:
        """Check if session filter is active."""
        return bool(self.session_filter_indexes)
    
    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """Filter rows based on all active filters."""
        try:
        # Safety checks for missing attributes (in case of incomplete initialization)
            if not hasattr(self, 'time_range_start'):
                self.time_range_start = None
            if not hasattr(self, 'time_range_end'):
                self.time_range_end = None
            if not hasattr(self, 'command_type_filter'):
                # Default to no filtering (equivalent to "All selected")
                self.command_type_filter = None
            if not hasattr(self, 'server_filter'):
                self.server_filter = ""

            # Always get source model early; needed for session filtering
            source_model = self.sourceModel()
            if not source_model:
                return True  # If no source model, accept all
                
            # Apply session filter first (most restrictive)
            if self.session_filter_indexes:
                # Determine if any trace item associated with this combined row belongs to the selected session indexes
                item_in_session = False
                if hasattr(source_model, 'trace_items'):
                    model_index = source_model.index(source_row, 0)
                    tree_model_item = source_model.data(model_index, Qt.UserRole + 1) or model_index.internalPointer()
                    if tree_model_item:
                        trace_items_in_row = []
                        if getattr(tree_model_item, 'trace_item', None):
                            trace_items_in_row.append(tree_model_item.trace_item)
                        if getattr(tree_model_item, 'response_item', None):
                            trace_items_in_row.append(tree_model_item.response_item)
                        if getattr(tree_model_item, 'terminal_item', None):
                            trace_items_in_row.append(tree_model_item.terminal_item)
                        # Map each TraceItem to its index in the source trace list and check membership
                        for ti in trace_items_in_row:
                            try:
                                ti_idx = source_model.trace_items.index(ti)
                                if ti_idx in self.session_filter_indexes:
                                    item_in_session = True
                                    break
                            except ValueError:
                                continue
                if not item_in_session:
                    return False
                # In session-filter mode, ignore other filters to keep behavior predictable
                return True
            
            # Get the summary text from the first column
            index = source_model.index(source_row, 0, source_parent)
            summary = source_model.data(index, Qt.DisplayRole)
            
            if not summary:
                return False
            
            # Apply time range filter based on actual timestamps
            if hasattr(self, 'time_range_start') and hasattr(self, 'time_range_end') and self.time_range_start and self.time_range_end:
                # Get the actual trace item to check its timestamp
                if hasattr(source_model, 'trace_items') and source_row < len(source_model.trace_items):
                    # Get the TreeModelItem from the source model to find the actual trace item
                    model_index = source_model.index(source_row, 0)
                    tree_model_item = model_index.internalPointer()
                    
                    if tree_model_item and tree_model_item.trace_item:
                        trace_item = tree_model_item.trace_item
                        
                        # Parse timestamp from trace item
                        if trace_item.timestamp:
                            try:
                                import re
                                from PySide6.QtCore import QTime
                                time_match = re.search(r'(\d{2}:\d{2}:\d{2})', trace_item.timestamp)
                                if time_match:
                                    time_str = time_match.group(1)
                                    item_time = QTime.fromString(time_str, "hh:mm:ss")
                                    
                                    if item_time.isValid():
                                        # Check if item time is within the selected range
                                        if self.time_range_start <= self.time_range_end:
                                            # Normal range (same day)
                                            if not (self.time_range_start <= item_time <= self.time_range_end):
                                                return False
                                        else:
                                            # Range crosses midnight
                                            if not (item_time >= self.time_range_start or item_time <= self.time_range_end):
                                                return False
                            except Exception:
                                # If timestamp parsing fails, don't filter out the item
                                pass
            
            # Apply command type filter semantics:
            # None  => no filtering
            # []    => user selected none, reject all rows
            # list  => filter to matching command types
            if hasattr(self, 'command_type_filter'):
                if self.command_type_filter is None:
                    pass  # Disabled
                elif isinstance(self.command_type_filter, list) and len(self.command_type_filter) == 0:
                    return False  # Explicit none selected
                elif self.command_type_filter:
                    summary_lower = summary.lower()
                    command_match = False
                    for cmd_type in self.command_type_filter:
                        if cmd_type == "OPEN":
                            # Match FETCH commands that open channels, not terminal responses
                            if "fetch" in summary_lower and "open channel" in summary_lower:
                                command_match = True
                                break
                        elif cmd_type == "SEND":
                            # Match only FETCH SEND DATA commands (not terminal responses)
                            if "fetch" in summary_lower and "send data" in summary_lower:
                                command_match = True
                                break
                        elif cmd_type == "RECEIVE":
                            # Match only FETCH RECEIVE DATA commands (not terminal responses)
                            if "fetch" in summary_lower and "receive data" in summary_lower:
                                command_match = True
                                break
                        elif cmd_type == "CLOSE":
                            # Match FETCH commands that close channels, not terminal responses
                            if "fetch" in summary_lower and "close channel" in summary_lower:
                                command_match = True
                                break
                        elif cmd_type == "ENVELOPE":
                            # Match envelope packets
                            if "envelope" in summary_lower:
                                command_match = True
                                break
                        elif cmd_type == "TERMINAL":
                            # Match only terminal response items
                            if "terminal response" in summary_lower:
                                command_match = True
                                break
                        elif cmd_type == "TIMER":
                            # Timer Management (e.g., Set Timer)
                            if "fetch" in summary_lower and (
                                "timer management" in summary_lower or "set timer" in summary_lower
                            ):
                                command_match = True
                                break
                        elif cmd_type == "TIMER_EXP":
                            # Timer Expiration events
                            if "fetch" in summary_lower and (
                                "timer expiration" in summary_lower or "timer expired" in summary_lower
                            ):
                                command_match = True
                                break
                        elif cmd_type == "COLD_RESET":
                            # Cold Reset events
                            if "fetch" in summary_lower and "cold reset" in summary_lower:
                                command_match = True
                                break
                        elif cmd_type == "PLI":
                            # Provide Local Info (PLI)
                            if "fetch" in summary_lower and "provide local info" in summary_lower:
                                command_match = True
                                break
                
                    if not command_match:
                        return False
            
            # Apply server filter with session awareness
            if hasattr(self, 'server_filter') and self.server_filter and self.server_filter != "All Servers":
                # Analyze sessions if not done yet
                self.analyze_channel_sessions()
                
                # Check if this item belongs to a session with the target server
                item_in_target_server_session = False
                
                # Map filter names to expected server labels
                target_server = None
                target_servers = []
                dns_filter = False
                def _is_dns_label(label: object) -> bool:
                    try:
                        return isinstance(label, str) and ("dns" in label.lower())
                    except Exception:
                        return False
                
                if self.server_filter == "DP+":
                    target_server = "DP+"
                elif self.server_filter == "TAC":
                    target_server = "TAC"
                elif self.server_filter == "DNS by ME" or self.server_filter == "ME":
                    target_server = "ME"
                elif self.server_filter == "DNS":
                    # Some traces label DNS sessions as a specific resolver (Google DNS, ...),
                    # some as a generic "DNS", and some use operator-specific labels (e.g. "SIMIN DNS Serveur").
                    # Treat any label containing "DNS" as DNS traffic.
                    dns_filter = True
                    target_servers = ["Google DNS", "Cloudflare DNS", "Quad9 DNS", "OpenDNS", "DNS", "SIMIN DNS Serveur"]
                elif self.server_filter in ["Google DNS", "Cloudflare DNS", "Quad9 DNS", "OpenDNS"]:
                    # Direct DNS server names from channel groups
                    target_server = self.server_filter
                else:
                    # Unknown server - try exact match
                    target_server = self.server_filter
                
                # Check if this row belongs to any session with the target server
                for session_id, server_label in self.active_sessions.items():
                    session_item_indices = self.session_items.get(session_id, [])
                    
                    # Get ALL trace items from this model row (could be combined FETCH+RESPONSE)
                    if hasattr(source_model, 'trace_items'):
                        model_index = source_model.index(source_row, 0)
                        tree_model_item = model_index.internalPointer()
                        
                        if tree_model_item:
                            # Get all trace items in this row (could be FETCH command, response, terminal response)
                            trace_items_in_row = []
                            if tree_model_item.trace_item:
                                trace_items_in_row.append(tree_model_item.trace_item)
                            if hasattr(tree_model_item, 'response_item') and tree_model_item.response_item:
                                trace_items_in_row.append(tree_model_item.response_item)
                            if hasattr(tree_model_item, 'terminal_item') and tree_model_item.terminal_item:
                                trace_items_in_row.append(tree_model_item.terminal_item)
                            
                            # Check if ANY of these trace items are in the session
                            for trace_item in trace_items_in_row:
                                try:
                                    trace_item_index = source_model.trace_items.index(trace_item)
                                    
                                    if trace_item_index in session_item_indices:
                                        if target_server and server_label == target_server:
                                            item_in_target_server_session = True
                                            break
                                        elif dns_filter and (_is_dns_label(server_label) or server_label in target_servers):
                                            item_in_target_server_session = True
                                            break
                                        elif target_servers and server_label in target_servers:
                                            item_in_target_server_session = True
                                            break
                                except ValueError:
                                    # TraceItem not found in list, continue
                                    continue
                            
                            if item_in_target_server_session:
                                break
                
                # If no session match found, fall back to direct IP checking for individual items
                # Special-case fallback for ME: allow TERMINAL RESPONSE - OPEN CHANNEL with Device Identities ME→SIM
                if not item_in_target_server_session and target_server == "ME":
                    if hasattr(source_model, 'trace_items') and source_row < len(source_model.trace_items):
                        model_index = source_model.index(source_row, 0)
                        tree_model_item = source_model.data(model_index, Qt.UserRole + 1) or model_index.internalPointer()
                        trace_item_to_check = None
                        if tree_model_item:
                            trace_item_to_check = tree_model_item.trace_item or tree_model_item.response_item
                        if trace_item_to_check:
                            summary_lower = trace_item_to_check.summary.lower() if trace_item_to_check.summary else ""
                            if "terminal response - open channel" in summary_lower:
                                from .xti_parser import TreeNode
                                def has_me_sim_device_identities(node: TreeNode) -> bool:
                                    if not node or not getattr(node, 'content', None):
                                        return False
                                    c = node.content.lower()
                                    if "device identity" in c or "device identities" in c:
                                        # Look for lines indicating Source: ME and Destination: SIM
                                        # We will scan subtree text for both tokens
                                        def subtree_text(n: TreeNode) -> str:
                                            t = n.content.lower()
                                            for ch in getattr(n, 'children', []):
                                                t += "\n" + subtree_text(ch)
                                            return t
                                        text = subtree_text(node)
                                        return ("source: me" in text and "destination: sim" in text)
                                    for ch in getattr(node, 'children', []):
                                        if has_me_sim_device_identities(ch):
                                            return True
                                    return False
                                if has_me_sim_device_identities(trace_item_to_check.details_tree):
                                    item_in_target_server_session = True
                # If no session match found, fall back to direct IP checking for individual items (non-ME)
                if not item_in_target_server_session and target_server != "ME":
                    # Get the actual TraceItem object to check for server information
                    if hasattr(source_model, 'trace_items') and source_row < len(source_model.trace_items):
                        # Get the TreeModelItem from the source model
                        model_index = source_model.index(source_row, 0)
                        tree_model_item = source_model.data(model_index, Qt.UserRole + 1)  # Custom role for TreeModelItem
                        
                        if not tree_model_item:
                            # Fallback: get via internalPointer
                            tree_model_item = model_index.internalPointer()
                        
                        trace_item_to_check = None
                        
                        if tree_model_item:
                            # For combined FETCH entries, check the response_item which has the IP info
                            if (hasattr(tree_model_item, 'response_item') and 
                                tree_model_item.response_item and
                                tree_model_item.trace_item and
                                "fetch" in tree_model_item.trace_item.summary.lower()):
                                trace_item_to_check = tree_model_item.response_item
                            else:
                                trace_item_to_check = tree_model_item.trace_item
                        
                        if trace_item_to_check:
                            # Extract IPs from the trace item's details tree
                            from .xti_parser import extract_ips_from_interpretation_tree, tag_server_from_ips
                            ips = extract_ips_from_interpretation_tree(trace_item_to_check.details_tree)
                            server_label = tag_server_from_ips(ips)
                            
                            # Check direct IP match
                            if target_server and server_label == target_server:
                                item_in_target_server_session = True
                            elif dns_filter and (_is_dns_label(server_label) or server_label in target_servers):
                                item_in_target_server_session = True
                            elif target_servers and server_label in target_servers:
                                item_in_target_server_session = True
                            elif self.server_filter == "Other":
                                # Exclude all known/suspected DNS labels too
                                item_in_target_server_session = (
                                    server_label not in ["DP+", "TAC", "ME", "Google DNS", "Cloudflare DNS", "Quad9 DNS", "OpenDNS", "DNS", "SIMIN DNS Serveur"]
                                    and not _is_dns_label(server_label)
                                )
                
                if not item_in_target_server_session:
                    return False
            
            # Apply command family filter
            if self.command_family_filter:
                if summary != self.command_family_filter:
                    return False
            
            # Apply search text filter
            if self.search_text:
                if self.search_text not in summary.lower():
                    return False
            
            return True
            
        except Exception as e:
            # Log error and return True to avoid blocking UI
            print(f"Filter error: {e}")
            return True


class InspectorTreeNode:
    """Node for the inspector tree model."""
    
    def __init__(self, tree_node: TreeNode, parent=None):
        self.tree_node = tree_node
        self.parent_item = parent
        self.child_items: List['InspectorTreeNode'] = []
        
        # Create child nodes
        for child_tree_node in tree_node.children:
            child_item = InspectorTreeNode(child_tree_node, self)
            self.child_items.append(child_item)
    
    def child(self, row: int) -> Optional['InspectorTreeNode']:
        """Get child at the specified row."""
        if 0 <= row < len(self.child_items):
            return self.child_items[row]
        return None
    
    def child_count(self) -> int:
        """Get the number of children."""
        return len(self.child_items)
    
    def row(self) -> int:
        """Get the row index of this item in its parent."""
        if self.parent_item:
            return self.parent_item.child_items.index(self)
        return 0
    
    def data(self, column: int) -> str:
        """Get data for the specified column."""
        if column == 0:
            return self.tree_node.content
        return ""


class InspectorTreeModel(QAbstractItemModel):
    """Model for the inspector tree view."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.root_item: Optional[InspectorTreeNode] = None
    
    def load_tree(self, tree_node: Optional[TreeNode]):
        """Load a tree structure into the model."""
        self.beginResetModel()
        
        if tree_node:
            self.root_item = InspectorTreeNode(tree_node)
        else:
            self.root_item = None
        
        self.endResetModel()
    
    def clear_tree(self):
        """Clear the tree."""
        self.load_tree(None)
    
    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        """Create an index for the given row and column."""
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        
        if not parent.isValid():
            # Top-level item
            if self.root_item:
                return self.createIndex(row, column, self.root_item)
            return QModelIndex()
        
        parent_item = parent.internalPointer()
        child_item = parent_item.child(row)
        if child_item:
            return self.createIndex(row, column, child_item)
        
        return QModelIndex()
    
    def parent(self, index: QModelIndex) -> QModelIndex:
        """Get the parent of the given index."""
        if not index.isValid():
            return QModelIndex()
        
        child_item = index.internalPointer()
        parent_item = child_item.parent_item
        
        if parent_item is None or parent_item == self.root_item:
            return QModelIndex()
        
        return self.createIndex(parent_item.row(), 0, parent_item)
    
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Get the number of rows under the given parent."""
        if not self.root_item:
            return 0
        
        if not parent.isValid():
            # Root level - return 1 if we have a root item
            return 1 if self.root_item else 0
        
        parent_item = parent.internalPointer()
        return parent_item.child_count()
    
    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Get the number of columns."""
        return 1  # Only content column
    
    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """Get data for the given index and role."""
        if not index.isValid():
            return None
        
        item = index.internalPointer()
        
        if role == Qt.DisplayRole:
            return item.data(index.column())
        elif role == Qt.ToolTipRole:
            # Show full content as tooltip for long text
            content = item.data(index.column())
            if len(content) > 50:
                return content
        
        return None
    
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        """Get header data."""
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if section == 0:
                return "Interpretation Details"
        return None


class HexViewModel:
    """Helper class for formatting hex data display."""
    
    @staticmethod
    def format_hex_data(rawhex: Optional[str], bytes_per_line: int = 16) -> str:
        """
        Format raw hex data with offsets and grouping.
        
        Args:
            rawhex: Raw hex string (may contain spaces or be continuous)
            bytes_per_line: Number of bytes to display per line
            
        Returns:
            Formatted hex string with offsets
        """
        if not rawhex:
            return "No hex data available"
        
        # Clean the hex string (remove spaces and non-hex characters)
        clean_hex = ''.join(c for c in rawhex if c.isalnum())
        
        if len(clean_hex) % 2 != 0:
            return "Invalid hex data (odd length)"
        
        # Convert to bytes
        try:
            byte_data = bytes.fromhex(clean_hex)
        except ValueError:
            return "Invalid hex data format"
        
        lines = []
        for i in range(0, len(byte_data), bytes_per_line):
            chunk = byte_data[i:i + bytes_per_line]
            
            # Offset
            offset = f"{i:08X}"
            
            # Hex bytes (grouped by 2)
            hex_part = " ".join(f"{b:02X}" for b in chunk)
            hex_part = hex_part.ljust(bytes_per_line * 3 - 1)  # Pad for alignment
            
            # ASCII representation
            ascii_part = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
            
            lines.append(f"{offset}  {hex_part}  |{ascii_part}|")
        
        return "\n".join(lines)
    
    @staticmethod
    def get_copy_text(rawhex: Optional[str]) -> str:
        """Get clean hex text for copying to clipboard."""
        if not rawhex:
            return ""
        
        # Return clean hex (uppercase, no spaces)
        clean_hex = ''.join(c for c in rawhex.upper() if c.isalnum())
        return clean_hex


class ChannelGroupsModel(QAbstractItemModel):
    """Model for displaying channel sessions in chronological order."""
    
    # Signal emitted when a group is selected for filtering
    groupSelected = Signal(list)  # List of session indexes for filtering
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._groups = []
        self._headers = ["#", "Channel Type", "Port", "Protocol", "Role", "Server", "IP", "Opened", "Closed", "Duration"]
    
    def set_groups(self, groups: List[dict]):
        """Set the channel groups data."""
        self.beginResetModel()
        self._groups = groups
        self.endResetModel()
    
    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        """Create a model index."""
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        
        if not parent.isValid():
            # Top-level items (groups)
            if 0 <= row < len(self._groups):
                return self.createIndex(row, column, None)
        
        return QModelIndex()
    
    def parent(self, index: QModelIndex) -> QModelIndex:
        """Get parent index."""
        return QModelIndex()  # Flat model, no hierarchy
    
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Get number of rows."""
        if not parent.isValid():
            return len(self._groups)
        return 0
    
    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Get number of columns."""
        return len(self._headers)
    
    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """Get data for a model index."""
        if not index.isValid() or index.row() >= len(self._groups):
            return None
        
        group = self._groups[index.row()]
        
        if role == Qt.DisplayRole:
            column = index.column()
            if column == 0:  # Session Number
                return str(group.get("session_number", index.row() + 1))
            elif column == 1:  # Channel Type
                t = group.get("type", "")
                # Normalize naming: 'open channel' -> 'BIP Session'
                if t.strip().lower() == "open channel":
                    return "BIP Session"
                return t
            elif column == 2:  # Port
                return str(group.get("port", "")) if group.get("port") else ""
            elif column == 3:  # Protocol
                return group.get("protocol", "")
            elif column == 4:  # Role
                return group.get("role", "Unknown")
            elif column == 5:  # Serveur utilisé
                return group.get("server", "")
            elif column == 6:  # IP
                # For display, join IPs with comma instead of <br>
                ips = group.get("ips", [])
                return ", ".join(ips) if ips else ""
            elif column == 7:  # Opened
                return group.get("opened_at", "Unknown")
            elif column == 8:  # Closed
                return group.get("closed_at", "Not closed")
            elif column == 9:  # Duration
                return group.get("duration", "Unknown")
        
        elif role == Qt.UserRole:
            # Return the group data for filtering
            return group
        
        return None
    
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        """Get header data."""
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if 0 <= section < len(self._headers):
                return self._headers[section]
        return None
    
    def get_group_session_indexes(self, group_index: int) -> List[int]:
        """Get all trace item indexes for sessions in a group, including OPEN/CLOSE commands."""
        if 0 <= group_index < len(self._groups):
            group = self._groups[group_index]
            sessions = group.get("sessions", [])
            
            # Collect all trace item indexes from all sessions in the group
            indexes = []
            for session in sessions:
                # Include all session-related indexes (includes OPEN, data transfers, and CLOSE)
                indexes.extend(session.traceitem_indexes)
                
                # Also find and include the OPEN CHANNEL and CLOSE CHANNEL commands
                # by searching for commands that mention this session's channel ID
                if hasattr(session, 'channel_id') and session.channel_id:
                    # This will be handled by the enhanced traceitem_indexes in the session
                    # The XTI parser should already include OPEN/CLOSE in traceitem_indexes
                    pass
            
            return sorted(set(indexes))  # Remove duplicates and sort
        return []


class KeyEventsModel(QAbstractItemModel):
    """Model to display key events (Refresh, Cold Reset, ICCID, etc.) for quick navigation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._events = []  # List of dicts: {type, summary, time, index}
        self._headers = ["Type", "Summary", "Time", "Index"]

    def set_events(self, events: List[dict]):
        self.beginResetModel()
        self._events = events
        self.endResetModel()

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        if not parent.isValid():
            if 0 <= row < len(self._events):
                return self.createIndex(row, column, None)
        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        return QModelIndex()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if not parent.isValid():
            return len(self._events)
        return 0

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._headers)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._events):
            return None
        ev = self._events[index.row()]
        if role == Qt.DisplayRole:
            if index.column() == 0:
                return ev.get("type", "")
            elif index.column() == 1:
                return ev.get("summary", "")
            elif index.column() == 2:
                return ev.get("time", "")
            elif index.column() == 3:
                return ev.get("index", "")
        elif role == Qt.UserRole:
            return ev
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if 0 <= section < len(self._headers):
                return self._headers[section]
        return None


class FlowTimelineModel(QAbstractItemModel):
    """Unified timeline mixing channel groups (sessions) and key events in chronological order."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []  # Each item: {kind: 'session'|'event', label, time, session_indexes|index}
        # Unified columns. For Session rows, fill rich details; for Event rows, leave unused columns blank.
        self._headers = [
            "Kind", "Label", "Time",
            "Port", "Protocol", "Role", "Targeted Server", "IP",
            "Opened", "Closed", "Duration"
        ]

    def set_timeline(self, items: List[dict]):
        self.beginResetModel()
        # Sort by a sortable key: prefer explicit sort_key, else time string, else fallback
        def time_key(it):
            return it.get("sort_key") or it.get("time") or ""
        self._items = sorted(items, key=time_key)
        self.endResetModel()

    @property
    def timeline_items(self) -> List[dict]:
        """Backward-compatible accessor used by export/report code."""
        try:
            return list(self._items)
        except Exception:
            return []

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        if not parent.isValid():
            if 0 <= row < len(self._items):
                return self.createIndex(row, column, None)
        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        return QModelIndex()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if not parent.isValid():
            return len(self._items)
        return 0

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._headers)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._items):
            return None
        item = self._items[index.row()]
        if role == Qt.DisplayRole:
            col = index.column()
            if col == 0:
                return item.get("kind", "")
            elif col == 1:
                return item.get("label", "")
            elif col == 2:
                return item.get("time", "")
            elif col == 3:
                return item.get("port", "")
            elif col == 4:
                return item.get("protocol", "")
            elif col == 5:
                return item.get("role", "")
            elif col == 6:
                return item.get("server", "")
            elif col == 7:
                ips = item.get("ips", [])
                return ", ".join(ips) if isinstance(ips, list) else (ips or "")
            elif col == 8:
                return item.get("opened", "")
            elif col == 9:
                return item.get("closed", "")
            elif col == 10:
                return item.get("duration", "")
        elif role == Qt.UserRole:
            return item
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if 0 <= section < len(self._headers):
                return self._headers[section]
        return None