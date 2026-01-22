"""
Unit tests for the XTI Parser functionality.
"""
import unittest
import tempfile
import os
from xti_viewer.xti_parser import XTIParser, TraceItem, TreeNode


class TestXTIParser(unittest.TestCase):
    """Test cases for XTI Parser."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = XTIParser()
    
    def create_test_xti_file(self, content: str) -> str:
        """Create a temporary XTI file with the given content."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xti', delete=False) as f:
            f.write(content)
            return f.name
    
    def tearDown(self):
        """Clean up after tests."""
        # Clean up any temporary files created during tests
        pass
    
    def test_parse_simple_xti_file(self):
        """Test parsing a simple XTI file with one trace item."""
        xti_content = '''<?xml version="1.0" encoding="UTF-8"?>
<tracedata>
    <traceitem protocol="ISO7816" type="apducommand">
        <data rawhex="00A4040007A0000001510000" type="apducommand" />
        <interpretation>
            <interpretedresult content="SELECT FILE Command">
                <interpretedresult content="CLA = 00 (ISO/IEC 7816)" />
                <interpretedresult content="INS = A4 (SELECT FILE)" />
                <interpretedresult content="P1 = 04" />
                <interpretedresult content="P2 = 00" />
            </interpretedresult>
        </interpretation>
    </traceitem>
</tracedata>'''
        
        file_path = self.create_test_xti_file(xti_content)
        
        try:
            trace_items = self.parser.parse_file(file_path)
            
            # Verify we got one trace item
            self.assertEqual(len(trace_items), 1)
            
            item = trace_items[0]
            
            # Test basic attributes
            self.assertEqual(item.protocol, "ISO7816")
            self.assertEqual(item.type, "apducommand")
            self.assertEqual(item.summary, "SELECT FILE Command")
            self.assertEqual(item.rawhex, "00A4040007A0000001510000")
            
            # Test interpretation tree structure
            self.assertIsInstance(item.details_tree, TreeNode)
            self.assertEqual(item.details_tree.content, "SELECT FILE Command")
            self.assertEqual(len(item.details_tree.children), 4)
            
            # Check first child
            first_child = item.details_tree.children[0]
            self.assertEqual(first_child.content, "CLA = 00 (ISO/IEC 7816)")
            self.assertEqual(len(first_child.children), 0)
            
        finally:
            os.unlink(file_path)
    
    def test_extract_first_interpreted_result(self):
        """Test that the first interpreted result is correctly extracted as summary."""
        xti_content = '''<?xml version="1.0" encoding="UTF-8"?>
<tracedata>
    <traceitem protocol="TEST">
        <interpretation>
            <interpretedresult content="First Line Summary">
                <interpretedresult content="Child line 1" />
                <interpretedresult content="Child line 2" />
            </interpretedresult>
        </interpretation>
    </traceitem>
</tracedata>'''
        
        file_path = self.create_test_xti_file(xti_content)
        
        try:
            trace_items = self.parser.parse_file(file_path)
            self.assertEqual(len(trace_items), 1)
            self.assertEqual(trace_items[0].summary, "First Line Summary")
        finally:
            os.unlink(file_path)
    
    def test_build_full_interpreted_tree(self):
        """Test that the full interpretation tree is correctly built."""
        xti_content = '''<?xml version="1.0" encoding="UTF-8"?>
<tracedata>
    <traceitem protocol="TEST">
        <interpretation>
            <interpretedresult content="Root">
                <interpretedresult content="Child 1">
                    <interpretedresult content="Grandchild 1.1" />
                    <interpretedresult content="Grandchild 1.2" />
                </interpretedresult>
                <interpretedresult content="Child 2" />
            </interpretedresult>
        </interpretation>
    </traceitem>
</tracedata>'''
        
        file_path = self.create_test_xti_file(xti_content)
        
        try:
            trace_items = self.parser.parse_file(file_path)
            item = trace_items[0]
            tree = item.details_tree
            
            # Check root
            self.assertEqual(tree.content, "Root")
            self.assertEqual(len(tree.children), 2)
            
            # Check first child
            child1 = tree.children[0]
            self.assertEqual(child1.content, "Child 1")
            self.assertEqual(len(child1.children), 2)
            
            # Check grandchildren
            self.assertEqual(child1.children[0].content, "Grandchild 1.1")
            self.assertEqual(child1.children[1].content, "Grandchild 1.2")
            
            # Check second child
            child2 = tree.children[1]
            self.assertEqual(child2.content, "Child 2")
            self.assertEqual(len(child2.children), 0)
            
        finally:
            os.unlink(file_path)
    
    def test_read_rawhex_when_present(self):
        """Test that rawhex data is correctly read when present."""
        xti_content = '''<?xml version="1.0" encoding="UTF-8"?>
<tracedata>
    <traceitem>
        <data rawhex="DEADBEEF" />
        <interpretation>
            <interpretedresult content="Test" />
        </interpretation>
    </traceitem>
</tracedata>'''
        
        file_path = self.create_test_xti_file(xti_content)
        
        try:
            trace_items = self.parser.parse_file(file_path)
            self.assertEqual(trace_items[0].rawhex, "DEADBEEF")
        finally:
            os.unlink(file_path)
    
    def test_handle_missing_rawhex(self):
        """Test that missing rawhex is handled gracefully."""
        xti_content = '''<?xml version="1.0" encoding="UTF-8"?>
<tracedata>
    <traceitem>
        <interpretation>
            <interpretedresult content="Test" />
        </interpretation>
    </traceitem>
</tracedata>'''
        
        file_path = self.create_test_xti_file(xti_content)
        
        try:
            trace_items = self.parser.parse_file(file_path)
            self.assertIsNone(trace_items[0].rawhex)
        finally:
            os.unlink(file_path)
    
    def test_multiple_trace_items(self):
        """Test parsing multiple trace items."""
        xti_content = '''<?xml version="1.0" encoding="UTF-8"?>
<tracedata>
    <traceitem protocol="ISO7816" type="command">
        <interpretation>
            <interpretedresult content="First Command" />
        </interpretation>
    </traceitem>
    <traceitem protocol="ISO7816" type="response">
        <interpretation>
            <interpretedresult content="First Response" />
        </interpretation>
    </traceitem>
    <traceitem protocol="NFC" type="data">
        <interpretation>
            <interpretedresult content="NFC Data" />
        </interpretation>
    </traceitem>
</tracedata>'''
        
        file_path = self.create_test_xti_file(xti_content)
        
        try:
            trace_items = self.parser.parse_file(file_path)
            self.assertEqual(len(trace_items), 3)
            
            self.assertEqual(trace_items[0].summary, "First Command")
            self.assertEqual(trace_items[0].protocol, "ISO7816")
            self.assertEqual(trace_items[0].type, "command")
            
            self.assertEqual(trace_items[1].summary, "First Response")
            self.assertEqual(trace_items[1].type, "response")
            
            self.assertEqual(trace_items[2].summary, "NFC Data")
            self.assertEqual(trace_items[2].protocol, "NFC")
            
        finally:
            os.unlink(file_path)
    
    def test_skip_items_without_interpretation(self):
        """Test that items without interpretation are skipped."""
        xti_content = '''<?xml version="1.0" encoding="UTF-8"?>
<tracedata>
    <traceitem protocol="TEST">
        <data rawhex="123456" />
        <!-- No interpretation element -->
    </traceitem>
    <traceitem protocol="TEST">
        <interpretation>
            <interpretedresult content="Valid Item" />
        </interpretation>
    </traceitem>
</tracedata>'''
        
        file_path = self.create_test_xti_file(xti_content)
        
        try:
            trace_items = self.parser.parse_file(file_path)
            # Should only get the second item
            self.assertEqual(len(trace_items), 1)
            self.assertEqual(trace_items[0].summary, "Valid Item")
        finally:
            os.unlink(file_path)
    
    def test_invalid_xml_file(self):
        """Test handling of invalid XML files."""
        invalid_xml = '''This is not valid XML'''
        
        file_path = self.create_test_xti_file(invalid_xml)
        
        try:
            with self.assertRaises(Exception):
                self.parser.parse_file(file_path)
        finally:
            os.unlink(file_path)
    
    def test_missing_file(self):
        """Test handling of missing files."""
        with self.assertRaises(FileNotFoundError):
            self.parser.parse_file("nonexistent_file.xti")
    
    def test_timestamp_extraction(self):
        """Test timestamp extraction from various attributes."""
        xti_content = '''<?xml version="1.0" encoding="UTF-8"?>
<tracedata>
    <traceitem timestamp="2023-11-05T14:30:00">
        <interpretation>
            <interpretedresult content="Test with timestamp" />
        </interpretation>
    </traceitem>
</tracedata>'''
        
        file_path = self.create_test_xti_file(xti_content)
        
        try:
            trace_items = self.parser.parse_file(file_path)
            self.assertEqual(trace_items[0].timestamp, "2023-11-05T14:30:00")
        finally:
            os.unlink(file_path)
    
    def test_chronological_sorting(self):
        """Test that trace items are sorted chronologically (oldest to newest)."""
        xti_content = '''<?xml version="1.0" encoding="UTF-8"?>
<tracedata>
    <traceitem timestamp="2023-11-05T14:30:02">
        <interpretation>
            <interpretedresult content="Third Command" />
        </interpretation>
    </traceitem>
    <traceitem timestamp="2023-11-05T14:30:00">
        <interpretation>
            <interpretedresult content="First Command" />
        </interpretation>
    </traceitem>
    <traceitem timestamp="2023-11-05T14:30:01">
        <interpretation>
            <interpretedresult content="Second Command" />
        </interpretation>
    </traceitem>
</tracedata>'''
        
        file_path = self.create_test_xti_file(xti_content)
        
        try:
            trace_items = self.parser.parse_file(file_path)
            
            # Should be sorted chronologically
            self.assertEqual(len(trace_items), 3)
            self.assertEqual(trace_items[0].summary, "First Command")
            self.assertEqual(trace_items[0].timestamp, "2023-11-05T14:30:00")
            
            self.assertEqual(trace_items[1].summary, "Second Command")
            self.assertEqual(trace_items[1].timestamp, "2023-11-05T14:30:01")
            
            self.assertEqual(trace_items[2].summary, "Third Command")
            self.assertEqual(trace_items[2].timestamp, "2023-11-05T14:30:02")
            
        finally:
            os.unlink(file_path)


class TestTreeNode(unittest.TestCase):
    """Test cases for TreeNode class."""
    
    def test_create_node(self):
        """Test creating a tree node."""
        node = TreeNode("Test Content")
        self.assertEqual(node.content, "Test Content")
        self.assertEqual(len(node.children), 0)
    
    def test_add_child(self):
        """Test adding children to a node."""
        parent = TreeNode("Parent")
        child1 = TreeNode("Child 1")
        child2 = TreeNode("Child 2")
        
        parent.add_child(child1)
        parent.add_child(child2)
        
        self.assertEqual(len(parent.children), 2)
        self.assertEqual(parent.children[0].content, "Child 1")
        self.assertEqual(parent.children[1].content, "Child 2")


def run_tests():
    """Run all tests."""
    unittest.main()


if __name__ == "__main__":
    run_tests()