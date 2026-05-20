@echo off
REM ============================================================
REM Gap Analysis Pipeline - Full Run (Windows)
REM ============================================================
REM Gap Taxonomy: Orthogonal G1-G6
REM
REM This script runs the FULL pipeline (not test mode)
REM Processes ALL threads for ALL providers
REM
REM Usage: run_full.bat
REM
REM Estimated time: ~30-60 minutes (70 concurrent API requests)
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
echo %BLUE%Gap Analysis Pipeline - FULL RUN%NC%
echo %BLUE%Orthogonal G1-G6 Gap Taxonomy%NC%
echo %BLUE%============================================================%NC%
echo %YELLOW%WARNING: This will process ALL data and may take 30-60 min.%NC%
echo %YELLOW%Press Ctrl+C within 5 seconds to cancel...%NC%
timeout /t 5 /nobreak >nul

REM Check environment
echo.
echo %YELLOW%Checking environment...%NC%
python -c "import sys; print(f'Python: {sys.version.split()[0]}')"
python -c "import aiohttp, tiktoken, yaml; print('Required packages: OK')" 2>nul || (
    echo %RED%Missing packages. Run: pip install -r requirements.txt%NC%
    exit /b 1
)

set START_TIME=%TIME%
echo.
echo %YELLOW%Starting full pipeline at %START_TIME%...%NC%

REM Phase 0: Data Preprocessing
echo.
echo %BLUE%[Phase 0] Data Preprocessing%NC%
python run_pipeline.py --phase 0
if %ERRORLEVEL% NEQ 0 exit /b 1

REM Phase 1: Concern Extraction (per provider)
echo.
echo %BLUE%[Phase 1] Concern Extraction (70 concurrent)%NC%
for %%p in (chatgpt claude gemini grok deepseek) do (
    echo.
    echo %YELLOW%  Processing %%p...%NC%
    python run_pipeline.py --phase 1 --provider %%p --concurrent 70
    if %ERRORLEVEL% NEQ 0 exit /b 1
)

REM Phase 2: Gap Auditing (per provider)
echo.
echo %BLUE%[Phase 2] Gap Auditing - G1-G6 Taxonomy (70 concurrent)%NC%
for %%p in (chatgpt claude gemini grok deepseek) do (
    echo.
    echo %YELLOW%  Auditing %%p...%NC%
    python run_pipeline.py --phase 2 --provider %%p --concurrent 70
    if %ERRORLEVEL% NEQ 0 exit /b 1
)

REM Phase 3: Result Mapping
echo.
echo %BLUE%[Phase 3] Result Mapping%NC%
python run_pipeline.py --phase 3
if %ERRORLEVEL% NEQ 0 exit /b 1

set END_TIME=%TIME%

echo.
echo %GREEN%============================================================%NC%
echo %GREEN%Full pipeline completed!%NC%
echo %GREEN%Started: %START_TIME%  Ended: %END_TIME%%NC%
echo %GREEN%============================================================%NC%

echo.
echo Final reports saved to: 02_Outputs\final_reports\

echo.
echo   Gap Types:
echo   Coverage Gaps (G1-G4):
echo     G1: POLICY_DETAIL_VAGUE
echo     G2: AI_FEATURE_UNADDRESSED
echo     G3: VULNERABLE_GROUP_NEGLECTED
echo     G4: JURISDICTION_UNCLEAR
echo   Perception Gaps (G5-G6):
echo     G5: EXPLICIT_POLICY_DISTRUST (requires policy coverage)
echo     G6: POLICY_AWARENESS_DEFICIT (requires policy coverage)

endlocal
