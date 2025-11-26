import json
from typing import Dict, Any, List

def load_content() -> Dict[str, Any]:
    """Loads the tutor content from the JSON file."""
    try:
        # NOTE: Adjust path if your working directory is different.
        # This assumes the script is run from a root directory or the agent directory
        with open('shared-data/day4_tutor_content.json', 'r') as f:
            data = json.load(f)
        
        # Convert list to a dictionary for easy lookup by ID
        return {item["id"]: item for item in data}
    except FileNotFoundError:
        print("Error: day4_tutor_content.json not found. Ensure the file is in shared-data/.")
        return {}
    except json.JSONDecodeError:
        print("Error: Invalid JSON format in day4_tutor_content.json.")
        return {}

# Content available to all agents
TUTOR_CONTENT: Dict[str, Any] = load_content()
CONCEPT_IDS: List[str] = list(TUTOR_CONTENT.keys())

# If content loading fails, ensure there are at least some fallback IDs to avoid errors
if not CONCEPT_IDS:
    CONCEPT_IDS = ["variables", "loops"] 
    print("Warning: Using placeholder concept IDs.")