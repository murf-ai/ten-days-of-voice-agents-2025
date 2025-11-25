@echo off
echo Starting all Teach-the-Tutor agents...
echo.

REM Start greeter agent (Matthew voice)
start "Greeter Agent" cmd /k "set AGENT_MODE=greeter && uv run python src/agent.py dev"

REM Wait a bit
timeout /t 2 /nobreak > nul

REM Start learn agent (Matthew voice)
start "Learn Agent" cmd /k "set AGENT_MODE=learn && uv run python src/agent.py dev"

REM Wait a bit
timeout /t 2 /nobreak > nul

REM Start quiz agent (Alicia voice)
start "Quiz Agent" cmd /k "set AGENT_MODE=quiz && uv run python src/agent.py dev"

REM Wait a bit
timeout /t 2 /nobreak > nul

REM Start teach_back agent (Ken voice)
start "TeachBack Agent" cmd /k "set AGENT_MODE=teach_back && uv run python src/agent.py dev"

echo.
echo All agents started!
echo - Greeter (Matthew)
echo - Learn (Matthew)
echo - Quiz (Alicia)
echo - TeachBack (Ken)
echo.
echo Press any key to exit...
pause > nul
