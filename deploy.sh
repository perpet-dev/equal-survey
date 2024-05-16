#!/bin/bash
# Enable error handling
set -e

# Variable settings
REGION="ap-northeast-2"
ACCOUNT_ID="868615245439"
REPO_NAME="equal/survey-service"
ECR="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
REGISTRY_REPO="${ECR}/${REPO_NAME}"

# Prompt the user for project version
read -p "Please enter the project version (default is 'latest'): " IMAGE_TAG
if [ -z "$IMAGE_TAG" ]; then
    IMAGE_TAG="latest"
fi

# Ensure Docker Buildx is available
if ! docker buildx version > /dev/null 2>&1; then
    echo "Docker Buildx is not available. Please install Docker Buildx and try again."
    exit 1
fi

# ECR login
PASSWORD=$(aws ecr get-login-password --region "$REGION")
echo "$PASSWORD" | docker login --username AWS --password-stdin "$ECR"

# Build and push the multi-platform Docker image with both tags
docker buildx build --platform linux/amd64,linux/arm64 --no-cache \
    -t "${REGISTRY_REPO}:latest" \
    -t "${REGISTRY_REPO}:${IMAGE_TAG}" \
    --push .
