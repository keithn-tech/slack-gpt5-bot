.PHONY: help build run stop logs clean test deploy docker-build docker-run docker-stop docker-logs k8s-deploy k8s-delete

# Default target
help:
	@echo "Available commands:"
	@echo "  build        - Install dependencies"
	@echo "  run          - Run the application locally"
	@echo "  stop         - Stop the application"
	@echo "  logs         - View application logs"
	@echo "  clean        - Clean up generated files"
	@echo "  test         - Run tests"
	@echo "  deploy       - Deploy using Docker Compose"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run   - Run with Docker Compose"
	@echo "  docker-stop  - Stop Docker Compose"
	@echo "  docker-logs  - View Docker logs"
	@echo "  k8s-deploy   - Deploy to Kubernetes"
	@echo "  k8s-delete   - Delete Kubernetes deployment"

# Local development
build:
	pip3 install -r requirements.txt

run:
	python3 app.py

stop:
	pkill -f "python3 app.py" || true

logs:
	tail -f logs/app.log || echo "No log file found"

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .pytest_cache
	rm -rf .coverage

test:
	python3 -m pytest tests/ || echo "No tests found"

# Docker deployment
deploy: docker-build docker-run

docker-build:
	docker-compose build

docker-run:
	docker-compose up -d

docker-stop:
	docker-compose down

docker-logs:
	docker-compose logs -f

# Kubernetes deployment
k8s-deploy:
	kubectl apply -f kubernetes/secrets.yaml
	kubectl apply -f kubernetes/deployment.yaml
	kubectl apply -f kubernetes/ingress.yaml

k8s-delete:
	kubectl delete -f kubernetes/

# Development helpers
setup:
	cp env.example .env
	mkdir -p data
	echo "{}" > thread_memory.json
	@echo "Setup complete! Edit .env with your configuration."

check-env:
	@if [ ! -f .env ]; then \
		echo "❌ .env file not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@echo "✅ Environment file found"

health-check:
	curl -f http://localhost:8000/health || echo "Service not responding"

# Production helpers
backup:
	cp thread_memory.json thread_memory.json.backup.$$(date +%Y%m%d_%H%M%S)

restore:
	@echo "Available backups:"
	@ls -la thread_memory.json.backup.* 2>/dev/null || echo "No backups found" 