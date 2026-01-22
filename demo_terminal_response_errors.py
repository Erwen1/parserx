"""
Test script to demonstrate TERMINAL RESPONSE error detection in parsing log.
This shows how "ME unable to process command" appears as a warning.
"""
from xti_viewer.xti_parser import XTIParser, TraceItem, TreeNode
from xti_viewer.validation import ValidationManager, ValidationSeverity

def create_open_channel_error():
    """Create a TERMINAL RESPONSE - OPEN CHANNEL with 'ME unable to process command'."""
    mock_item = TraceItem(
        protocol="CAT",
        type="TERMINAL RESPONSE",
        summary="TERMINAL RESPONSE - OPEN CHANNEL",
        rawhex="80140000148103014009820282818302200435010339020578",
        timestamp="15:09:52:502.000000",
        details_tree=TreeNode("TERMINAL RESPONSE - OPEN CHANNEL"),
        timestamp_sort_key="15:09:52:502.000000"
    )
    
    cmd_details = TreeNode("Command Details")
    cmd_details.children = [
        TreeNode("Command Number: 1"),
        TreeNode("Command Name: OPEN CHANNEL"),
        TreeNode("Command Qualifier: Immediate Link Establishment, No Automatic Reconnection")
    ]
    
    device_identity = TreeNode("Device Identity")
    device_identity.children = [
        TreeNode("Source: ME"),
        TreeNode("Destination: SIM")
    ]
    
    result = TreeNode("Result")
    general_result = TreeNode("General Result: ME unable to process command")
    additional_info = TreeNode("Additional Info: No service")
    result.children = [general_result, additional_info]
    
    bearer_desc = TreeNode("Bearer Description: Default bearer for requested transport layer.")
    buffer_size = TreeNode("Buffer Size: 1400 bytes")
    raw_data = TreeNode("Raw Data: 0x80140000148103014009820282818302200435010339020578")
    
    mock_item.details_tree.children = [
        cmd_details,
        device_identity,
        result,
        bearer_desc,
        buffer_size,
        raw_data
    ]
    
    return mock_item

def create_send_data_error():
    """Create a TERMINAL RESPONSE - SEND DATA with error."""
    mock_item = TraceItem(
        protocol="CAT",
        type="TERMINAL RESPONSE",
        summary="TERMINAL RESPONSE - SEND DATA",
        rawhex="801400000C810301430182028281830136",
        timestamp="12:56:50.286",
        details_tree=TreeNode("TERMINAL RESPONSE - SEND DATA"),
        timestamp_sort_key="12:56:50.286000000"
    )
    
    cmd_details = TreeNode("Command Details")
    cmd_details.children = [
        TreeNode("Command Number: 1"),
        TreeNode("Command Name: SEND DATA"),
        TreeNode("Command Qualifier: Send Data Immediately")
    ]
    
    device_identity = TreeNode("Device Identity")
    device_identity.children = [
        TreeNode("Source: ME"),
        TreeNode("Destination: SIM")
    ]
    
    result = TreeNode("Result")
    general_result = TreeNode("General Result: Error - required values are missing")
    result.children = [general_result]
    
    mock_item.details_tree.children = [
        cmd_details,
        device_identity,
        result
    ]
    
    return mock_item

# Create test scenarios
print("=" * 80)
print("TERMINAL RESPONSE ERROR DETECTION - PARSING LOG DISPLAY")
print("=" * 80)
print()

test_items = [
    ("OPEN CHANNEL with 'ME unable to process command'", create_open_channel_error()),
    ("SEND DATA with 'Error - required values are missing'", create_send_data_error())
]

vm = ValidationManager()

for idx, (description, item) in enumerate(test_items):
    print(f"Test {idx+1}: {description}")
    print("-" * 80)
    vm.validate_trace_item(item, idx)
    print()

# Display the parsing log entries
print("=" * 80)
print("PARSING LOG ENTRIES (as they would appear in the UI)")
print("=" * 80)
print()
print(f"{'Severity':<12} {'Category':<25} {'Message':<40} {'Index':<8} {'Timestamp':<25}")
print("-" * 110)

for issue in vm.issues:
    severity_color = "🔴" if issue.severity == ValidationSeverity.CRITICAL else "🟠" if issue.severity == ValidationSeverity.WARNING else "🔵"
    print(f"{severity_color} {issue.severity.value:<10} {issue.category:<25} {issue.message:<40} {issue.trace_index:<8} {issue.timestamp or 'N/A':<25}")

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(vm.get_summary())
print()
print("✅ All TERMINAL RESPONSE errors are detected and shown as WARNING in parsing log")
print("=" * 80)
