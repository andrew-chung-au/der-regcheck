.PHONY: \
	ui \
	db-init \
	test \
	test-unit \
	test-eval \
	demo-rag \
	demo-retrieval \
	load-chunks \
	docker-build \
	docker-run \
	docker-clean \
	clean


# ------------------------------------------------------------------
# Streamlit UI
# ------------------------------------------------------------------
ui:
	uv run streamlit run src/ui/streamlit_app.py


# ------------------------------------------------------------------
# Database schema initialisation
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
# Data / evaluation scripts
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
# Docker (basic targets; adjust image name / args as needed)
# ------------------------------------------------------------------
docker-build:
	docker build -t der-regcheck:latest .

docker-run:
	docker run --rm \
		--env-file .env \
		-p 8501:8501 \
		der-regcheck:latest

docker-clean:
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