"""Quick test for calculate_waste_status business logic."""
import sys
sys.path.insert(0, ".")
from app.services.waste_logic import calculate_waste_status

tests = [
    (20, 100, "LOW"),
    (60, 100, "MEDIUM"),
    (80, 100, "HIGH"),
    (95, 100, "CRITICAL"),
    (0, 100, "LOW"),
    (50, 100, "LOW"),
    (51, 100, "MEDIUM"),
    (75, 100, "MEDIUM"),
    (76, 100, "HIGH"),
    (90, 100, "HIGH"),
    (91, 100, "CRITICAL"),
    (100, 100, "CRITICAL"),
]

passed = 0
failed = 0
for level, cap, expected in tests:
    result = calculate_waste_status(level, cap)
    status = "PASS" if result == expected else "FAIL"
    if result == expected:
        passed += 1
    else:
        failed += 1
    print(f"  level={level}, cap={cap} => {result} (expected {expected}) [{status}]")

print(f"\nResults: {passed} passed, {failed} failed out of {len(tests)}")
