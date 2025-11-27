#!/usr/bin/env python3
"""
Database Check Script for Fraud Cases
Run this to view all fraud cases and their current status
"""

import sqlite3
from pathlib import Path

# Database file path
DB_FILE = Path(__file__).parent / "shared-data" / "fraud_cases.db"

def check_fraud_cases():
    """Check all fraud cases in the database"""
    
    if not DB_FILE.exists():
        print("❌ Database file not found!")
        print(f"   Expected location: {DB_FILE}")
        return
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Get all cases
    cursor.execute('''
        SELECT id, userName, status, cardEnding, transactionName, 
               transactionAmount, verified, outcome, updated_at 
        FROM fraud_cases 
        ORDER BY updated_at DESC
    ''')
    
    rows = cursor.fetchall()
    
    if not rows:
        print("📭 No fraud cases found in database")
        conn.close()
        return
    
    print(f"\n🚨 FRAUD CASES DATABASE - Total Cases: {len(rows)}\n")
    print("=" * 80)
    
    for row in rows:
        case_id, name, status, card, merchant, amount, verified, outcome, updated = row
        
        # Status emoji
        status_emoji = {
            'pending_review': '⏳',
            'confirmed_safe': '✅',
            'confirmed_fraud': '🚨',
            'verification_failed': '❌'
        }.get(status, '❓')
        
        print(f"\n{status_emoji} Case #{case_id}: {name}")
        print(f"   Card: XXXX-{card}")
        print(f"   Transaction: {merchant}")
        print(f"   Amount: ₹{amount:,.2f}")
        print(f"   Status: {status.upper().replace('_', ' ')}")
        print(f"   Verified: {'Yes' if verified else 'No'}")
        if outcome:
            print(f"   Outcome: {outcome}")
        print(f"   Last Updated: {updated}")
        print("-" * 80)
    
    conn.close()
    print("\n✅ Database check complete!\n")

if __name__ == "__main__":
    check_fraud_cases()
