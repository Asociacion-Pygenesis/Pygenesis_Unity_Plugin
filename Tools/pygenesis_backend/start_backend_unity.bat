@echo off
REM Arranque del backend para Unity (sin pause al final).
REM Variables opcionales: PYGENESIS_REASONING, OPENAI_API_KEY, PYGENESIS_OPENAI_* — ver README.md

cd /d "%~dp0"

call .venv\Scripts\activate.bat

python -u -m uvicorn main:app --host 127.0.0.1 --port 8765