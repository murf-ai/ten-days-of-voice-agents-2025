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

# Get absolute path to database file in the same folder
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(SCRIPT_DIR, "fraud_cases.db")


# ================================================================
# DATA MODEL
# ================================================================
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


# ================================================================
# DATABASE CLASS
# ================================================================
class FraudDatabase:
    """SQLite Database handler for fraud cases"""

    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self.init_database()

    # ------------------------------------------------------------
    # CREATE TABLE
    # ------------------------------------------------------------
    def init_database(self):
        """Initialize the database and create fraud_cases table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
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
                lastUpdated TEXT
            )
        """)

        conn.commit()
        conn.close()

        print("INFO Database initialized and ensured schema exists")

    # ------------------------------------------------------------
    # ADD CASE
    # ------------------------------------------------------------
    def add_fraud_case(self, case: FraudCase) -> bool:
        """Insert new fraud case"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO fraud_cases 
                (id, userName, securityIdentifier, cardEnding, cardType,
                 transactionName, transactionAmount, transactionTime, transactionLocation,
                 transactionCategory, transactionSource, status, securityQuestion,
                 securityAnswer, outcome, outcomeNote, createdAt, lastUpdated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                case.id, case.userName, case.securityIdentifier, case.cardEnding,
                case.cardType, case.transactionName, case.transactionAmount,
                case.transactionTime, case.transactionLocation, case.transactionCategory,
                case.transactionSource, case.status, case.securityQuestion,
                case.securityAnswer, case.outcome, case.outcomeNote,
                case.createdAt, datetime.now().isoformat()
            ))

            conn.commit()
            conn.close()
            print(f"INFO Added fraud case: {case.id}")
            return True

        except Exception as e:
            print("ERROR Error adding fraud case:", e)
            return False

    # ------------------------------------------------------------
    # GET ALL CASES
    # ------------------------------------------------------------
    def get_all_fraud_cases(self) -> List[FraudCase]:
        """Return all fraud cases"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM fraud_cases")
            rows = cursor.fetchall()
            conn.close()

            return [self._row_to_case(r) for r in rows]

        except Exception as e:
            print("ERROR Error getting all fraud cases:", e)
            return []

    # ------------------------------------------------------------
    # GET CASE BY CARD ENDING
    # ------------------------------------------------------------
    def get_fraud_case_by_card(self, card_ending: str) -> Optional[FraudCase]:
        """Find fraud case by last 4 digits of card"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM fraud_cases WHERE cardEnding = ?",
                (card_ending,)
            )

            row = cursor.fetchone()
            conn.close()

            return self._row_to_case(row) if row else None

        except Exception as e:
            print("ERROR Error getting fraud case by card:", e)
            return None

    # ------------------------------------------------------------
    # UPDATE STATUS
    # ------------------------------------------------------------
    def update_fraud_case_status(self, case_id: str, status: str, outcome: str, note: str) -> bool:
        """Update fraud case status and outcome"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE fraud_cases
                SET status = ?, outcome = ?, outcomeNote = ?, lastUpdated = ?
                WHERE id = ?
            """, (
                status, outcome, note,
                datetime.now().isoformat(),
                case_id
            ))

            conn.commit()
            conn.close()
            print(f"INFO Updated case {case_id}: {status} / {outcome}")
            return True

        except Exception as e:
            print("ERROR Error updating fraud case:", e)
            return False

    # ------------------------------------------------------------
    # STATS (FIXES YOUR ERROR)
    # ------------------------------------------------------------
    def get_statistics(self) -> Dict[str, Any]:
        """Return counts for statuses"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM fraud_cases")
            total = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM fraud_cases WHERE status = 'confirmed_fraud'")
            fraud = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM fraud_cases WHERE status = 'confirmed_safe'")
            safe = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM fraud_cases WHERE status = 'pending'")
            pending = cursor.fetchone()[0]

            conn.close()

            return {
                "total_cases": total,
                "confirmed_fraud": fraud,
                "confirmed_safe": safe,
                "pending": pending,
            }

        except Exception as e:
            print("ERROR Error generating statistics:", e)
            return {}

    # ------------------------------------------------------------
    # ROW → CASE OBJECT
    # ------------------------------------------------------------
    def _row_to_case(self, row: sqlite3.Row) -> FraudCase:
        """Convert DB row to FraudCase object"""
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
            outcome=row["outcome"],
            outcomeNote=row["outcomeNote"] or "",
            createdAt=row["createdAt"],
        )


# ================================================================
# SINGLETON INSTANCE
# ================================================================
db = FraudDatabase()
