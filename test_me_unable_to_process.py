"""Test TERMINAL RESPONSE 'ME unable to process command' detection."""
from xti_viewer.xti_parser import XTIParser, TraceItem, TreeNode
from xti_viewer.validation import ValidationManager, ValidationSeverity

# Create a mock trace item with TERMINAL RESPONSE - ME unable to process command
mock_item = TraceItem(
    protocol="CAT",
    type="TERMINAL RESPONSE",
    summary="TERMINAL RESPONSE - OPEN CHANNEL",
    rawhex="80140000148103014009820282818302200435010339020578",
    timestamp="15:09:52:502.000000",
    details_tree=TreeNode("TERMINAL RESPONSE - OPEN CHANNEL"),
    timestamp_sort_key="15:09:52:502.000000"
)

# Build the tree structure matching your example
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

# Test the validation
vm = ValidationManager()
vm.validate_trace_item(mock_item, 0)

print("=" * 80)
print("TERMINAL RESPONSE 'ME unable to process command' DETECTION TEST")
print("=" * 80)
print()

# Print detected issues
if vm.issues:
    for issue in vm.issues:
        severity_icon = "🔴" if issue.severity == ValidationSeverity.CRITICAL else "🟠" if issue.severity == ValidationSeverity.WARNING else "🔵"
        print(f"{severity_icon} [{issue.severity.value}] {issue.category}: {issue.message}")
        print(f"   Index: {issue.trace_index}")
        print(f"   Time: {issue.timestamp}")
        if issue.command_details:
            print(f"   Details: {issue.command_details}")
        print()
    print("✅ TEST PASSED - 'ME unable to process command' detected successfully!")
else:
    print("❌ No issues detected - test FAILED")
    print("Expected: 1 WARNING issue for 'Terminal Response Error'")

print("=" * 80)
print(f"Expected: 1 WARNING issue for 'Terminal Response Error'")
print(f"Actual: {len(vm.issues)} issues")
print("=" * 80)
