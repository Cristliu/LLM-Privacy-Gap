#!/bin/bash
# ============================================================
# Gap Analysis Pipeline - Full Run (Ubuntu)
# ============================================================
# Gap Taxonomy: Orthogonal G1-G6
#
# This script runs the FULL pipeline (not test mode)
# Processes ALL threads for ALL providers
#
# Usage:
#   chmod +x run_full_ubuntu.sh
#   ./run_full_ubuntu.sh
#
# Estimated time: ~30-60 minutes (70 concurrent API requests)
# (Simplified pipeline)
#
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}Gap Analysis Pipeline - FULL RUN${NC}"
echo -e "${BLUE}Orthogonal G1-G6 Gap Taxonomy${NC}"
echo -e "${BLUE}============================================================${NC}"
echo -e "${YELLOW}WARNING: This will process ALL data and may take 30-60 min.${NC}"
echo -e "${YELLOW}Press Ctrl+C within 5 seconds to cancel...${NC}"
sleep 5

# Check environment
echo -e "\n${YELLOW}Checking environment...${NC}"
python3 -c "
import sys
print(f'Python: {sys.version.split()[0]}')
try:
    import aiohttp, tiktoken, yaml
    print('✓ Required packages installed')
except ImportError as e:
    print(f'⚠ Missing package: {e}')
    sys.exit(1)
"

START_TIME=$(date +%s)
echo -e "\n${YELLOW}Starting full pipeline at $(date '+%Y-%m-%d %H:%M:%S')...${NC}"

# Provider list and total count
PROVIDERS=(chatgpt claude gemini grok deepseek)
TOTAL_PROVIDERS=${#PROVIDERS[@]}
TOTAL_STEPS=$((TOTAL_PROVIDERS * 2))  # Phase 1 + Phase 2

# Function to format duration
format_duration() {
    local seconds=$1
    local hours=$((seconds / 3600))
    local minutes=$(((seconds % 3600) / 60))
    local secs=$((seconds % 60))
    if [ $hours -gt 0 ]; then
        echo "${hours}h ${minutes}m ${secs}s"
    elif [ $minutes -gt 0 ]; then
        echo "${minutes}m ${secs}s"
    else
        echo "${secs}s"
    fi
}

# Function to show progress with ETA
show_progress() {
    local current_step=$1
    local step_start=$2
    local phase_name=$3
    
    local now=$(date +%s)
    local elapsed=$((now - START_TIME))
    local step_elapsed=$((now - step_start))
    
    # Calculate ETA based on average time per step
    if [ $current_step -gt 0 ]; then
        local avg_per_step=$((elapsed / current_step))
        local remaining_steps=$((TOTAL_STEPS - current_step))
        local eta=$((avg_per_step * remaining_steps))
        
        echo -e "${BLUE}  ⏱  Progress: ${current_step}/${TOTAL_STEPS} steps | Elapsed: $(format_duration $elapsed) | ETA: $(format_duration $eta)${NC}"
    fi
}

# Phase 0: Data Preprocessing
echo -e "\n${BLUE}[Phase 0] Data Preprocessing${NC}"
PHASE0_START=$(date +%s)
echo -e "${YELLOW}Started at: $(date '+%H:%M:%S')${NC}"
python3 run_pipeline.py --phase 0
PHASE0_END=$(date +%s)
PHASE0_DURATION=$((PHASE0_END - PHASE0_START))
echo -e "${GREEN}Phase 0 completed in $(format_duration $PHASE0_DURATION)${NC}"

# Phase 1: Concern Extraction (per provider for better progress tracking)
echo -e "\n${BLUE}[Phase 1] Concern Extraction (70 concurrent)${NC}"
PHASE1_START=$(date +%s)
echo -e "${YELLOW}Started at: $(date '+%H:%M:%S')${NC}"

STEP_COUNT=0
for provider in "${PROVIDERS[@]}"; do
    PROVIDER_START=$(date +%s)
    echo -e "\n${YELLOW}  Processing $provider...${NC}"
    python3 run_pipeline.py --phase 1 --provider $provider --concurrent 70
    
    STEP_COUNT=$((STEP_COUNT + 1))
    PROVIDER_END=$(date +%s)
    PROVIDER_DURATION=$((PROVIDER_END - PROVIDER_START))
    echo -e "${GREEN}  ✓ $provider completed in $(format_duration $PROVIDER_DURATION)${NC}"
    show_progress $STEP_COUNT $PROVIDER_START "Phase 1"
done

PHASE1_END=$(date +%s)
PHASE1_DURATION=$((PHASE1_END - PHASE1_START))
echo -e "\n${GREEN}Phase 1 completed in $(format_duration $PHASE1_DURATION)${NC}"

# Phase 2: Gap Auditing (per provider)
echo -e "\n${BLUE}[Phase 2] Gap Auditing - G1-G6 Taxonomy (70 concurrent)${NC}"
PHASE2_START=$(date +%s)
echo -e "${YELLOW}Started at: $(date '+%H:%M:%S')${NC}"

for provider in "${PROVIDERS[@]}"; do
    PROVIDER_START=$(date +%s)
    echo -e "\n${YELLOW}  Auditing $provider...${NC}"
    python3 run_pipeline.py --phase 2 --provider $provider --concurrent 70
    
    STEP_COUNT=$((STEP_COUNT + 1))
    PROVIDER_END=$(date +%s)
    PROVIDER_DURATION=$((PROVIDER_END - PROVIDER_START))
    echo -e "${GREEN}  ✓ $provider completed in $(format_duration $PROVIDER_DURATION)${NC}"
    show_progress $STEP_COUNT $PROVIDER_START "Phase 2"
done

PHASE2_END=$(date +%s)
PHASE2_DURATION=$((PHASE2_END - PHASE2_START))
echo -e "\n${GREEN}Phase 2 completed in $(format_duration $PHASE2_DURATION)${NC}"

# Phase 3: Result Mapping
echo -e "\n${BLUE}[Phase 3] Result Mapping${NC}"
PHASE3_START=$(date +%s)
echo -e "${YELLOW}Started at: $(date '+%H:%M:%S')${NC}"
python3 run_pipeline.py --phase 3
PHASE3_END=$(date +%s)
PHASE3_DURATION=$((PHASE3_END - PHASE3_START))
echo -e "${GREEN}Phase 3 completed in $(format_duration $PHASE3_DURATION)${NC}"

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo -e "\n${GREEN}============================================================${NC}"
echo -e "${GREEN}Full pipeline completed in $(format_duration $DURATION)${NC}"
echo -e "${GREEN}============================================================${NC}"

# Show detailed timing summary
echo -e "\n${BLUE}Timing Summary:${NC}"
echo -e "  Phase 0 (Preprocessing):     $(format_duration $PHASE0_DURATION)"
echo -e "  Phase 1 (Concern Extraction): $(format_duration $PHASE1_DURATION)"
echo -e "  Phase 2 (Gap Auditing):       $(format_duration $PHASE2_DURATION)"
echo -e "  Phase 3 (Result Mapping):     $(format_duration $PHASE3_DURATION)"
echo -e "  ────────────────────────────"
echo -e "  Total:                        $(format_duration $DURATION)"

echo -e "\nFinal reports saved to: 02_Outputs/final_reports/"
echo -e "\n${YELLOW}Gap Types:${NC}"
echo "  Coverage Gaps (G1-G4):"
echo "    G1: POLICY_DETAIL_VAGUE"
echo "    G2: AI_FEATURE_UNADDRESSED"
echo "    G3: VULNERABLE_GROUP_NEGLECTED"
echo "    G4: JURISDICTION_UNCLEAR"
echo "  Perception Gaps (G5-G6):"
echo "    G5: EXPLICIT_POLICY_DISTRUST (requires policy coverage)"
echo "    G6: POLICY_AWARENESS_DEFICIT (requires policy coverage)"
