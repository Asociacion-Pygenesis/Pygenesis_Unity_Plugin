@echo off
REM Opcional: set PYGENESIS_REASONING=rules|llm|hybrid y OPENAI_API_KEY — ver README.md

cd /d %~dp0
call .venv\Scripts\activate
uvicorn main:app --host 127.0.0.1 --port 8765
pause