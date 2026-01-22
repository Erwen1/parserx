"""Test TERMINAL RESPONSE error detection."""
from xti_viewer.xti_parser import XTIParser, TraceItem, TreeNode
from xti_viewer.validation import ValidationManager, ValidationSeverity

# Create a mock trace item with TERMINAL RESPONSE error
mock_item = TraceItem(
    protocol="CAT",
    type="TERMINAL RESPONSE",
    summary="TERMINAL RESPONSE - SEND DATA",
    rawhex="801400000C810301430182028281830136",
    timestamp="12:56:50.286",
    details_tree=TreeNode("TERMINAL RESPONSE - SEND DATA"),
    timestamp_sort_key="12:56:50.286000000"
)

# Build the tree structure
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

# Test the validation
vm = ValidationManager()
vm.validate_trace_item(mock_item, 0)

print("=" * 80)
print("TERMINAL RESPONSE ERROR DETECTION TEST")
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
else:
    print("❌ No issues detected - test FAILED")

print("=" * 80)
print(f"Expected: 1 WARNING issue for 'Terminal Response Error'")
print(f"Actual: {len(vm.issues)} issues")
print("=" * 80)
