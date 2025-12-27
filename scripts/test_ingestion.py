#!/usr/bin/env python3
"""
Test script for ingestion workflow with LangChain caching.
Run this to debug ingestion phases without the UI.

Usage:
    python scripts/test_ingestion.py [sample_requirements.txt]
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

# =============================================================================
# Setup LangChain Cache (SQLite-based for persistence)
# =============================================================================

from langchain_community.cache import SQLiteCache
from langchain_core.globals import set_llm_cache

# Create cache directory if not exists
cache_dir = Path(__file__).parent.parent / ".cache"
cache_dir.mkdir(exist_ok=True)
cache_file = cache_dir / "langchain_cache.db"

# Set up SQLite cache
set_llm_cache(SQLiteCache(database_path=str(cache_file)))
print(f"✅ LangChain cache enabled: {cache_file}")

# =============================================================================
# Test Ingestion
# =============================================================================

async def test_ingestion(text_content: str):
    """Run ingestion workflow and print progress."""
    from api.ingestion import run_ingestion_workflow, IngestionSession
    
    # Create a mock session
    session = IngestionSession(id="test-session")
    
    print("\n" + "="*60)
    print("Starting Ingestion Test")
    print("="*60 + "\n")
    
    event_count = 0
    
    async for event in run_ingestion_workflow(session, text_content):
        event_count += 1
        phase = event.phase.value
        progress = event.progress
        message = event.message
        
        # Format output
        bar_length = 30
        filled = int(bar_length * progress / 100)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        print(f"[{progress:3d}%] [{bar}] {phase.upper()}")
        print(f"       {message}")
        
        if event.data:
            if "type" in event.data:
                obj = event.data.get("object", {})
                print(f"       → Created: {event.data['type']} - {obj.get('name', obj.get('id', ''))}")
            elif "summary" in event.data:
                print(f"\n📊 Summary:")
                for key, value in event.data["summary"].items():
                    print(f"   - {key}: {value}")
        
        print()
        
        # Check for errors
        if phase == "error":
            print(f"❌ ERROR: {message}")
            break
    
    print("="*60)
    print(f"✅ Ingestion completed with {event_count} events")
    print("="*60)


async def main():
    # Sample requirements for testing
    sample_text = """
    # E-Commerce System Requirements
    
    ## User Stories
    
    1. As a customer, I want to browse products so that I can find items to purchase.
    2. As a customer, I want to add items to my cart so that I can purchase multiple items.
    3. As a customer, I want to place an order so that I can receive the products.
    4. As a customer, I want to view my order status so that I can track my delivery.
    5. As a customer, I want to cancel my order so that I can get a refund if I change my mind.
    
    6. As a store owner, I want to manage product inventory so that I can keep stock levels accurate.
    7. As a store owner, I want to process refunds when orders are cancelled.
    
    8. As a delivery person, I want to update delivery status so that customers can track their orders.
    """
    
    # Check if a file path was provided
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                sample_text = f.read()
            print(f"📄 Using requirements from: {file_path}")
        else:
            print(f"⚠️ File not found: {file_path}, using sample requirements")
    else:
        print("📄 Using sample requirements (pass a file path to use custom requirements)")
    
    await test_ingestion(sample_text)


if __name__ == "__main__":
    asyncio.run(main())

