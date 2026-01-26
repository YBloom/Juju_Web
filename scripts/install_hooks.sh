#!/bin/bash

# Ensure we are in the project root
cd "$(dirname "$0")/.."

HOOK_PATH=".git/hooks/pre-commit"

echo "🔧 Installing Architecture Guardrails to $HOOK_PATH..."

# Create the hook file
cat > "$HOOK_PATH" << 'EOF'
#!/bin/bash
# MusicalBot Architecture Guardrails
# Automatically runs before every commit

echo "🛡️  Running Architecture Linter..."

# Verify we have the linter script
if [ ! -f "scripts/arch_lint.py" ]; then
    echo "⚠️  Warning: scripts/arch_lint.py not found. Skipping check."
    exit 0
fi

# Run the linter using the local python environment
# Try .venv first, then fallback to python3
if [ -f ".venv/bin/python" ]; then
    PYTHON_CMD=".venv/bin/python"
else
    PYTHON_CMD="python3"
fi

$PYTHON_CMD scripts/arch_lint.py

# Capture exit code
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "❌ Commit BLOCKED: Architecture violations found."
    echo "👉 Please fix the errors above or use 'git commit --no-verify' to bypass (Not Recommended)."
    exit 1
fi

echo "✅ Architecture Compliant."
exit 0
EOF

# Make it executable
chmod +x "$HOOK_PATH"

echo "✅ Git Hook installed successfully!"
echo "   Now 'scripts/arch_lint.py' will run automatically before every commit."
