.PHONY: \
	ui \
	db-init \
	test \
	test-unit \
	test-eval \
	demo-rag \
	demo-retrieval \
	load-chunks \
	db-init-docker \
	load-chunks-docker \
	docker-build \
	docker-up \
	docker-down \
	docker-logs \
	docker-restart \
	docker-run \
	docker-clean \
	clean



# ------------------------------------------------------------------
# Streamlit UI
# ------------------------------------------------------------------
ui:
	uv run streamlit run src/ui/streamlit_app.py



# ------------------------------------------------------------------
# Database schema initialisation (local)
# ------------------------------------------------------------------
db-init:
	uv run python -m src.database.db_init



# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------
test: test-unit test-eval


test-unit:
	uv run python -m unittest \
		tests.test_answer_generator \
		tests.test_chunk_documents \
		tests.test_db_schema \
		tests.test_demo_rag \
		tests.test_embed_chunks \
		tests.test_normalise_documents \
		tests.test_quality_check_chunks \
		tests.test_quality_check_normalised \
		tests.test_retrieval \
		tests.test_summarise_evaluation


test-eval:
	uv run python -m unittest \
		tests.test_evaluate_retrieval



# ------------------------------------------------------------------
# Data / evaluation scripts (local)
# ------------------------------------------------------------------
demo-rag:
	uv run python -m src.scripts.demo_rag


demo-retrieval:
	uv run python -m src.scripts.demo_retrieval


load-chunks:
	uv run python -m src.scripts.load_chunks_to_db \
		--chunks-dir data/processed/chunks \
		--embeddings-file data/processed/embeddings/embeddings.jsonl



# ------------------------------------------------------------------
# Database / Compose helpers (Docker)
# ------------------------------------------------------------------
db-init-docker:
	docker compose exec app python -m src.database.db_init


load-chunks-docker:
	docker compose exec app python -m src.scripts.load_chunks_to_db \
		--chunks-dir /app/data/processed/chunks \
		--embeddings-dir /app/data/processed/embeddings



# ------------------------------------------------------------------
# Docker / Compose (Milestone 5)
# ------------------------------------------------------------------
docker-build:
	docker build -t der-regcheck:latest .


docker-up:
	docker compose up -d


docker-down:
	docker compose down


docker-logs:
	docker compose logs -f


docker-restart:
	docker compose restart


# Legacy standalone container run (optional)
docker-run:
	docker run --rm \
		--env-file .env \
		-p 8501:8501 \
		der-regcheck:latest


docker-clean:
	docker compose down -v || true
	docker rmi der-regcheck:latest || true



# ------------------------------------------------------------------
# Cleanup (optional, adjust to your needs)
# ------------------------------------------------------------------
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + || true
	find . -type f -name "*.pyc" -delete || true
	find . -type f -name "*.pyo" -delete || true
	find . -type f -name "*.pyd" -delete || true
	find . -type f -name ".DS_Store" -delete || true
	find . -type f -name "*.orig" -delete || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + || true
	find . -type d -name "htmlcov" -exec rm -rf {} + || true