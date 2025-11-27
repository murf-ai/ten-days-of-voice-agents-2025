import asyncio
import json
from pathlib import Path

from src.fraud_agent import FraudAgent, FRAUD_DB_PATH, load_fraud_cases


async def run_simulation():
    agent = FraudAgent()
    # Greet
    resp = await agent.greet(None)
    print(f"[Agent] {resp}")

    # Simulate user 'John Doe' starting a call
    username = "John Doe"
    print(f"[User] My name is {username}")
    resp = await agent.ask_for_username(None, username)
    print(f"[Agent] {resp}")

    # Read the security question
    case = agent.case
    if not case:
        print("[Error] No case loaded; exiting")
        return

    # Simulate providing correct security answer
    answer = case.get("securityAnswer")
    print(f"[User] {answer}")
    resp = await agent.verify_security_answer(None, answer)
    print(f"[Agent] {resp}")

    # Read the suspicious transaction
    resp = await agent.read_transaction(None)
    print(f"[Agent] {resp}")

    # Simulate user denying the transaction
    print("[User] No")
    resp = await agent.mark_fraudulent(None)
    print(f"[Agent] {resp}")

    # Show updated DB entry
    cases = load_fraud_cases()
    print("\n[DB] Updated case:\n")
    for c in cases:
        if c.get("securityIdentifier") == case.get("securityIdentifier"):
            print(json.dumps(c, indent=2))
            break


if __name__ == "__main__":
    asyncio.run(run_simulation())
