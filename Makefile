.PHONY: dev-backend 

dev-backend:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

##.\.venv\Scripts\Activate.ps1