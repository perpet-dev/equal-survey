#!/bin/bash
# Enable error handling
set -e
# Variable settings
REGISTRY="dev.promptinsight.ai"
REPO_NAME="dev/survey-service"
REGISTRY_REPO="${REGISTRY}/${REPO_NAME}"

# Prompt the user for project version
read -p "Please enter the project version: " IMAGE_TAG
if [ -z "$IMAGE_TAG" ]; then
    echo "Error: No version input provided. Exiting..."
    exit 1
fi

# Build Docker image for multiple platforms with both tags and push
docker buildx build --platform linux/amd64,linux/arm64 --no-cache \
    -t ${REGISTRY_REPO}:${IMAGE_TAG} \
    -t ${REGISTRY_REPO}:latest \
    --push .

