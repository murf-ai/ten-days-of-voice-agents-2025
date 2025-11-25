#!/usr/bin/env python3
"""Helper functions for Notion integration."""

import json
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(".env.local")

NOTION_API_KEY = os.getenv("NOTION_API_KEY")

# Load database IDs from config
config_file = Path("notion_config.json")
if config_file.exists():
    with open(config_file, "r") as f:
        config = json.load(f)
    TASKS_DB_ID = config["databases"]["tasks"]
    CHECKINS_DB_ID = config["databases"]["checkins"]
else:
    TASKS_DB_ID = None
    CHECKINS_DB_ID = None


def save_checkin_to_notion(checkin_data):
    """Save a check-in to Notion."""
    if not NOTION_API_KEY or not CHECKINS_DB_ID:
        return False, "Notion not configured"
    
    try:
        import requests
        
        headers = {
            "Authorization": f"Bearer {NOTION_API_KEY}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
        
        page_data = {
            "parent": {"database_id": CHECKINS_DB_ID},
            "properties": {
                "Date": {
                    "date": {"start": checkin_data.get("date", datetime.now().strftime("%Y-%m-%d"))}
                },
                "Mood": {
                    "rich_text": [{"text": {"content": checkin_data.get("mood", "")}}]
                },
                "Energy": {
                    "select": {"name": checkin_data.get("energy_level", "Medium").capitalize()}
                },
                "Objectives": {
                    "multi_select": [{"name": obj} for obj in checkin_data.get("objectives", [])]
                },
                "Summary": {
                    "rich_text": [{"text": {"content": checkin_data.get("summary", "")}}]
                }
            }
        }
        
        response = requests.post(
            "https://api.notion.com/v1/pages",
            headers=headers,
            json=page_data
        )
        
        if response.status_code == 200:
            return True, "Saved to Notion successfully!"
        else:
            error = response.json().get("message", "Unknown error")
            return False, f"Notion API error: {error}"
            
    except Exception as e:
        return False, f"Error: {str(e)}"


def save_task_to_notion(task_title):
    """Save a task to Notion."""
    if not NOTION_API_KEY or not TASKS_DB_ID:
        return False, "Notion not configured"
    
    try:
        import requests
        
        headers = {
            "Authorization": f"Bearer {NOTION_API_KEY}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
        
        task_data = {
            "parent": {"database_id": TASKS_DB_ID},
            "properties": {
                "Name": {
                    "title": [{"text": {"content": task_title}}]
                },
                "Status": {
                    "select": {"name": "Not started"}
                },
                "Created": {
                    "date": {"start": datetime.now().strftime("%Y-%m-%d")}
                }
            }
        }
        
        response = requests.post(
            "https://api.notion.com/v1/pages",
            headers=headers,
            json=task_data
        )
        
        if response.status_code == 200:
            return True, "Task saved to Notion!"
        else:
            error = response.json().get("message", "Unknown error")
            return False, f"Notion API error: {error}"
            
    except Exception as e:
        return False, f"Error: {str(e)}"


def test_notion_connection():
    """Test if Notion is properly configured."""
    print("\n" + "="*60)
    print("NOTION CONNECTION TEST")
    print("="*60 + "\n")
    
    # Check API key
    if not NOTION_API_KEY:
        print("❌ NOTION_API_KEY not found in .env.local")
        return False
    else:
        print(f"✅ NOTION_API_KEY found: {NOTION_API_KEY[:20]}...")
    
    # Check database IDs
    if not TASKS_DB_ID or not CHECKINS_DB_ID:
        print("❌ Database IDs not found in notion_config.json")
        return False
    else:
        print(f"✅ Tasks DB ID: {TASKS_DB_ID}")
        print(f"✅ Check-ins DB ID: {CHECKINS_DB_ID}")
    
    # Check requests library
    try:
        import requests
        print("✅ requests library installed")
    except ImportError:
        print("❌ requests library not installed")
        print("   Install with: pip install requests")
        return False
    
    # Test API connection
    print("\nTesting Notion API connection...")
    try:
        headers = {
            "Authorization": f"Bearer {NOTION_API_KEY}",
            "Notion-Version": "2022-06-28"
        }
        
        response = requests.get(
            f"https://api.notion.com/v1/databases/{CHECKINS_DB_ID}",
            headers=headers
        )
        
        if response.status_code == 200:
            db_info = response.json()
            print(f"✅ Successfully connected to: {db_info.get('title', [{}])[0].get('plain_text', 'Database')}")
        else:
            print(f"❌ API Error: {response.json().get('message', 'Unknown error')}")
            print("   Make sure the database is shared with your integration!")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False
    
    print("\n" + "="*60)
    print("✅ NOTION IS READY TO USE!")
    print("="*60 + "\n")
    return True


if __name__ == "__main__":
    test_notion_connection()
