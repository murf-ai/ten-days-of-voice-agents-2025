#!/usr/bin/env python3
"""Simple script to view wellness check-in history."""

import json
from pathlib import Path
from datetime import datetime


def view_wellness_log():
    """Display wellness check-in history in a readable format."""
    wellness_file = Path("wellness_log.json")
    
    if not wellness_file.exists():
        print("No wellness log found yet. Complete your first check-in to create it!")
        return
    
    with open(wellness_file, "r") as f:
        data = json.load(f)
    
    check_ins = data.get("check_ins", [])
    
    if not check_ins:
        print("No check-ins recorded yet.")
        return
    
    print(f"\n{'='*60}")
    print(f"WELLNESS CHECK-IN HISTORY ({len(check_ins)} total)")
    print(f"{'='*60}\n")
    
    for i, checkin in enumerate(check_ins, 1):
        date = checkin.get("date", "Unknown date")
        mood = checkin.get("mood", "Not specified")
        energy = checkin.get("energy_level", "Not specified")
        objectives = checkin.get("objectives", [])
        self_care = checkin.get("self_care_intentions", "None specified")
        summary = checkin.get("summary", "")
        
        print(f"Check-in #{i} - {date}")
        print(f"{'-'*60}")
        print(f"Mood: {mood}")
        print(f"Energy Level: {energy}")
        print(f"Objectives:")
        for obj in objectives:
            print(f"  • {obj}")
        print(f"Self-Care: {self_care}")
        if summary:
            print(f"Summary: {summary}")
        print()


if __name__ == "__main__":
    view_wellness_log()
