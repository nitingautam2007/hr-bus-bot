import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.queries import find_departures_by_names

tests = [
    ("Chandigarh", "Delhi (ISBT)"),
    ("Delhi (ISBT)", "Chandigarh"),
    ("Gurugram", "Chandigarh"),
    ("Hisar", "Delhi (ISBT)"),
    ("Rohtak", "Delhi (ISBT)"),
    ("Bhiwani", "Delhi (ISBT)"),
    ("Sirsa", "Hisar"),
    ("Faridabad", "Delhi (ISBT)"),
    ("Panipat", "Chandigarh"),
    ("Rewari", "Delhi (ISBT)"),
    ("Sonipat", "Delhi (ISBT)"),
    ("Yamunanagar", "Chandigarh"),
    ("Ambala Cantt", "Delhi (ISBT)"),
    ("Karnal", "Delhi (ISBT)")
]

print("Verifying comprehensive route queries:")
for f, t in tests:
    deps = find_departures_by_names(f, t)
    status = f"[OK] {len(deps)} departures" if len(deps) > 0 else "[FAIL] 0 departures"
    print(f"{f:15} -> {t:15} : {status}")

