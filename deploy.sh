#!/bin/bash

# Slack GPT Bot Deployment Script
# This script helps deploy the Slack bot using Docker Compose

set -e

echo "🚀 Starting Slack GPT Bot Deployment..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please copy env.example to .env and configure your environment variables."
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed!"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Error: Docker Compose is not installed!"
    echo "Please install Docker Compose first: https://docs.docker.com/compose/install/"
    exit 1
fi

# Create data directory if it doesn't exist
mkdir -p data

# Create thread_memory.json if it doesn't exist
if [ ! -f thread_memory.json ]; then
    echo "{}" > thread_memory.json
    echo "✅ Created thread_memory.json"
fi

# Build and start the containers
echo "🔨 Building Docker image..."
docker-compose build

echo "🚀 Starting services..."
docker-compose up -d

echo "⏳ Waiting for service to be ready..."
sleep 10

# Check if the service is running
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Deployment successful!"
    echo "🌐 Health check: http://localhost:8000/health"
    echo "📝 Logs: docker-compose logs -f"
    echo "🛑 Stop: docker-compose down"
else
    echo "❌ Deployment failed! Service is not responding."
    echo "📋 Check logs: docker-compose logs"
    exit 1
fi 