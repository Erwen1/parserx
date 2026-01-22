"""Test script for new validation detections."""
import sys
from xti_viewer.xti_parser import XTIParser
from xti_viewer.validation import ValidationManager, ValidationSeverity

def test_new_validations():
    """Test the new validation detections."""
    
    # Parse the XTI file
    parser = XTIParser()
    trace_items = parser.parse_file("HL7812_fallback_NOK.xti")
    
    print(f"Parsed {len(trace_items)} trace items\n")
    
    # Create validation manager and validate all items
    validator = ValidationManager()
    for i, item in enumerate(trace_items):
        validator.validate_trace_item(item, i)
    
    # Print summary by category
    print("=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print(validator.get_summary())
    print()
    
    # Group issues by category
    issues_by_category = {}
    for issue in validator.issues:
        if issue.category not in issues_by_category:
            issues_by_category[issue.category] = []
        issues_by_category[issue.category].append(issue)
    
    # Print issues by category
    for category in sorted(issues_by_category.keys()):
        issues = issues_by_category[category]
        print(f"\n{category} ({len(issues)} issues)")
        print("-" * 80)
        
        for issue in issues:
            severity_icon = "🔴" if issue.severity == ValidationSeverity.CRITICAL else "🟠" if issue.severity == ValidationSeverity.WARNING else "🔵"
            print(f"{severity_icon} [{issue.severity.value}] {issue.message}")
            print(f"   Index: {issue.trace_index}, Time: {issue.timestamp}")
            if issue.command_details:
                print(f"   Details: {issue.command_details}")
            print()

if __name__ == "__main__":
    test_new_validations()
