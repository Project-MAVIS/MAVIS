.PHONY: help run-gradio run install sync clean format lint test

# Default target
help:
	@echo "Available commands:"
	@echo "  make run-gradio    - Run the Gradio app"
	@echo "  make run           - Alias for run-gradio"
	@echo "  make install       - Install all dependencies (including dev and test)"
	@echo "  make sync          - Sync dependencies with pyproject.toml"
	@echo "  make format        - Format code with black"
	@echo "  make lint          - Run code quality checks"
	@echo "  make test          - Run tests with pytest"
	@echo "  make clean         - Clean temporary files and caches"

# Run the Gradio app
run-gradio:
	@echo "Starting Gradio app..."
	uv run python -m mavis.cmd.ui

# Alias for run-gradio
run: run-gradio

# Install all dependencies
install:
	@echo "Installing dependencies..."
	uv sync --all-groups

# Sync dependencies
sync:
	@echo "Syncing dependencies..."
	uv sync --all-groups

# Format code with black
format:
	@echo "Formatting code with black..."
	uv run black mavis/

# Run linting
lint:
	@echo "Running code quality checks..."
	uv run black --check mavis/

# Run tests
test:
	@echo "Running tests..."
	uv run pytest

# Clean temporary files
clean:
	@echo "Cleaning temporary files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleanup complete!"

