#!/bin/bash
# =============================================================================
# Batch Process Split Concerns for ChatGPT
# =============================================================================
# This script demonstrates the workflow for processing split concerns files.
# Run each part sequentially (or in separate terminals for parallel execution).
#
# Usage:
#   1. First split the concerns file:
#      python split_concerns.py --input ../02_Outputs/extracted_concerns/concerns_chatgpt_20260202_122720.json --parts 4
#
#   2. Run this script OR run parts manually:
#      bash run_chatgpt_parts.sh
#
#   3. After all parts complete, merge:
#      python merge_gap_results.py --provider chatgpt --parts 4
# =============================================================================

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONCERNS_DIR="${SCRIPT_DIR}/../02_Outputs/extracted_concerns"

echo "=============================================="
echo "ChatGPT Split Processing Workflow"
echo "=============================================="

# Check if part files exist
PART_FILES=$(ls ${CONCERNS_DIR}/concerns_chatgpt_*_part*.json 2>/dev/null | wc -l)

if [ "$PART_FILES" -eq 0 ]; then
    echo ""
    echo "⚠️  No part files found. Please split the concerns file first:"
    echo ""
    echo "   python split_concerns.py \\"
    echo "       --input ../02_Outputs/extracted_concerns/concerns_chatgpt_20260202_122720.json \\"
    echo "       --parts 4"
    echo ""
    exit 1
fi

echo ""
echo "Found ${PART_FILES} part files to process."
echo ""

# List part files
for PART_FILE in ${CONCERNS_DIR}/concerns_chatgpt_*_part*.json; do
    echo "  - $(basename ${PART_FILE})"
done

echo ""
echo "=============================================="
echo "Processing Options:"
echo "=============================================="
echo ""
echo "Option 1: Run sequentially (safer, slower)"
echo "  for i in 1 2 3 4; do"
echo "    python 02_gap_auditor.py --provider chatgpt --input ../02_Outputs/extracted_concerns/concerns_chatgpt_*_part\${i}.json"
echo "  done"
echo ""
echo "Option 2: Run in parallel (separate terminals)"
echo "  Terminal 1: python 02_gap_auditor.py --provider chatgpt --input ../02_Outputs/extracted_concerns/concerns_chatgpt_*_part1.json"
echo "  Terminal 2: python 02_gap_auditor.py --provider chatgpt --input ../02_Outputs/extracted_concerns/concerns_chatgpt_*_part2.json"
echo "  Terminal 3: python 02_gap_auditor.py --provider chatgpt --input ../02_Outputs/extracted_concerns/concerns_chatgpt_*_part3.json"
echo "  Terminal 4: python 02_gap_auditor.py --provider chatgpt --input ../02_Outputs/extracted_concerns/concerns_chatgpt_*_part4.json"
echo ""
echo "Option 3: Run with reduced concurrency (balance)"
echo "  for i in 1 2 3 4; do"
echo "    python 02_gap_auditor.py --provider chatgpt --concurrent 30 --input ../02_Outputs/extracted_concerns/concerns_chatgpt_*_part\${i}.json"
echo "  done"
echo ""

read -p "Do you want to run sequentially now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Starting sequential processing..."
    echo ""
    
    for PART_FILE in ${CONCERNS_DIR}/concerns_chatgpt_*_part*.json; do
        echo "=============================================="
        echo "Processing: $(basename ${PART_FILE})"
        echo "=============================================="
        python "${SCRIPT_DIR}/02_gap_auditor.py" --provider chatgpt --input "${PART_FILE}"
        echo ""
    done
    
    echo "=============================================="
    echo "All parts processed. Now merging..."
    echo "=============================================="
    python "${SCRIPT_DIR}/merge_gap_results.py" --provider chatgpt --parts ${PART_FILES}
    
    echo ""
    echo "✅ Complete! Check 02_Outputs/gap_results/ for the merged file."
else
    echo ""
    echo "Exiting. Run parts manually using the commands above."
fi
