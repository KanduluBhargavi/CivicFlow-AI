from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "frontend" / "data" / "state_district_wise.json"
EXPECTED_COUNTS = {'Andaman and Nicobar Islands': 3, 'Andhra Pradesh': 28, 'Arunachal Pradesh': 27, 'Assam': 35, 'Bihar': 38, 'Chandigarh': 1, 'Chhattisgarh': 33, 'Dadra and Nagar Haveli and Daman and Diu': 3, 'Delhi': 11, 'Goa': 3, 'Gujarat': 34, 'Haryana': 23, 'Himachal Pradesh': 12, 'Jammu and Kashmir': 20, 'Jharkhand': 24, 'Karnataka': 31, 'Kerala': 14, 'Ladakh': 2, 'Lakshadweep': 1, 'Madhya Pradesh': 55, 'Maharashtra': 36, 'Manipur': 16, 'Meghalaya': 12, 'Mizoram': 11, 'Nagaland': 17, 'Odisha': 30, 'Puducherry': 2, 'Punjab': 23, 'Rajasthan': 41, 'Sikkim': 6, 'Tamil Nadu': 38, 'Telangana': 33, 'Tripura': 8, 'Uttar Pradesh': 75, 'Uttarakhand': 13, 'West Bengal': 23}

data = json.loads(DATA.read_text(encoding="utf-8"))
by_state = {row["state"]: row["districts"] for row in data}
problems = []

if len(by_state) != 36:
    problems.append(f"Expected 36 states/UTs, found {len(by_state)}")

for state, expected in EXPECTED_COUNTS.items():
    values = by_state.get(state)
    if values is None:
        problems.append(f"Missing state/UT: {state}")
        continue
    if len(values) != expected:
        problems.append(f"{state}: expected {expected}, found {len(values)}")
    if len(values) != len({v.casefold() for v in values}):
        problems.append(f"{state}: duplicate district name")
    if any(not v.strip() for v in values):
        problems.append(f"{state}: blank district name")

if problems:
    print("[FAIL] Administrative location data")
    for item in problems:
        print(" -", item)
    raise SystemExit(1)

print("[PASS] 36 states/UTs present")
print("[PASS] District lists match configured 2026 administrative counts")
print("[PASS] No duplicate or blank district names")
print("[PASS] Rayagada:", "Rayagada" in by_state["Odisha"])
print("Total configured district entries:", sum(len(v) for v in by_state.values()))
