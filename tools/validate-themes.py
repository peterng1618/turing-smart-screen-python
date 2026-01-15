#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
import sys
import argparse
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from tests.tools.theme_validator import ThemeValidator

def main():
    parser = argparse.ArgumentParser(description="Validate themes for turing-smart-screen-python")
    parser.add_argument("--theme", help="Validate a specific theme by name")
    parser.add_argument("--all", action="store_true", help="Validate all active themes")
    parser.add_argument("--json-output", action="store_true", help="Output results in JSON format")
    
    args = parser.parse_args()
    
    validator = ThemeValidator()
    
    if args.theme:
        results = [validator.validate_theme(args.theme)]
    elif args.all:
        if not args.json_output:
            print("Discovering and validating all themes...")
        results = validator.validate_all()
    else:
        parser.print_help()
        return

    if args.json_output:
        import json
        print(json.dumps([res.to_dict() for res in results]))
        return

    # Print summary
    failed = []
    print(f"\n{'Theme':<30} | {'Status':<10} | {'Error'}")
    print("-" * 60)
    for res in results:
        status = "PASSED" if res.success else "FAILED"
        error_msg = res.error if res.error else ""
        print(f"{res.theme_name:<30} | {status:<10} | {error_msg}")
        if not res.success:
            failed.append(res)

    print("-" * 60)
    print(f"Total: {len(results)} | Passed: {len(results) - len(failed)} | Failed: {len(failed)}")
    
    if failed:
        print("\nDetails of Failures:")
        for res in failed:
            print(f"--- {res.theme_name} ---")
            print(res.error)
            if res.traceback:
                print(res.traceback)
        sys.exit(1)

if __name__ == "__main__":
    main()
