#!/bin/bash

# Daily branch creation script for Voice Agents Challenge
# Usage: ./create_daily_branch.sh <day_number> <agent_description>

if [ $# -ne 2 ]; then
    echo "Usage: $0 <day_number> <agent_description>"
    echo "Example: $0 1 coffee-barista"
    exit 1
fi

DAY_NUM=$(printf "%02d" $1)
AGENT_DESC=$2
BRANCH_NAME="day-${DAY_NUM}-${AGENT_DESC}"

echo "Creating branch for Day ${DAY_NUM}: ${AGENT_DESC}"

# Ensure we're on development branch
git checkout development

# Pull latest changes
git pull origin development

# Create and switch to new daily branch
git checkout -b ${BRANCH_NAME}

# Create day-specific directory structure
mkdir -p "day-${DAY_NUM}"
mkdir -p "day-${DAY_NUM}/docs"
mkdir -p "day-${DAY_NUM}/assets"

# Create README for the day
cat > "day-${DAY_NUM}/README.md" << EOF
# Day ${DAY_NUM}: ${AGENT_DESC^}

## Objective
[Add today's objective here]

## Implementation
[Document your approach]

## Features
- [ ] Feature 1
- [ ] Feature 2
- [ ] Feature 3

## Testing
[How to test this agent]

## Demo
[Link to demo video/screenshots]
EOF

# Initial commit
git add .
git commit -m "Day ${DAY_NUM}: Initialize ${AGENT_DESC} agent structure"

echo "✅ Branch '${BRANCH_NAME}' created successfully!"
echo "📁 Day-specific folder created at day-${DAY_NUM}/"
echo "🚀 Ready to start building your ${AGENT_DESC} agent!"