#!/bin/bash
# Security Audit Script for Menu Green
# Kiểm tra các file có thể chứa thông tin nhạy cảm

echo "🔒 MENU GREEN - SECURITY AUDIT"
echo "================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check 1: .env in gitignore
echo "1. Checking .gitignore..."
if grep -q "^\.env$" .gitignore; then
    echo -e "${GREEN}✅ .env is in .gitignore${NC}"
else
    echo -e "${RED}❌ .env NOT in .gitignore!${NC}"
fi

# Check 2: .env not in git
echo ""
echo "2. Checking if .env is tracked by git..."
if git ls-files --error-unmatch .env >/dev/null 2>&1; then
    echo -e "${RED}❌ WARNING: .env is tracked by git!${NC}"
    echo "   Run: git rm --cached .env"
else
    echo -e "${GREEN}✅ .env is not tracked by git${NC}"
fi

# Check 3: .env in git history
echo ""
echo "3. Checking git history for .env..."
if git log --all --full-history -- .env 2>/dev/null | grep -q "commit"; then
    echo -e "${YELLOW}⚠️  .env mentioned in git history${NC}"
    echo "   (This may be from .gitignore commits, not actual .env)"
else
    echo -e "${GREEN}✅ No .env in git history${NC}"
fi

# Check 4: Search for API keys in code
echo ""
echo "4. Scanning for hardcoded API keys..."
FOUND_KEYS=0

# Check for Google API keys pattern
if grep -r "AIza[A-Za-z0-9_-]\{35\}" --exclude-dir={.git,.venv,venv,node_modules} --exclude={"*.md","*.log",".env*","security_audit.sh","SECURITY.md"} . 2>/dev/null; then
    echo -e "${RED}❌ Found potential Google API key in code!${NC}"
    FOUND_KEYS=1
fi

# Check for Supabase JWT tokens
if grep -r "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\." --exclude-dir={.git,.venv,venv,node_modules} --exclude={"*.md","*.log",".env*","security_audit.sh","SECURITY.md"} . 2>/dev/null; then
    echo -e "${RED}❌ Found potential Supabase JWT token in code!${NC}"
    FOUND_KEYS=1
fi

if [ $FOUND_KEYS -eq 0 ]; then
    echo -e "${GREEN}✅ No hardcoded API keys found${NC}"
fi

# Check 5: Sensitive files exist
echo ""
echo "5. Checking for sensitive files..."
SENSITIVE_FILES=(".env" "mem0_history.db")
for file in "${SENSITIVE_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${YELLOW}⚠️  $file exists (should be gitignored)${NC}"
    fi
done

# Check 6: .env.example exists
echo ""
echo "6. Checking for template files..."
if [ -f ".env.example" ] || [ -f ".env.template" ]; then
    echo -e "${GREEN}✅ Environment template file exists${NC}"
else
    echo -e "${RED}❌ No .env.example or .env.template found${NC}"
fi

# Check 7: Search in logs
echo ""
echo "7. Scanning log files..."
if [ -d "logs" ] || ls *.log >/dev/null 2>&1; then
    if grep -r "AIza\|eyJ\|password=\|api_key=" logs/ *.log 2>/dev/null; then
        echo -e "${RED}❌ Found potential secrets in log files!${NC}"
    else
        echo -e "${GREEN}✅ No secrets found in logs${NC}"
    fi
else
    echo -e "${GREEN}✅ No log files found${NC}"
fi

# Summary
echo ""
echo "================================"
echo "🔒 AUDIT COMPLETE"
echo "================================"
echo ""
echo "📝 Next steps:"
echo "   1. Review any warnings above"
echo "   2. Rotate exposed credentials"
echo "   3. Read SECURITY.md for best practices"
echo "   4. Run this script regularly"
echo ""
