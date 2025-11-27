import json
from pathlib import Path
from datetime import datetime

FRAUD_DB_PATH = Path("fraud_cases.json")


def load_fraud_cases() -> list:
    if not FRAUD_DB_PATH.exists():
        print("No fraud_cases.json found. Exiting.")
        return []
    with open(FRAUD_DB_PATH, "r") as f:
        return json.load(f)


def save_fraud_cases(cases: list) -> None:
    with open(FRAUD_DB_PATH, "w") as f:
        json.dump(cases, f, indent=2)


def find_case_by_username(username: str, cases: list) -> dict | None:
    for c in cases:
        if c.get("userName", "").lower() == username.lower():
            return c
    return None


if __name__ == "__main__":
    cases = load_fraud_cases()
    if not cases:
        exit(1)

    username = input("[Agent] Hello, I'm calling from the Fraud Department. May I get your full name? ")
    if not username.strip():
        print("[Agent] Name empty. Exiting.")
        exit(1)

    case = find_case_by_username(username, cases)
    if not case:
        print(f"[Agent] I couldn't find any cases for {username}. Exiting.")
        exit(1)

    print(f"[Agent] Thanks {username}. I found one case. I'll ask one security question to verify your identity: {case.get('securityQuestion')}")
    answer = input("[Agent] Your answer: ")
    if answer.strip().lower() != case.get("securityAnswer", "").strip().lower():
        case["case"] = "verification_failed"
        case["outcome_note"] = "Verification failed during call."
        case["last_updated"] = datetime.now().isoformat()
        save_fraud_cases(cases)
        print("[Agent] I'm sorry, I couldn't verify your identity. For your safety, I cannot discuss this case further. Goodbye.")
        exit(0)

    print("[Agent] Verification successful. I'll read the suspicious transaction now.")

    masked = f"**** {case.get('cardEnding', 'XXXX')}"
    print(f"[Agent] We detected a suspicious transaction on your card {masked}, amount {case.get('amount')}, merchant {case.get('transactionName')}, source {case.get('transactionSource')}, location {case.get('location')} at {case.get('transactionTime')}")

    resp = input("[Agent] Did you make this transaction? (yes/no) ")
    if resp.strip().lower() in ("y", "yes"):
        case["case"] = "confirmed_safe"
        case["outcome_note"] = "Customer confirmed transaction as legitimate."
        case["last_updated"] = datetime.now().isoformat()
        print("[Agent] Thanks for confirming. We've marked the case as safe. If you notice anything else, contact the bank. Goodbye.")
    else:
        case["case"] = "confirmed_fraud"
        case["outcome_note"] = "Customer denied the transaction; mock card blocked and dispute raised."
        case["last_updated"] = datetime.now().isoformat()
        print("[Agent] Thank you. We've marked this transaction as fraudulent, blocked the card, and raised a dispute. Our fraud team will reach out soon. Goodbye.")

    save_fraud_cases(cases)

    print("\n[DB] Updated case:\n")
    print(json.dumps(case, indent=2))
