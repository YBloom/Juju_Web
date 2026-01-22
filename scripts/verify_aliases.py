import sys
import os

# Ensure project root is in path
sys.path.append(os.getcwd())

try:
    from services.bot.handlers import extract_args
    from services.bot.commands import resolve_command
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def test_resolve(trigger, expected_canonical):
    result = resolve_command(trigger)
    status = "✅" if result == expected_canonical else "❌"
    print(f"{status} Trigger: '{trigger}' -> Expected: '{expected_canonical}' | Got: '{result}'")

def test_extract(msg, expected_cmd, expected_args, expected_mode):
    result = extract_args(msg)
    cmd_match = result["command"] == expected_cmd
    args_match = result["text_args"] == expected_args
    mode_match = result["mode_args"] == expected_mode
    
    status = "✅" if (cmd_match and args_match and mode_match) else "❌"
    print(f"{status} Msg: '{msg}'")
    if not (cmd_match and args_match and mode_match):
        print(f"   Expected: cmd='{expected_cmd}', args={expected_args}, mode={expected_mode}")
        print(f"   Got:      cmd='{result['command']}', args={result['text_args']}, mode={result['mode_args']}")

def run_tests():
    print("--- Testing Command Resolution ---")
    test_resolve("查剧", "/hlq")
    test_resolve("搜剧", "/hlq")
    test_resolve("/hlq", "/hlq")
    test_resolve("日历", "/date")
    test_resolve("关注", "/关注学生票")
    test_resolve("Unknown", None)
    test_resolve("/WEB", "/web") # Should handle case insensitivity via lower() in resolve_command?
    # resolve_command uses .lower() for comparison.
    
    print("\n--- Testing Argument Extraction ---")
    test_extract("查剧 连璧", "/hlq", ["连璧"], [])
    test_extract("搜演出 -all 魅影", "/hlq", ["魅影"], ["-all"])
    test_extract("关注 -E 连璧 2", "/关注学生票", ["连璧", "2"], ["-e"]) 
    test_extract("日历", "/date", [], [])
    test_extract("普通消息", "普通消息", [], [])

if __name__ == "__main__":
    run_tests()
