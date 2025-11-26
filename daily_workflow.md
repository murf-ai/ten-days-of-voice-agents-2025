# Daily Git Workflow for Voice Agents Challenge

## Quick Commands Reference

### Start New Day
```bash
# Make script executable (first time only)
chmod +x create_daily_branch.sh

# Create new day branch
./create_daily_branch.sh 1 coffee-barista
./create_daily_branch.sh 2 customer-service
./create_daily_branch.sh 3 tutor-agent
# etc.
```

### Daily Development Cycle
```bash
# Work on your agent
git add .
git commit -m "Day X: Add feature Y"

# Push daily progress
git push origin day-XX-agent-name

# End of day - merge to development
git checkout development
git merge day-XX-agent-name
git push origin development
```

### View All Agents
```bash
# List all day branches
git branch | grep day-

# Switch between agents
git checkout day-01-coffee-barista
git checkout day-05-therapist-agent
```

### Create Agent Showcase
```bash
# Create showcase branch with all agents
git checkout development
git checkout -b agent-showcase

# Copy key files from each day
cp day-01/backend/src/agent.py showcase/day01_barista.py
cp day-02/backend/src/agent.py showcase/day02_service.py
# etc.
```

## Branch Protection Strategy

### Keep Each Day Isolated
- Each day gets its own branch
- Previous days remain untouched
- Easy to demo any specific agent

### Merge Strategy
```bash
# Option 1: Keep separate (recommended)
# Each day branch stays independent

# Option 2: Cumulative development
# Merge each day into development branch
git checkout development
git merge day-XX-agent-name
```

## Repository Structure After 10 Days
```
main/
├── development/
├── day-01-coffee-barista/
├── day-02-customer-service/
├── day-03-tutor-agent/
├── day-04-therapist-agent/
├── day-05-sales-agent/
├── day-06-tech-support/
├── day-07-fitness-coach/
├── day-08-travel-planner/
├── day-09-cooking-assistant/
├── day-10-final-showcase/
└── agent-showcase/
```

## Best Practices

1. **Commit Often**: Save progress multiple times per day
2. **Descriptive Messages**: Use clear commit messages
3. **Tag Releases**: Tag completed agents
4. **Document Everything**: Update README for each day
5. **Backup**: Push to GitHub regularly