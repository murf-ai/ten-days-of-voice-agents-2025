import sqlite3
import json
from pathlib import Path
from datetime import datetime

DB_FILE = Path(__file__).parent / "fraud_cases.db"

class FraudDatabase:
    def __init__(self):
        self.db_path = DB_FILE
        self._init_database()
    
    def _init_database(self):
        """Initialize database with schema and sample data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create fraud_cases table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fraud_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                userName TEXT NOT NULL,
                securityIdentifier TEXT NOT NULL,
                securityQuestion TEXT NOT NULL,
                securityAnswer TEXT NOT NULL,
                cardEnding TEXT NOT NULL,
                status TEXT DEFAULT 'pending_review',
                transactionName TEXT NOT NULL,
                transactionAmount REAL NOT NULL,
                transactionTime TEXT NOT NULL,
                transactionCategory TEXT NOT NULL,
                transactionSource TEXT NOT NULL,
                transactionLocation TEXT NOT NULL,
                outcome TEXT DEFAULT '',
                verified BOOLEAN DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Check if we have data
        cursor.execute("SELECT COUNT(*) FROM fraud_cases")
        if cursor.fetchone()[0] == 0:
            # Insert sample fraud cases
            sample_cases = [
                (
                    "John Doe",
                    "JD12345",
                    "What is your mother's maiden name?",
                    "Smith",
                    "4242",
                    "pending_review",
                    "ABC Electronics Ltd",
                    15999.00,
                    "2025-11-27 02:30:00",
                    "Electronics",
                    "alibaba.com",
                    "Shanghai, China",
                    "",
                    0
                ),
                (
                    "Priya Sharma",
                    "PS67890",
                    "What city were you born in?",
                    "Mumbai",
                    "8765",
                    "pending_review",
                    "Luxury Fashion Store",
                    45000.00,
                    "2025-11-27 03:15:00",
                    "Fashion",
                    "luxuryboutique.eu",
                    "Paris, France",
                    "",
                    0
                ),
                (
                    "Raj Kumar",
                    "RK45678",
                    "What is your favorite color?",
                    "Blue",
                    "3456",
                    "pending_review",
                    "Tech Gadgets International",
                    28500.00,
                    "2025-11-26 23:45:00",
                    "Electronics",
                    "techgadgets.cn",
                    "Shenzhen, China",
                    "",
                    0
                ),
                (
                    "Ananya Patel",
                    "AP98765",
                    "What is your pet's name?",
                    "Max",
                    "7890",
                    "pending_review",
                    "Online Gaming Platform",
                    12000.00,
                    "2025-11-27 01:00:00",
                    "Gaming",
                    "gamepro.io",
                    "Singapore",
                    "",
                    0
                )
            ]
            
            cursor.executemany('''
                INSERT INTO fraud_cases (
                    userName, securityIdentifier, securityQuestion, securityAnswer,
                    cardEnding, status, transactionName, transactionAmount,
                    transactionTime, transactionCategory, transactionSource,
                    transactionLocation, outcome, verified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', sample_cases)
            
            conn.commit()
            print(f"✅ Initialized fraud database with {len(sample_cases)} sample cases")
        
        conn.close()
    
    def get_case_by_username(self, username: str):
        """Get pending fraud case for a specific user"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM fraud_cases 
            WHERE LOWER(userName) = LOWER(?) 
            AND status = 'pending_review'
            ORDER BY created_at DESC
            LIMIT 1
        ''', (username,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def update_case_status(self, case_id: int, status: str, outcome: str, verified: bool = True):
        """Update fraud case status after investigation"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE fraud_cases 
            SET status = ?, outcome = ?, verified = ?, updated_at = ?
            WHERE id = ?
        ''', (status, outcome, verified, datetime.now().isoformat(), case_id))
        
        conn.commit()
        conn.close()
        print(f"✅ Updated case {case_id}: {status} - {outcome}")
    
    def get_all_pending_cases(self):
        """Get all pending cases (for admin view)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM fraud_cases 
            WHERE status = 'pending_review'
            ORDER BY created_at DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_case_by_id(self, case_id: int):
        """Get specific case by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM fraud_cases WHERE id = ?', (case_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
