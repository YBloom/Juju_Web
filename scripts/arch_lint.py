import ast
import os
import sys

# Rules Configuration
VIOLATIONS = []

def check_bot_imports(file_path):
    """Rule: main_bot_v2.py should not import crawler components."""
    with open(file_path, "r") as f:
        tree = ast.parse(f.read())
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
            module = node.module if isinstance(node, ast.ImportFrom) else None
            names = [n.name for n in node.names]
            
            # Check logic
            if module and "hulaquan.crawler" in module:
                VIOLATIONS.append(f"[CRITICAL] Bot ({file_path}) imports Crawler: {module}")

def check_engine_dicts(file_path):
    """Rule: notification/engine.py should not construct loose dicts for payloads."""
    with open(file_path, "r") as f:
        content = f.read()
        
    # Heuristic: Check for manual dict construction pattern near "messages.append"
    # This is a simple text check; AST would be better but more complex for this specific pattern
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if "messages.append({" in line:
             VIOLATIONS.append(f"[WARNING] Engine ({file_path}:{i+1}) detects manual Dict construction. Use Pydantic model_dump()!")

def main():
    print("🛡️  Running Architecture Guardrails...")
    
    # 1. Check Bot Isolation
    bot_file = "main_bot_v2.py"
    if os.path.exists(bot_file):
        check_bot_imports(bot_file)
        
    # 2. Check Engine Schemas
    engine_file = "services/notification/engine.py"
    if os.path.exists(engine_file):
        check_engine_dicts(engine_file)
        
    # Report
    if VIOLATIONS:
        print("\n❌ Architecture Violations Found:")
        for v in VIOLATIONS:
            print(v)
        sys.exit(1)
    else:
        print("\n✅ Architecture Compliant.")
        sys.exit(0)

if __name__ == "__main__":
    main()
