.PHONY: runtime docker-up docker-down docker-logs docker-status test run-api run-dashboard

runtime:
	bash scripts/prepare_docker_runtime.sh

docker-up: runtime
	docker compose up --build -d


docker-down:
	docker compose down


docker-logs:
	docker compose logs -f --tail=100


docker-status:
	docker compose ps


test:
	python -m pytest -q


run-api:
	python -m uvicorn app.main:app --reload


run-dashboard:
	python -m streamlit run app/dashboard.py
