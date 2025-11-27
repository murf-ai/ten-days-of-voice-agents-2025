"""
Verification + Initialization Script for SQLite Fraud Cases DB
Creates the database (if needed), inserts sample fake cases (unique dataset),
and prints statistics.

Updated dataset: Case1 = Meera Shah (card last4 7321) — used for LinkedIn demo.
"""

import os
from datetime import datetime
import uuid
from database import FraudDatabase, FraudCase

# --- Initialize DB ---
db = FraudDatabase()

print("✅ Database module imported successfully")

# Correct DB path check (database lives next to this script)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(SCRIPT_DIR, "fraud_cases.db")
print(f"📁 Database file exists: {os.path.exists(DB_FILE)}")


# --- Insert sample cases ONLY if DB is empty ---
existing = db.get_all_fraud_cases()

if not existing:
    print("📝 No cases found → inserting sample fake fraud cases...")

    now = datetime.now().isoformat()

    sample_cases = [
        FraudCase(
            id=str(uuid.uuid4()),
            userName="Meera Shah",
            securityIdentifier="SID-91001",
            cardEnding="7321",
            cardType="Visa",
            transactionName="BlueLeaf Electronics",
            transactionAmount="₹4,799",
            transactionTime="2025-11-27T14:55:00+05:30",
            transactionLocation="Ahmedabad",
            transactionCategory="electronics",
            transactionSource="blueleaf-store.com",
            status="pending",
            securityQuestion="What city were you born in?",
            securityAnswer="surat",
            createdAt=now
        ),
        FraudCase(
            id=str(uuid.uuid4()),
            userName="Aarav Nanda",
            securityIdentifier="SID-91002",
            cardEnding="5614",
            cardType="Mastercard",
            transactionName="FlyHigh Travel Agency",
            transactionAmount="₹18,250",
            transactionTime="2025-11-26T10:15:00+05:30",
            transactionLocation="New Delhi",
            transactionCategory="travel",
            transactionSource="flyhigh-booking.com",
            status="pending",
            securityQuestion="What is your favorite holiday destination?",
            securityAnswer="goa",
            createdAt=now
        ),
        FraudCase(
            id=str(uuid.uuid4()),
            userName="Zoya Khan",
            securityIdentifier="SID-91003",
            cardEnding="8873",
            cardType="Rupay",
            transactionName="StreamZone Premium Subscription",
            transactionAmount="₹499",
            transactionTime="2025-11-27T20:22:00+05:30",
            transactionLocation="Bengaluru",
            transactionCategory="streaming",
            transactionSource="streamzone.in",
            status="pending",
            securityQuestion="What is your pet’s name?",
            securityAnswer="snowy",
            createdAt=now
        ),
    ]

    for c in sample_cases:
        ok = db.add_fraud_case(c)
        print(f"  - Inserted: {c.userName} (ok={ok})")

    print("✅ Sample cases inserted successfully!")

else:
    print(f"🔎 Found existing cases → skipping seeding ({len(existing)} records already present)")


# --- Print Stats ---
stats = db.get_statistics()
print("\n📊 DATABASE STATISTICS")
print(f"   Total Cases     : {stats.get('total_cases')}")
print(f"   Pending         : {stats.get('pending')}")
print(f"   Confirmed Safe  : {stats.get('confirmed_safe')}")
print(f"   Confirmed Fraud : {stats.get('confirmed_fraud')}")
print("\n🚀 Database Setup Complete — Ready for Fraud Alert Agent!\n")
