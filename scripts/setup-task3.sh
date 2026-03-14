#!/bin/bash
# Task 3: Set up Qwen Code API and Backend for benchmark
# Run this script on your VM via SSH

set -e

echo "=== Task 3 Setup Script ==="
echo "Run these commands on your VM: ssh nurikos@10.93.24.193"
echo ""

# Step 1: Install pnpm (if not installed)
echo "Step 1: Install pnpm"
if ! command -v pnpm &> /dev/null; then
    curl -fsSL https://get.pnpm.io/install.sh | sh -
    export PNPM_HOME="$HOME/.local/share/pnpm"
    export PATH="$PNPM_HOME:$PATH"
    echo "pnpm installed"
else
    echo "pnpm already installed"
fi
echo ""

# Step 2: Install Qwen Code CLI
echo "Step 2: Install Qwen Code CLI"
pnpm add -g @qwen-code/qwen-code
echo ""

# Step 3: Authenticate with Qwen
echo "Step 3: Authenticate with Qwen"
echo "Run: qwen"
echo "Then type: /auth"
echo "Open the browser link and complete OAuth"
echo "Then type: /quit"
echo ""
read -p "Press Enter after authentication is complete..."

# Step 4: Get API key
echo "Step 4: Get your API key"
API_KEY=$(cat ~/.qwen/oauth_creds.json | jq -r .api_key)
echo "Your API key: $API_KEY"
echo ""

# Step 5: Set up qwen-code-oai-proxy
echo "Step 5: Set up qwen-code-oai-proxy"
if [ ! -d ~/qwen-code-oai-proxy ]; then
    git clone https://github.com/inno-se-toolkit/qwen-code-oai-proxy ~/qwen-code-oai-proxy
fi
cd ~/qwen-code-oai-proxy
cp .env.example .env
sed -i "s/QWEN_API_KEY=.*/QWEN_API_KEY=$API_KEY/" .env
echo "Proxy configured with API key"
echo ""

# Step 6: Start the proxy
echo "Step 6: Start the proxy"
docker compose up --build -d
echo "Waiting for proxy to start..."
sleep 5
echo ""

# Step 7: Test the proxy
echo "Step 7: Test the proxy"
HOST_PORT=$(grep HOST_PORT .env | cut -d'=' -f2)
echo "Testing API at http://localhost:$HOST_PORT"
curl -s http://localhost:$HOST_PORT/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{"model":"qwen3-coder-plus","messages":[{"role":"user","content":"Hello"}]}' | jq .
echo ""

# Step 8: Start backend services
echo "Step 8: Start backend services"
cd ~/se-toolkit-lab-6
docker compose --env-file .env.docker.secret up --build -d
echo "Waiting for services to start..."
sleep 10
echo ""

# Step 9: Verify backend
echo "Step 9: Verify backend"
LMS_API_KEY=$(grep LMS_API_KEY .env.docker.secret | cut -d'=' -f2)
curl -s http://localhost:42002/items/ -H "Authorization: Bearer $LMS_API_KEY" | head -c 100
echo ""
echo ""

# Step 10: Show configuration for local machine
echo "=== Configuration for local machine ==="
echo "On your LOCAL machine, update .env.agent.secret:"
echo "  LLM_API_KEY=$API_KEY"
echo "  LLM_API_BASE=http://10.93.24.193:$HOST_PORT/v1"
echo "  LLM_MODEL=qwen3-coder-plus"
echo ""
echo "Ensure .env.docker.secret has:"
echo "  LMS_API_KEY=$LMS_API_KEY"
echo ""
echo "=== Setup Complete ==="
echo "Now run on your local machine:"
echo "  uv run run_eval.py"
