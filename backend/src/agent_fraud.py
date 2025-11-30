import os
import json
import logging
from typing import Dict, Any
import asyncio 

from dotenv import load_dotenv

# LiveKit Agent imports
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
    function_tool,
    RunContext,
)
# LiveKit Plugin imports
from livekit.plugins import google, murf, deepgram, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel 

load_dotenv(".env.local")
# Set logging to INFO, but run with LOG_LEVEL=DEBUG in terminal for detailed error messages
logger = logging.getLogger("fraud.agent")

# --- Configuration & File Paths ---
FRAUD_DB_FILE = 'fraud_cases.json' 
VOICE_FRAUD_REP = "Alicia" # CHANGED: A professional, calm voice for a fraud representative
TARGET_CUSTOMER_NAME = "Elias Vance" # The single MVP customer

# --- Database Mock & Helper Functions ---

def initialize_database_file():
    """Creates the initial fraud_cases.json file with one pending case for the MVP."""
    if not os.path.exists(FRAUD_DB_FILE):
        print(f"Creating initial {FRAUD_DB_FILE}...")
        initial_case = [
            {
                "case_id": "FC00129",
                "customer_name": TARGET_CUSTOMER_NAME,
                "security_id": "EV-2983",
                "masked_card": "**** **** **** 7311",
                "transaction_amount": 985.50,
                "merchant_name": "Global Tech Imports",
                "location": "Los Angeles, CA",
                "timestamp": "2025-11-26 18:45 PST",
                "security_q_answer": "2983",  # The answer for verification
                "status": "pending_review",
                "outcome_note": "Initial case creation."
            }
        ]
        with open(FRAUD_DB_FILE, 'w') as f:
            json.dump(initial_case, f, indent=4)
        print("Database file created with one pending case.")

def load_fraud_case_sync(customer_name: str) -> Dict[str, Any] | None:
    """Loads the specific case from the mock DB."""
    try:
        with open(FRAUD_DB_FILE, 'r') as f:
            cases = json.load(f)
            for case in cases:
                # This line requires 'case' to be a dictionary, not a string
                if case['customer_name'] == customer_name: 
                    return case
            return None
    except FileNotFoundError:
        logger.error(f"Fraud DB file not found at {FRAUD_DB_FILE}.")
        return None
    except Exception:
        # Added this to catch corruption errors in the JSON file
        logger.exception(f"Error reading and parsing data from {FRAUD_DB_FILE}.")
        return None 

def update_fraud_case_sync(updated_case_data: Dict[str, Any]) -> bool:
    """Updates the status and note in the mock DB file."""
    try:
        with open(FRAUD_DB_FILE, 'r') as f:
            cases = json.load(f)
    except:
        cases = []

    # Find and replace the specific case by case_id
    found = False
    for i, case in enumerate(cases):
        if case.get('case_id') == updated_case_data.get('case_id'):
            # Update only the status and outcome_note fields
            cases[i]['status'] = updated_case_data['status']
            cases[i]['outcome_note'] = updated_case_data['outcome_note']
            found = True
            break
    
    # Write the modified list back to the file
    with open(FRAUD_DB_FILE, 'w') as f:
        json.dump(cases, f, indent=4)

    # Console log for debugging (MVP requirement)
    logger.info(f"DB UPDATE: Case {updated_case_data.get('case_id')} set to status: {updated_case_data['status']}")
    logger.info(f"DB OUTCOME NOTE: {updated_case_data['outcome_note']}")
    return True

# --- LLM Tool for Fraud Case Logic ---

@function_tool
async def handle_final_fraud_status(ctx: RunContext[dict], case_id: str, status: str, outcome_note: str):
    """
    Called at the end of the conversation to update the fraud case status in the database.
    Status must be one of: 'confirmed_safe', 'confirmed_fraud', or 'verification_failed'.
    """
    
    # Reload the original case to ensure we retain all original fields
    original_case = await asyncio.to_thread(load_fraud_case_sync, TARGET_CUSTOMER_NAME) 
    
    if not original_case:
        logger.error(f"Failed to load case {case_id} for update.")
        return {"status": "error", "verbal_summary": "I am sorry, I encountered an internal error. Please call back later."}

    # Update the status and note on the full case data structure
    original_case['status'] = status
    original_case['outcome_note'] = outcome_note
    
    # Update the case asynchronously
    await asyncio.to_thread(update_fraud_case_sync, original_case)
    
    # The LLM will speak this verbal summary and then disconnect
    return {
        "status": "success", 
        "verbal_summary": f"Thank you for your time. We have updated your case to status: {status}. We are now taking the action of: {outcome_note.split('.')[0]}."
    }

# --- The Fraud Agent Class ---

class FraudAgent(Agent):
    """Phoenix Financial Fraud Detection Agent."""
    def __init__(self, dynamic_instructions: str): 
        super().__init__(
            instructions=dynamic_instructions,
            tools=[
                handle_final_fraud_status,
            ]
        )

# --- LiveKit Entrypoint (UPDATED with dynamic data loading) ---

async def entrypoint(ctx: JobContext):
    logger.info("Starting Fraud Agent and Loading Case Data...")
    
    # --- 1. Load the single MVP case from the database ---
    fraud_case_data = await asyncio.to_thread(load_fraud_case_sync, TARGET_CUSTOMER_NAME)

    if not fraud_case_data:
        logger.error(f"FATAL: Could not load fraud case for {TARGET_CUSTOMER_NAME}. Ending job.")
        # Attempt to disconnect if loading fails
        await ctx.disconnect() 
        return

    # --- 2. Dynamically build the LLM Instructions ---
    dynamic_instructions = f"""You are AVA, a highly professional, calm, and reassuring Fraud Detection Representative for PHOENIX FINANCIAL.
        
        You are handling **Case ID {fraud_case_data['case_id']}** for customer **{fraud_case_data['customer_name']}**.
        
        You **MUST** follow this exact flow:
        1. GREETING & INTENT: Start with the script: "Thank you for calling Phoenix Financial. My name is Ava, and I am a Fraud Protection Representative. I am calling regarding a suspicious transaction on your account."
        2. VERIFICATION: Immediately ask for the last four digits of the user's Security Identifier. **The correct answer is '{fraud_case_data['security_q_answer']}'**.
            * If the user answers correctly, proceed to Step 3.
            * If the user answers incorrectly, politely state you cannot proceed, then call the `handle_final_fraud_status` tool with `case_id='{fraud_case_data['case_id']}'`, `status='verification_failed'`, and `outcome_note='Identity confirmation failed by user. Call ended.'`. Speak the tool's verbal summary and hang up.
        3. TRANSACTION DISCLOSURE: Once verified, read the suspicious transaction details to the user:
            * Amount: ${fraud_case_data['transaction_amount']:.2f}
            * Merchant: {fraud_case_data['merchant_name']}
            * Location/Time: {fraud_case_data['location']} yesterday at {fraud_case_data['timestamp'].split()[-2]}
            * Card: Ending in {fraud_case_data['masked_card'].split()[-1]}
        4. CONFIRMATION: Ask the user clearly: "**Did you authorize this transaction? Please answer Yes or No.**"
        5. CLOSURE:
            * If the user says YES (legitimate): Call `handle_final_fraud_status` with `case_id='{fraud_case_data['case_id']}'`, `status='confirmed_safe'`, and `outcome_note='Customer confirmed transaction as legitimate. Alert removed.'`. Speak the summary and hang up.
            * If the user says NO (fraudulent): Call `handle_final_fraud_status` with `case_id='{fraud_case_data['case_id']}'`, `status='confirmed_fraud'`, and `outcome_note='Customer denied transaction. Card blocked, dispute filed, new card being issued.'`. Speak the summary and hang up.

        Do not ask for full card numbers, PINs, or credentials.
    """

    # Initialize the LLM, STT, and TTS components
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash", api_key=os.getenv("GOOGLE_API_KEY")),
        tts=murf.TTS(voice=VOICE_FRAUD_REP, style="Conversation", text_pacing=True), 
        turn_detection=MultilingualModel(),
        vad=silero.VAD.load(),
    )

    # --- 3. Pass the dynamic instructions to the agent ---
    agent = FraudAgent(dynamic_instructions=dynamic_instructions) 
    await session.start(agent=agent, room=ctx.room)
    await ctx.connect()

if __name__ == "__main__":
    # Ensure the fraud case file is initialized correctly before starting
    initialize_database_file() 
    
    # Run the worker to listen for incoming job requests
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        )
    )