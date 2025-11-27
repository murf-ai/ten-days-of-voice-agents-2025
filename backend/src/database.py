"""
SQLite Database Module for Fraud Alert System
Handles all database operations for fraud cases
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict

# Get absolute path to database file (same directory as this script)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(SCRIPT_DIR, "fraud_cases.db")


@dataclass
class FraudCase:
    """Fraud case data model"""
    id: str
    userName: str
    securityIdentifier: str
    cardEnding: str
    cardType: str
    transactionName: str
    transactionAmount: str
    transactionTime: str
    transactionLocation: str
    transactionCategory: str
    transactionSource: str
    status: str
    securityQuestion: str
    securityAnswer: str
    createdAt: str
    outcome: str = "pending"
    outcomeNote: str = ""


class FraudDatabase:
    """SQLite Database handler for fraud cases"""

    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self.init_database()

    def init_database(self) -> None:
        """Initialize the database with fraud cases table"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create fraud cases table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS fraud_cases (
                    id TEXT PRIMARY KEY,
                    userName TEXT NOT NULL,
                    securityIdentifier TEXT,
                    cardEnding TEXT NOT NULL,
                    cardType TEXT,
                    transactionName TEXT,
                    transactionAmount TEXT,
                    transactionTime TEXT,
                    transactionLocation TEXT,
                    transactionCategory TEXT,
                    transactionSource TEXT,
                    status TEXT DEFAULT 'pending',
                    securityQuestion TEXT,
                    securityAnswer TEXT,
                    outcome TEXT DEFAULT 'pending',
                    outcomeNote TEXT,
                    createdAt TEXT,
                    lastUpdated TEXT,
                    UNIQUE(cardEnding)
                )
                """
            )

        print("✅ Database initialized successfully")

    def add_fraud_case(self, case: FraudCase) -> bool:
        """Add a new fraud case to the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT INTO fraud_cases 
                    (id, userName, securityIdentifier, cardEnding, cardType, 
                     transactionName, transactionAmount, transactionTime, 
                     transactionLocation, transactionCategory, transactionSource,
                     status, securityQuestion, securityAnswer, outcome, outcomeNote,
                     createdAt, lastUpdated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        case.id,
                        case.userName,
                        case.securityIdentifier,
                        case.cardEnding,
                        case.cardType,
                        case.transactionName,
                        case.transactionAmount,
                        case.transactionTime,
                        case.transactionLocation,
                        case.transactionCategory,
                        case.transactionSource,
                        case.status,
                        case.securityQuestion,
                        case.securityAnswer,
                        case.outcome,
                        case.outcomeNote,
                        case.createdAt,
                        datetime.now().isoformat(),
                    ),
                )

            print(f"✅ Added fraud case: {case.id}")
            return True
        except Exception as e:
            print(f"❌ Error adding fraud case: {e}")
            return False

    def get_fraud_case_by_card(self, card_ending: str) -> Optional[FraudCase]:
        """Get fraud case by card ending digits"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT * FROM fraud_cases WHERE cardEnding = ?",
                    (card_ending,),
                )

                row = cursor.fetchone()

            if row:
                return self._row_to_fraud_case(row)
            return None
        except Exception as e:
            print(f"❌ Error getting fraud case: {e}")
            return None

    def get_fraud_case_by_id(self, case_id: str) -> Optional[FraudCase]:
        """Get fraud case by ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT * FROM fraud_cases WHERE id = ?",
                    (case_id,),
                )

                row = cursor.fetchone()

            if row:
                return self._row_to_fraud_case(row)
            return None
        except Exception as e:
            print(f"❌ Error getting fraud case: {e}")
            return None

    def get_all_fraud_cases(self) -> List[FraudCase]:
        """Get all fraud cases from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute("SELECT * FROM fraud_cases")
                rows = cursor.fetchall()

            return [self._row_to_fraud_case(row) for row in rows]
        except Exception as e:
            print(f"❌ Error getting all fraud cases: {e}")
            return []

    def update_fraud_case_status(
        self, case_id: str, status: str, outcome: str, note: str
    ) -> bool:
        """Update fraud case status and outcome"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    UPDATE fraud_cases 
                    SET status = ?, outcome = ?, outcomeNote = ?, lastUpdated = ?
                    WHERE id = ?
                    """,
                    (status, outcome, note, datetime.now().isoformat(), case_id),
                )

            print(
                f"✅ Updated fraud case {case_id}: status={status}, outcome={outcome}"
            )
            return True
        except Exception as e:
            print(f"❌ Error updating fraud case: {e}")
            return False

    def delete_fraud_case(self, case_id: str) -> bool:
        """Delete a fraud case"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM fraud_cases WHERE id = ?", (case_id,))

            print(f"✅ Deleted fraud case: {case_id}")
            return True
        except Exception as e:
            print(f"❌ Error deleting fraud case: {e}")
            return False

    def clear_all_cases(self) -> bool:
        """Clear all fraud cases from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM fraud_cases")

            print("✅ Cleared all fraud cases")
            return True
        except Exception as e:
            print(f"❌ Error clearing database: {e}")
            return False

    def export_to_json(self, output_file: str = "fraud_cases_backup.json") -> bool:
        """Export all fraud cases to JSON for backup"""
        try:
            cases = self.get_all_fraud_cases()
            data = {
                "fraud_cases": [asdict(case) for case in cases],
            }

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            print(f"✅ Exported {len(cases)} cases to {output_file}")
            return True
        except Exception as e:
            print(f"❌ Error exporting to JSON: {e}")
            return False

    def import_from_json(self, input_file: str) -> bool:
        """Import fraud cases from JSON file"""
        try:
            with open(input_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.clear_all_cases()

            for case_data in data.get("fraud_cases", []):
                case = FraudCase(**case_data)
                self.add_fraud_case(case)

            print(
                f"✅ Imported {len(data.get('fraud_cases', []))} cases from {input_file}"
            )
            return True
        except Exception as e:
            print(f"❌ Error importing from JSON: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT COUNT(*) FROM fraud_cases")
                total = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(*) FROM fraud_cases WHERE status = 'confirmed_fraud'"
                )
                fraud_count = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(*) FROM fraud_cases WHERE status = 'confirmed_safe'"
                )
                safe_count = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(*) FROM fraud_cases WHERE status = 'pending'"
                )
                pending_count = cursor.fetchone()[0]

            return {
                "total_cases": total,
                "confirmed_fraud": fraud_count,
                "confirmed_safe": safe_count,
                "pending": pending_count,
            }
        except Exception as e:
            print(f"❌ Error getting statistics: {e}")
            return {}

    @staticmethod
    def _row_to_fraud_case(row: sqlite3.Row) -> FraudCase:
        """Convert database row to FraudCase object"""
        return FraudCase(
            id=row["id"],
            userName=row["userName"],
            securityIdentifier=row["securityIdentifier"],
            cardEnding=row["cardEnding"],
            cardType=row["cardType"],
            transactionName=row["transactionName"],
            transactionAmount=row["transactionAmount"],
            transactionTime=row["transactionTime"],
            transactionLocation=row["transactionLocation"],
            transactionCategory=row["transactionCategory"],
            transactionSource=row["transactionSource"],
            status=row["status"],
            securityQuestion=row["securityQuestion"],
            securityAnswer=row["securityAnswer"],
            createdAt=row["createdAt"],
            outcome=row["outcome"],
            outcomeNote=row["outcomeNote"] if row["outcomeNote"] else "",
        )


# Initialize database instance
db = FraudDatabase()
