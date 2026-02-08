import asyncio
import os
import sys
from chatbot import InvestmentChatbot
from dotenv import load_dotenv

# Ensure env is loaded
load_dotenv()

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def main():
    # Use a dummy thread_id
    tid = "1"
    
    chatbot = InvestmentChatbot(thread_id=tid)
    print("Initializing chatbot component...")
    try:
        await chatbot.initialize()
        print("Initialization complete.")
    except Exception as e:
        print(f"Initialization warning: {e}")
        # Even if some parts fail, we check if graph is built.
        if not hasattr(chatbot, 'graph'):
            print("Graph not built. Aborting.")
            return

    print(f"Sending TRADING message with thread_id={tid}...")
    try:
        # Intent 'trading'
        response = await chatbot.chat("Should I buy MTN?", thread_id=tid, intent="trading")
        print(f"SUCCESS: Received response: {response}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"FAILURE: Exception {e}")

if __name__ == "__main__":
    asyncio.run(main())
