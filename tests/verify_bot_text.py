import sys
import os
import asyncio

# Add project root to path
sys.path.append(os.getcwd())

from services.bot.handlers import BotHandler, MODE_DESCRIPTIONS

async def verify():
    print("--- Verifying MODE_DESCRIPTIONS ---")
    expected_modes = {
        0: "关闭",
        1: "开票",
        2: "开票+补票",
        3: "开票+补票+回流",
        4: "开票+补票+回流+票减",
        5: "全部"
    }
    for mode, desc in expected_modes.items():
        actual = MODE_DESCRIPTIONS.get(mode)
        if actual == desc:
            print(f"✅ Mode {mode}: {actual}")
        else:
            print(f"❌ Mode {mode}: Expected '{desc}', got '{actual}'")

    print("\n--- Verifying Help Text Logic (Mock) ---")
    # We can't easily mock the whole DB session here without setting up a test DB context, 
    # but we can verify the text generation functions if we copy the string logic or just inspect the file.
    # Since we modified _handle_set_notify_level, let's look at the static text part of it (if level is None).
    
    handler = BotHandler(None)
    help_text = await handler._handle_set_notify_level("mock_user", None)
    
    print("Notification Help Text Preview:")
    print(help_text)
    
    if "模式说明" in help_text and "模式2（开票+补票）" in help_text:
        print("\n✅ Help text verification PASSED")
    else:
        print("\n❌ Help text verification FAILED")

if __name__ == "__main__":
    asyncio.run(verify())
