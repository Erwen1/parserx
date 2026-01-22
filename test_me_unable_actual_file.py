"""Test TERMINAL RESPONSE error detection with actual XTI file."""
from xti_viewer.xti_parser import XTIParser
from xti_viewer.validation import ValidationManager, ValidationSeverity

# Load the actual XTI file
print("Loading BC660K_enable_OK.xti...")
parser = XTIParser()
parser.parse_file('BC660K_enable_OK.xti')

print(f"Total trace items: {len(parser.trace_items)}")

# Run validation
vm = ValidationManager()
for i, ti in enumerate(parser.trace_items):
    vm.validate_trace_item(ti, i)
vm.finalize_validation()

# Find all Terminal Response Error issues
terminal_response_errors = [
    issue for issue in vm.issues 
    if issue.category == "Terminal Response Error"
]

print("\n" + "=" * 80)
print("TERMINAL RESPONSE ERROR DETECTION RESULTS")
print("=" * 80)
print()

if terminal_response_errors:
    print(f"✅ Found {len(terminal_response_errors)} Terminal Response Error(s):")
    print()
    for issue in terminal_response_errors:
        severity_icon = "🔴" if issue.severity == ValidationSeverity.CRITICAL else "🟠" if issue.severity == ValidationSeverity.WARNING else "🔵"
        print(f"{severity_icon} [{issue.severity.value}] {issue.category}")
        print(f"   Message: {issue.message}")
        print(f"   Index: {issue.trace_index}")
        print(f"   Time: {issue.timestamp}")
        if issue.command_details:
            print(f"   Command: {issue.command_details}")
        print()
        
        # Show a snippet of the trace item for verification
        if issue.trace_index < len(parser.trace_items):
            ti = parser.trace_items[issue.trace_index]
            print(f"   Trace Summary: {ti.summary[:80]}")
            print()
else:
    print("❌ No Terminal Response Errors detected")

print("=" * 80)
print(f"\nTotal validation issues: {len(vm.issues)}")
print(f"  Critical: {len(vm.get_critical_issues())}")
print(f"  Warnings: {len(vm.get_warning_issues())}")
print(f"  Info: {len(vm.get_info_issues())}")
print("=" * 80)

# Specifically check for "ME unable to process command"
me_unable_errors = [
    issue for issue in terminal_response_errors
    if "ME unable to process command" in issue.message
]

print()
print("=" * 80)
print("SPECIFIC CHECK: 'ME unable to process command'")
print("=" * 80)
if me_unable_errors:
    print(f"✅ Found {len(me_unable_errors)} 'ME unable to process command' error(s)")
    for issue in me_unable_errors:
        print(f"   - {issue.message}")
else:
    print("⚠️  No 'ME unable to process command' errors found in this file")
print("=" * 80)
