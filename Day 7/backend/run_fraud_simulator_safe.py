import asyncio
import json
from pathlib import Path

from src.fraud_agent import FraudAgent, FRAUD_DB_PATH, load_fraud_cases


async def run_simulation_safe():
    agent = FraudAgent()
    resp = await agent.greet(None)
    print(f"[Agent] {resp}")

    username = "John Doe"
    print(f"[User] My name is {username}")
    resp = await agent.ask_for_username(None, username)
    print(f"[Agent] {resp}")

    case = agent.case
    if not case:
        print("[Error] No case loaded; exiting")
        return

    answer = case.get("securityAnswer")
    print(f"[User] {answer}")
    resp = await agent.verify_security_answer(None, answer)
    print(f"[Agent] {resp}")

    resp = await agent.read_transaction(None)
    print(f"[Agent] {resp}")

    print("[User] Yes")
    resp = await agent.mark_safe(None)
    print(f"[Agent] {resp}")

    cases = load_fraud_cases()
    print("\n[DB] Updated case:\n")
    for c in cases:
        if c.get("securityIdentifier") == case.get("securityIdentifier"):
            print(json.dumps(c, indent=2))
            break


if __name__ == "__main__":
    asyncio.run(run_simulation_safe())
