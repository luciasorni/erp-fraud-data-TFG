#!/usr/bin/env bash
set -euo pipefail

AWS_PROFILE="${AWS_PROFILE:-tfg-fraud-dev}"
AWS_REGION="${AWS_REGION:-eu-west-1}"
AWS_ACCOUNT_ID="$(aws sts get-caller-identity --profile "$AWS_PROFILE" --query Account --output text)"
ECR_REPOSITORY="tfg-fraud-dev-ecr-pipeline"
IMAGE_LOCAL="erp-fraud-pipeline:rf14c14"
GIT_SHA="$(git rev-parse --short HEAD)"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}"

echo "==> Building image"
docker build -t "${IMAGE_LOCAL}" .

echo "==> Logging in to ECR"
aws ecr get-login-password --region "${AWS_REGION}" --profile "${AWS_PROFILE}" | \
  docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "==> Tagging image"
docker tag "${IMAGE_LOCAL}" "${ECR_URI}:${GIT_SHA}"
docker tag "${IMAGE_LOCAL}" "${ECR_URI}:latest"

echo "==> Pushing image tags"
docker push "${ECR_URI}:${GIT_SHA}"
docker push "${ECR_URI}:latest"

echo "==> Done"
echo "Pushed:"
echo "  ${ECR_URI}:${GIT_SHA}"
echo "  ${ECR_URI}:latest"