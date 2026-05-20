@echo off
REM ============================================================
REM Gap Analysis Pipeline - Test Runner (Windows)
REM ============================================================
REM Gap Taxonomy: Orthogonal G1-G6
REM
REM Usage: run_test.bat
REM
REM Changes:
REM   - Simplified pipeline (4 phases instead of 6)
REM   - No aggregation phase
REM   - Each concern has exactly one topic
REM   - Orthogonal gap taxonomy (G1-G6)
REM
REM ============================================================

setlocal enabledelayedexpansion

set "GREEN=[92m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "RED=[91m"
set "NC=[0m"

cd /d "%~dp0"

echo %BLUE%============================================================%NC%
echo %BLUE%Gap Analysis Pipeline - Test Runner%NC%
echo %BLUE%Orthogonal G1-G6 Gap Taxonomy%NC%
echo %BLUE%============================================================%NC%

REM Check Python
echo.
echo %YELLOW%[1/5] Checking environment...%NC%
python -c "import sys; print(f'Python: {sys.version.split()[0]}')"
python -c "import aiohttp, tiktoken, yaml; print('Required packages: OK')" 2>nul || (
    echo %RED%Missing packages. Run: pip install -r requirements.txt%NC%
    exit /b 1
)

REM Phase 0: Data Preprocessing
echo.
echo %YELLOW%[2/5] Phase 0: Data Preprocessing...%NC%
python run_pipeline.py --phase 0 --test
if %ERRORLEVEL% NEQ 0 (
    echo %RED%X Phase 0 failed%NC%
    exit /b 1
)
echo %GREEN%V Phase 0 completed%NC%

REM Phase 1: Concern Extraction
echo.
echo %YELLOW%[3/5] Phase 1: Concern Extraction (70 concurrent)...%NC%
python run_pipeline.py --phase 1 --test --concurrent 70
if %ERRORLEVEL% NEQ 0 (
    echo %RED%X Phase 1 failed%NC%
    exit /b 1
)
echo %GREEN%V Phase 1 completed%NC%

REM Phase 2: Gap Auditing
echo.
echo %YELLOW%[4/5] Phase 2: Gap Auditing (G1-G6 taxonomy)...%NC%
python run_pipeline.py --phase 2 --test --concurrent 70
if %ERRORLEVEL% NEQ 0 (
    echo %RED%X Phase 2 failed%NC%
    exit /b 1
)
echo %GREEN%V Phase 2 completed%NC%

REM Phase 3: Result Mapping
echo.
echo %YELLOW%[5/5] Phase 3: Result Mapping...%NC%
python run_pipeline.py --phase 3 --test
if %ERRORLEVEL% NEQ 0 (
    echo %RED%X Phase 3 failed%NC%
    exit /b 1
)
echo %GREEN%V Phase 3 completed%NC%

echo.
echo %BLUE%============================================================%NC%
echo %GREEN%All phases completed successfully!%NC%
echo %BLUE%============================================================%NC%

echo.
echo Output files:
echo   - Preprocessed: 02_Outputs\preprocessed_threads\
echo   - Concerns: 02_Outputs\extracted_concerns\
echo   - Gaps: 02_Outputs\gap_results\
echo   - Reports: 02_Outputs\final_reports\

echo.
echo Gap Types:
echo   G1: POLICY_DETAIL_VAGUE
echo   G2: AI_FEATURE_UNADDRESSED
echo   G3: VULNERABLE_GROUP_NEGLECTED
echo   G4: JURISDICTION_UNCLEAR
echo   G5: EXPLICIT_POLICY_DISTRUST
echo   G6: POLICY_AWARENESS_DEFICIT

endlocal
