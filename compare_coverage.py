import json


def get_coverage_data(file_path):
    with open(file_path) as file:
        data = json.load(file)
    coverage_data = {}
    for file_name, file_report in data["files"].items():
        line_rate = (
            file_report["summary"]["percent_covered"] / 100.0
        )  # Convert to a fraction
        coverage_data[file_name] = line_rate
    return coverage_data


def check_coverage_drop(base, current, threshold=0.05):
    dropped_files = []
    for file, base_rate in base.items():
        if file in current:
            if file.endswith("_test.py"):
                continue
            current_rate = current.get(file)
            if not current_rate:
                continue
            if base_rate - current_rate > threshold:
                dropped_files.append((file, base_rate, current_rate))
    return dropped_files


base_coverage = get_coverage_data("base_coverage.json")
current_coverage = get_coverage_data("current_coverage.json")
dropped_files = check_coverage_drop(base_coverage, current_coverage)
if dropped_files:
    print("Coverage dropped significantly in the following files:")
    for f, br, cr in dropped_files:
        print(f"{f}: {br:.2f} -> {cr:.2f}")
    exit(1)

print("Coverage OK")
