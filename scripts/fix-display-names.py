#!/usr/bin/env python3
"""Fix display names in CSV by mapping them to usernames via identity mapping."""

import csv
import sys
from pathlib import Path

# Add parent directory to path to import CLI modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.bitbucket_identity import load_bitbucket_identity_mapping

CSV_FILE = "complexity-report.csv"


def main():
    print(f"🔧 Fixing display names in {CSV_FILE}...")
    print()

    # Load identity mapping
    mapping = load_bitbucket_identity_mapping()
    if not mapping:
        print("⚠️  No identity mapping found, nothing to fix")
        return

    print(f"📋 Loaded {len(mapping)} identity mappings:")
    for display_name, username in mapping.items():
        print(f"   '{display_name}' → '{username}'")
    print()

    # Load CSV
    csv_path = Path(CSV_FILE)
    if not csv_path.exists():
        print(f"❌ Error: {CSV_FILE} not found")
        sys.exit(1)

    rows = []
    fieldnames = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    print(f"📊 Loaded {len(rows)} rows from CSV")

    # Fix display names
    fixed_count = 0
    for row in rows:
        developer = row.get("developer", "")
        if developer in mapping:
            old_name = developer
            new_name = mapping[developer]
            row["developer"] = new_name
            fixed_count += 1
            print(f"   ✓ Fixed: '{old_name}' → '{new_name}'")

    # Write back to CSV
    if fixed_count > 0:
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print()
        print(f"✅ Fixed {fixed_count} rows in {CSV_FILE}")
    else:
        print()
        print("✓ No rows needed fixing")


if __name__ == "__main__":
    main()
