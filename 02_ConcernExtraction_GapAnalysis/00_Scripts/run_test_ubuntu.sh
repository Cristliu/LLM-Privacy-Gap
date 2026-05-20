#!/bin/bash
# ============================================================
# Gap Analysis Pipeline - Test Runner (Ubuntu)
# ============================================================
# Gap Taxonomy: Orthogonal G1-G6
#
# Usage:
#   chmod +x run_test_ubuntu.sh
#   ./run_test_ubuntu.sh
#
# Changes:
#   - Simplified pipeline (4 phases instead of 6)
#   - No aggregation phase
#   - Each concern has exactly one topic
#   - Orthogonal gap taxonomy (G1-G6)
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
echo -e "${BLUE}Gap Analysis Pipeline - Test Runner${NC}"
echo -e "${BLUE}Orthogonal G1-G6 Gap Taxonomy${NC}"
echo -e "${BLUE}============================================================${NC}"

# Check environment
echo -e "\n${YELLOW}[1/5] Checking environment...${NC}"
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

# Phase 0: Data Preprocessing
echo -e "\n${YELLOW}[2/5] Phase 0: Data Preprocessing...${NC}"
PHASE_START=$(date +%s)
python3 run_pipeline.py --phase 0 --test
PHASE_END=$(date +%s)
echo -e "${GREEN}✓ Phase 0 completed in $((PHASE_END - PHASE_START))s${NC}"

# Phase 1: Concern Extraction
echo -e "\n${YELLOW}[3/5] Phase 1: Concern Extraction (70 concurrent)...${NC}"
PHASE_START=$(date +%s)
python3 run_pipeline.py --phase 1 --test --concurrent 70
PHASE_END=$(date +%s)
echo -e "${GREEN}✓ Phase 1 completed in $((PHASE_END - PHASE_START))s${NC}"

# Phase 2: Gap Auditing
echo -e "\n${YELLOW}[4/5] Phase 2: Gap Auditing (G1-G6 taxonomy)...${NC}"
PHASE_START=$(date +%s)
python3 run_pipeline.py --phase 2 --test --concurrent 70
PHASE_END=$(date +%s)
echo -e "${GREEN}✓ Phase 2 completed in $((PHASE_END - PHASE_START))s${NC}"

# Phase 3: Result Mapping
echo -e "\n${YELLOW}[5/5] Phase 3: Result Mapping...${NC}"
PHASE_START=$(date +%s)
python3 run_pipeline.py --phase 3 --test
PHASE_END=$(date +%s)
echo -e "${GREEN}✓ Phase 3 completed in $((PHASE_END - PHASE_START))s${NC}"

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo -e "\n${BLUE}============================================================${NC}"
echo -e "${GREEN}All phases completed successfully in ${DURATION}s!${NC}"
echo -e "${BLUE}============================================================${NC}"

echo -e "\nOutput files:"
echo "  - Preprocessed: 02_Outputs/preprocessed_threads/"
echo "  - Concerns: 02_Outputs/extracted_concerns/"
echo "  - Gaps: 02_Outputs/gap_results/"
echo "  - Reports: 02_Outputs/final_reports/"

echo -e "\n${YELLOW}Gap Type Summary:${NC}"
echo "  G1: POLICY_DETAIL_VAGUE"
echo "  G2: AI_FEATURE_UNADDRESSED"
echo "  G3: VULNERABLE_GROUP_NEGLECTED"
echo "  G4: JURISDICTION_UNCLEAR"
echo "  G5: EXPLICIT_POLICY_DISTRUST"
echo "  G6: POLICY_AWARENESS_DEFICIT"
