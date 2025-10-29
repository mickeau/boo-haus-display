#!/usr/bin/env python3
"""
Add Birthday Script
Simple interactive script to add birthdays to the JSON file

Usage:
    python add_birthday.py
    python add_birthday.py --file custom_birthdays.json
"""

import json
import argparse
import os
from datetime import datetime

def load_birthdays(filename):
    """Load existing birthdays from JSON file"""
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Error reading {filename}. Starting with empty list.")
            return []
    else:
        print(f"{filename} not found. Creating new file.")
        return []

def save_birthdays(birthdays, filename):
    """Save birthdays to JSON file, sorted by date"""
    # Sort by month, then day
    birthdays.sort(key=lambda x: (x['month'], x['day']))
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(birthdays, f, indent=2, ensure_ascii=False)
    
    print(f"\nSaved to {filename}")

def validate_date(month, day):
    """Validate that the date is valid"""
    try:
        datetime(2024, month, day)  # Use 2024 (leap year) to allow Feb 29
        return True
    except ValueError:
        return False

def add_birthday_interactive(birthdays):
    """Interactive prompt to add a birthday"""
    print("\n--- Add New Birthday ---")
    
    # Get name
    name = input("Name: ").strip()
    if not name:
        print("Name cannot be empty. Cancelled.")
        return False
    
    # Get month
    while True:
        month_input = input("Month (1-12 or name): ").strip()
        
        # Try to parse as number
        try:
            month = int(month_input)
            if 1 <= month <= 12:
                break
        except ValueError:
            # Try to parse as month name
            try:
                month = datetime.strptime(month_input, '%B').month
                break
            except ValueError:
                try:
                    month = datetime.strptime(month_input, '%b').month
                    break
                except ValueError:
                    pass
        
        print("Invalid month. Please enter 1-12 or month name (e.g., 'January' or 'Jan')")
    
    # Get day
    while True:
        try:
            day = int(input("Day (1-31): ").strip())
            if validate_date(month, day):
                break
            else:
                print(f"Invalid date: {month}/{day}")
        except ValueError:
            print("Please enter a number for the day")
    
    # Create birthday entry
    birthday = {
        "name": name,
        "month": month,
        "day": day,
        "date": f"{month:02d}-{day:02d}"
    }
    
    # Confirm
    date_str = datetime(2024, month, day).strftime('%B %d')
    print(f"\nAdd birthday: {name} - {date_str}")
    confirm = input("Confirm? (y/n): ").strip().lower()
    
    if confirm == 'y':
        birthdays.append(birthday)
        print(f"Added {name}'s birthday!")
        return True
    else:
        print("Cancelled.")
        return False

def list_birthdays(birthdays):
    """Display all birthdays"""
    if not birthdays:
        print("\nNo birthdays in the list.")
        return
    
    print(f"\n--- All Birthdays ({len(birthdays)}) ---")
    for i, b in enumerate(birthdays, 1):
        date_str = datetime(2024, b['month'], b['day']).strftime('%B %d')
        print(f"{i:2d}. {b['name']:<25} - {date_str}")

def delete_birthday(birthdays):
    """Delete a birthday from the list"""
    if not birthdays:
        print("\nNo birthdays to delete.")
        return False
    
    list_birthdays(birthdays)
    
    try:
        index = int(input("\nEnter number to delete (0 to cancel): ").strip())
        if index == 0:
            print("Cancelled.")
            return False
        
        if 1 <= index <= len(birthdays):
            deleted = birthdays.pop(index - 1)
            print(f"Deleted {deleted['name']}'s birthday")
            return True
        else:
            print("Invalid number.")
            return False
    except ValueError:
        print("Please enter a valid number.")
        return False

def main():
    parser = argparse.ArgumentParser(description='Add birthdays to JSON file')
    parser.add_argument('--file', default='birthdays.json',
                       help='JSON file to use (default: birthdays.json)')
    args = parser.parse_args()
    
    filename = args.file
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
                save_birthdays(birthdays, filename)
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