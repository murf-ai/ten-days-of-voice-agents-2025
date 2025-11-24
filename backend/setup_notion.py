#!/usr/bin/env python3
"""Interactive setup script for Notion integration."""

import os
from pathlib import Path


def setup_notion():
    """Guide user through Notion integration setup."""
    
    print("\n" + "="*60)
    print("🌟 NOTION INTEGRATION SETUP")
    print("="*60 + "\n")
    
    print("This script will help you set up Notion integration for your")
    print("Health & Wellness Voice Companion.\n")
    
    # Check if .env.local exists
    env_file = Path(".env.local")
    
    if not env_file.exists():
        print("❌ Error: .env.local file not found!")
        print("Please create it first by copying .env.example\n")
        return
    
    # Read current env file
    with open(env_file, "r") as f:
        env_content = f.read()
    
    # Check if NOTION_API_KEY already exists
    if "NOTION_API_KEY" in env_content:
        print("✓ NOTION_API_KEY already exists in .env.local\n")
        update = input("Do you want to update it? (y/n): ").strip().lower()
        if update != 'y':
            print("\nSetup cancelled. Your existing configuration is unchanged.")
            return
    
    print("\n" + "-"*60)
    print("STEP 1: Get Your Notion API Key")
    print("-"*60)
    print("\n1. Go to: https://www.notion.so/my-integrations")
    print("2. Click 'New integration'")
    print("3. Name it 'Wellness Companion'")
    print("4. Select your workspace")
    print("5. Copy the 'Internal Integration Token'\n")
    
    api_key = input("Paste your Notion API key here: ").strip()
    
    if not api_key:
        print("\n❌ No API key provided. Setup cancelled.")
        return
    
    if not api_key.startswith("secret_"):
        print("\n⚠️  Warning: Notion API keys usually start with 'secret_'")
        confirm = input("Continue anyway? (y/n): ").strip().lower()
        if confirm != 'y':
            print("\nSetup cancelled.")
            return
    
    # Update .env.local
    if "NOTION_API_KEY" in env_content:
        # Replace existing key
        lines = env_content.split('\n')
        new_lines = []
        for line in lines:
            if line.startswith("NOTION_API_KEY"):
                new_lines.append(f"NOTION_API_KEY={api_key}")
            else:
                new_lines.append(line)
        env_content = '\n'.join(new_lines)
    else:
        # Add new key
        if not env_content.endswith('\n'):
            env_content += '\n'
        env_content += f"\n# Notion Integration\nNOTION_API_KEY={api_key}\n"
    
    # Write updated env file
    with open(env_file, "w") as f:
        f.write(env_content)
    
    print("\n✅ API key saved to .env.local")
    
    print("\n" + "-"*60)
    print("STEP 2: Create Notion Databases")
    print("-"*60)
    print("\nYou need to create two databases in Notion:\n")
    
    print("📋 Database 1: Daily Wellness")
    print("   Properties:")
    print("   - Date (Date)")
    print("   - Mood (Text)")
    print("   - Energy (Select: High, Medium, Low)")
    print("   - Objectives (Multi-select)")
    print("   - Summary (Text)\n")
    
    print("✓ Database 2: Tasks (Optional)")
    print("   Properties:")
    print("   - Name (Title)")
    print("   - Status (Select: Not started, In progress, Complete)")
    print("   - Created (Date)\n")
    
    print("-"*60)
    print("STEP 3: Share Databases with Integration")
    print("-"*60)
    print("\nFor each database:")
    print("1. Open the database in Notion")
    print("2. Click '...' (three dots) in top right")
    print("3. Click 'Add connections'")
    print("4. Select 'Wellness Companion'")
    print("5. Click 'Confirm'\n")
    
    print("="*60)
    print("✅ SETUP COMPLETE!")
    print("="*60)
    print("\nYour Notion integration is configured!")
    print("\nNext steps:")
    print("1. Create the databases in Notion")
    print("2. Share them with your integration")
    print("3. Restart your agent")
    print("4. Try: 'Save this check-in to Notion'\n")
    
    print("For detailed instructions, see: backend/NOTION_INTEGRATION.md\n")


if __name__ == "__main__":
    try:
        setup_notion()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        print("Please check backend/NOTION_INTEGRATION.md for manual setup.")
