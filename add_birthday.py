#!/usr/bin/env python3
"""
Interactive birthday manager for Boo Haus Display.

Usage:
    python add_birthday.py
    python add_birthday.py --file custom_birthdays.json
"""

import argparse
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from config import config


def default_birthday_file() -> str:
    """Return the configured birthday file path."""
    return config.runtime_path('screens.birthday.birthday_file', 'birthdays.json')


def validate_date(month, day) -> bool:
    """Validate that the month/day pair is a real calendar date."""
    try:
        datetime(2024, int(month), int(day))
        return True
    except (TypeError, ValueError):
        return False


def normalize_birthday(row) -> Optional[dict]:
    """Return a clean birthday row, or None when the row is malformed."""
    if not isinstance(row, dict):
        return None

    name = str(row.get('name', '')).strip()
    if not name:
        return None

    try:
        month = int(row.get('month'))
        day = int(row.get('day'))
    except (TypeError, ValueError):
        return None

    if not validate_date(month, day):
        return None

    return {
        'name': name,
        'month': month,
        'day': day,
        'date': f"{month:02d}-{day:02d}",
    }


def sanitize_birthdays(rows: Iterable) -> Tuple[List[dict], int]:
    """Normalize rows and return (valid_birthdays, skipped_count)."""
    birthdays = []
    skipped = 0

    for row in rows:
        birthday = normalize_birthday(row)
        if birthday is None:
            skipped += 1
            continue
        birthdays.append(birthday)

    birthdays.sort(key=lambda item: (item['month'], item['day'], item['name'].lower()))
    return birthdays, skipped


def load_birthdays(filename) -> List[dict]:
    """Load existing birthdays from JSON file."""
    path = Path(filename)
    if not path.exists():
        print(f"{path} not found. Creating new file.")
        return []

    try:
        with open(path, 'r', encoding='utf-8') as f:
            rows = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"Error reading {path}: {exc}. Starting with empty list.")
        return []
    except OSError as exc:
        print(f"Could not read {path}: {exc}. Starting with empty list.")
        return []

    if not isinstance(rows, list):
        print(f"Error reading {path}: expected a JSON list. Starting with empty list.")
        return []

    birthdays, skipped = sanitize_birthdays(rows)
    if skipped:
        print(f"Skipped {skipped} malformed birthday entr{'y' if skipped == 1 else 'ies'}.")
    return birthdays


def save_birthdays(birthdays, filename):
    """Save birthdays to JSON file, sorted by date, using an atomic replace."""
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)

    clean_birthdays, skipped = sanitize_birthdays(birthdays)
    if skipped:
        print(f"Skipped {skipped} malformed birthday entr{'y' if skipped == 1 else 'ies'} while saving.")

    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            'w',
            encoding='utf-8',
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as f:
            temp_name = f.name
            json.dump(clean_birthdays, f, indent=2, ensure_ascii=False)
            f.write("\n")

        os.replace(temp_name, path)
    except OSError as exc:
        if temp_name:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
        raise RuntimeError(f"Could not save birthdays to {path}: {exc}") from exc

    print(f"\nSaved {len(clean_birthdays)} birthday{'s' if len(clean_birthdays) != 1 else ''} to {path}")


def parse_month(month_input: str) -> Optional[int]:
    """Parse a numeric month or English month name."""
    try:
        month = int(month_input)
        if 1 <= month <= 12:
            return month
    except ValueError:
        pass

    for date_format in ('%B', '%b'):
        try:
            return datetime.strptime(month_input, date_format).month
        except ValueError:
            continue

    return None


def add_birthday_interactive(birthdays):
    """Interactive prompt to add a birthday."""
    print("\n--- Add New Birthday ---")

    name = input("Name: ").strip()
    if not name:
        print("Name cannot be empty. Cancelled.")
        return False

    while True:
        month = parse_month(input("Month (1-12 or name): ").strip())
        if month is not None:
            break
        print("Invalid month. Please enter 1-12 or month name (e.g., 'January' or 'Jan')")

    while True:
        try:
            day = int(input("Day (1-31): ").strip())
        except ValueError:
            print("Please enter a number for the day")
            continue

        if validate_date(month, day):
            break
        print(f"Invalid date: {month}/{day}")

    birthday = normalize_birthday({
        'name': name,
        'month': month,
        'day': day,
    })

    date_str = datetime(2024, month, day).strftime('%B %d')
    print(f"\nAdd birthday: {name} - {date_str}")
    confirm = input("Confirm? (y/n): ").strip().lower()

    if confirm == 'y':
        birthdays.append(birthday)
        print(f"Added {name}'s birthday.")
        return True

    print("Cancelled.")
    return False


def list_birthdays(birthdays):
    """Display all birthdays."""
    birthdays, skipped = sanitize_birthdays(birthdays)
    if skipped:
        print(f"\nSkipped {skipped} malformed birthday entr{'y' if skipped == 1 else 'ies'}.")

    if not birthdays:
        print("\nNo birthdays in the list.")
        return

    print(f"\n--- All Birthdays ({len(birthdays)}) ---")
    for index, birthday in enumerate(birthdays, 1):
        date_str = datetime(2024, birthday['month'], birthday['day']).strftime('%B %d')
        print(f"{index:2d}. {birthday['name']:<25} - {date_str}")


def delete_birthday(birthdays):
    """Delete a birthday from the list."""
    clean_birthdays, skipped = sanitize_birthdays(birthdays)
    if skipped:
        print(f"\nSkipped {skipped} malformed birthday entr{'y' if skipped == 1 else 'ies'}.")

    if not clean_birthdays:
        print("\nNo birthdays to delete.")
        birthdays[:] = []
        return False

    list_birthdays(clean_birthdays)

    try:
        index = int(input("\nEnter number to delete (0 to cancel): ").strip())
    except ValueError:
        print("Please enter a valid number.")
        return False

    if index == 0:
        print("Cancelled.")
        birthdays[:] = clean_birthdays
        return False

    if not 1 <= index <= len(clean_birthdays):
        print("Invalid number.")
        return False

    deleted = clean_birthdays.pop(index - 1)
    birthdays[:] = clean_birthdays
    print(f"Deleted {deleted['name']}'s birthday")
    return True


def main():
    parser = argparse.ArgumentParser(description='Add birthdays to JSON file')
    parser.add_argument(
        '--file',
        default=None,
        help='JSON file to use (default: configured screens.birthday.birthday_file)',
    )
    args = parser.parse_args()

    filename = args.file or default_birthday_file()
    birthdays = load_birthdays(filename)

    print("=" * 50)
    print("Birthday Manager")
    print("=" * 50)
    print(f"Using file: {filename}")
    print(f"Current birthdays: {len(birthdays)}")

    modified = False

    while True:
        print("\n--- Menu ---")
        print("1. Add birthday")
        print("2. List all birthdays")
        print("3. Delete birthday")
        print("4. Save and exit")
        print("5. Exit without saving")

        choice = input("\nChoice: ").strip()

        if choice == '1':
            if add_birthday_interactive(birthdays):
                modified = True
        elif choice == '2':
            list_birthdays(birthdays)
        elif choice == '3':
            if delete_birthday(birthdays):
                modified = True
        elif choice == '4':
            if modified:
                try:
                    save_birthdays(birthdays, filename)
                except RuntimeError as exc:
                    print(exc)
                    continue
            else:
                print("\nNo changes made.")
            print("Goodbye!")
            break
        elif choice == '5':
            if modified:
                confirm = input("\nYou have unsaved changes. Exit anyway? (y/n): ").strip().lower()
                if confirm != 'y':
                    continue
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please enter 1-5.")


if __name__ == "__main__":
    main()
