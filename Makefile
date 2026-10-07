.PHONY: run test reset lint
run:
	uvicorn app.main:app --reload
test:
	pytest
reset:
	python scripts/reset_demo.py
lint:
	ruff check .
