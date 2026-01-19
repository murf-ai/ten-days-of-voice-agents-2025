"""Initialize SQLite database with sample fraud cases"""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent / "fraud_cases.db"

def init_database():
    """Create database and populate with sample fraud cases"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create fraud_cases table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fraud_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            userName TEXT NOT NULL,
            securityIdentifier TEXT NOT NULL,
            cardEnding TEXT NOT NULL,
            case_status TEXT DEFAULT 'pending_review',
            transactionName TEXT NOT NULL,
            transactionAmount REAL NOT NULL,
            transactionTime TEXT NOT NULL,
            transactionCategory TEXT NOT NULL,
            transactionSource TEXT NOT NULL,
            transactionLocation TEXT,
            securityQuestion TEXT NOT NULL,
            securityAnswer TEXT NOT NULL,
            outcome_note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Clear existing data for fresh start
    cursor.execute("DELETE FROM fraud_cases")
    
    # Sample fraud cases
    fraud_cases = [
        {
            "userName": "Rajesh Kumar",
            "securityIdentifier": "RK2024",
            "cardEnding": "4242",
            "transactionName": "Global Electronics Ltd",
            "transactionAmount": 45999.00,
            "transactionTime": (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
            "transactionCategory": "electronics",
            "transactionSource": "alibaba.com",
            "transactionLocation": "Shanghai, China",
            "securityQuestion": "What is your mother's maiden name?",
            "securityAnswer": "sharma"
        },
        {
            "userName": "Vikram Singh",
            "securityIdentifier": "VS1234",
            "cardEnding": "8765",
            "transactionName": "Luxury Fashion Store",
            "transactionAmount": 89500.00,
            "transactionTime": (datetime.now() - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S"),
            "transactionCategory": "fashion",
            "transactionSource": "luxuryfashion.ru",
            "transactionLocation": "Moscow, Russia",
            "securityQuestion": "What city were you born in?",
            "securityAnswer": "delhi"
        },
        {
            "userName": "Amit Patel",
            "securityIdentifier": "AP5678",
            "cardEnding": "3456",
            "transactionName": "Tech Gadgets Inc",
            "transactionAmount": 125000.00,
            "transactionTime": (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
            "transactionCategory": "electronics",
            "transactionSource": "techgadgets.com",
            "transactionLocation": "Lagos, Nigeria",
            "securityQuestion": "What is your favorite color?",
            "securityAnswer": "blue"
        },
        {
            "userName": "Arjun Reddy",
            "securityIdentifier": "AR9012",
            "cardEnding": "7890",
            "transactionName": "Online Gaming Credits",
            "transactionAmount": 15000.00,
            "transactionTime": (datetime.now() - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S"),
            "transactionCategory": "gaming",
            "transactionSource": "gamecredits.xyz",
            "transactionLocation": "Manila, Philippines",
            "securityQuestion": "What is your pet's name?",
            "securityAnswer": "bruno"
        },
        {
            "userName": "Karan Sharma",
            "securityIdentifier": "KS3344",
            "cardEnding": "5521",
            "transactionName": "Cryptocurrency Exchange",
            "transactionAmount": 250000.00,
            "transactionTime": (datetime.now() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
            "transactionCategory": "crypto",
            "transactionSource": "cryptoexchange.io",
            "transactionLocation": "Dubai, UAE",
            "securityQuestion": "What is your father's middle name?",
            "securityAnswer": "kumar"
        },
        {
            "userName": "Rohan Gupta",
            "securityIdentifier": "RG6677",
            "cardEnding": "2289",
            "transactionName": "Premium Software Subscription",
            "transactionAmount": 35000.00,
            "transactionTime": (datetime.now() - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S"),
            "transactionCategory": "software",
            "transactionSource": "premiumsoft.xyz",
            "transactionLocation": "Singapore",
            "securityQuestion": "What is your first school name?",
            "securityAnswer": "dav"
        },
        {
            "userName": "Siddharth Verma",
            "securityIdentifier": "SV8899",
            "cardEnding": "1122",
            "transactionName": "International Money Transfer",
            "transactionAmount": 180000.00,
            "transactionTime": (datetime.now() - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S"),
            "transactionCategory": "transfer",
            "transactionSource": "moneytransfer.net",
            "transactionLocation": "London, UK",
            "securityQuestion": "What is your favorite movie?",
            "securityAnswer": "sholay"
        },
        {
            "userName": "Nikhil Mehta",
            "securityIdentifier": "NM4455",
            "cardEnding": "9988",
            "transactionName": "Premium Watch Store",
            "transactionAmount": 275000.00,
            "transactionTime": (datetime.now() - timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S"),
            "transactionCategory": "luxury",
            "transactionSource": "luxurywatches.com",
            "transactionLocation": "Geneva, Switzerland",
            "securityQuestion": "What is your favorite food?",
            "securityAnswer": "biryani"
        },
        {
            "userName": "Aditya Joshi",
            "securityIdentifier": "AJ7766",
            "cardEnding": "3344",
            "transactionName": "Online Betting Platform",
            "transactionAmount": 95000.00,
            "transactionTime": (datetime.now() - timedelta(minutes=45)).strftime("%Y-%m-%d %H:%M:%S"),
            "transactionCategory": "gambling",
            "transactionSource": "betking.online",
            "transactionLocation": "Malta",
            "securityQuestion": "What is your nickname?",
            "securityAnswer": "adi"
        },
        {
            "userName": "Varun Kapoor",
            "securityIdentifier": "VK5566",
            "cardEnding": "6677",
            "transactionName": "Designer Clothing Store",
            "transactionAmount": 145000.00,
            "transactionTime": (datetime.now() - timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S"),
            "transactionCategory": "fashion",
            "transactionSource": "designerfashion.it",
            "transactionLocation": "Milan, Italy",
            "securityQuestion": "What is your birth city?",
            "securityAnswer": "bangalore"
        }
    ]
    
    # Insert fraud cases
    for case in fraud_cases:
        cursor.execute("""
            INSERT INTO fraud_cases (
                userName, securityIdentifier, cardEnding, transactionName,
                transactionAmount, transactionTime, transactionCategory,
                transactionSource, transactionLocation, securityQuestion, securityAnswer
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            case["userName"], case["securityIdentifier"], case["cardEnding"],
            case["transactionName"], case["transactionAmount"], case["transactionTime"],
            case["transactionCategory"], case["transactionSource"], case["transactionLocation"],
            case["securityQuestion"], case["securityAnswer"]
        ))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Database initialized at: {DB_PATH}")
    print(f"✅ Created {len(fraud_cases)} fraud cases")
    
    # Display the cases
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, userName, cardEnding, transactionName, transactionAmount, case_status FROM fraud_cases")
    rows = cursor.fetchall()
    
    print("\n📋 Sample Fraud Cases:")
    for row in rows:
        print(f"  ID {row[0]}: {row[1]} | Card **** {row[2]} | {row[3]} | ₹{row[4]:,.2f} | Status: {row[5]}")
    
    conn.close()

if __name__ == "__main__":
    init_database()
