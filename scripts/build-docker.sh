#!/bin/bash
set -e

echo "FFAStrans Linux Mimo - Docker Build Script"
echo "==========================================="

VERSION=${1:-"latest"}
IMAGE_NAME="ffastrans-linux-mimo"

echo "Building Docker image: $IMAGE_NAME:$VERSION"
docker build -t "$IMAGE_NAME:$VERSION" .

echo ""
echo "Image built successfully!"
echo "Run with: docker run -d -p 8080:8080 $IMAGE_NAME:$VERSION"
echo "Or use docker-compose: docker-compose up -d"
