"""Diffs per-file coverage between baseline and updates; fails
    with error if the coverage noticeably decreases"""

import json
import sys


def get_coverage_data(file_path):
    """Load coverage data from file_path"""
    with open(file_path, encoding="utf8") as file:
        data = json.load(file)
    coverage_data = {}
    for file_name, file_report in data["files"].items():
        line_rate = (
            file_report["summary"]["percent_covered"] / 100.0
        )  # Convert to a fraction
        coverage_data[file_name] = line_rate
    return coverage_data


def check_coverage_drop(base, current, threshold=0.05):
    """Check for drops in coverage across files over a threshold"""
    result = []
    for file, base_rate in base.items():
        if file in current:
            if file.endswith("_test.py"):
                continue
            current_rate = current.get(file)
            if not current_rate:
                continue
            if base_rate - current_rate > threshold:
                result.append((file, base_rate, current_rate))
    return result


base_coverage = get_coverage_data("base_coverage.json")
current_coverage = get_coverage_data("current_coverage.json")
dropped_files = check_coverage_drop(base_coverage, current_coverage)
if dropped_files:
    print("Coverage dropped significantly in the following files:")
    for f, br, cr in dropped_files:
        print(f"{f}: {br:.2f} -> {cr:.2f}")
    sys.exit(1)

print("Coverage OK")
