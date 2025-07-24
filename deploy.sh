

#!/bin/bash

# このスクリプトは、バックエンドとフロントエンドのスタックを順番にデプロイします。
# 実行する前に、AWS CLIが設定済みで、Dockerが実行中であることを確認してください。

# --- グローバル設定 ---
AWS_REGION="ap-northeast-1"

# --- フロントエンド設定 ---
FRONTEND_ECR_REPO_NAME="chainlit-frontend"
FRONTEND_IMAGE_TAG="latest"
FRONTEND_STACK_NAME="chainlit-frontend-stack"

# --- バックエンド設定 ---
BACKEND_STACK_NAME="chainlit-backend-stack"

# エラーが発生した場合はスクリプトを終了する
set -e

# --- Step 1: フロントエンドのDockerイメージをビルドしてECRにプッシュ ---
echo "--- フロントエンドの準備を開始します ---"

# フロントエンドのディレクトリに移動
cd frontend

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
FRONTEND_ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${FRONTEND_ECR_REPO_NAME}"

echo "ECRリポジトリを作成または確認しています..."
aws ecr describe-repositories --repository-names "${FRONTEND_ECR_REPO_NAME}" --region "${AWS_REGION}" > /dev/null 2>&1 || \
    aws ecr create-repository --repository-name "${FRONTEND_ECR_REPO_NAME}" --region "${AWS_REGION}" > /dev/null

echo "ECRにログインしています..."
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${FRONTEND_ECR_URI}"

echo "Dockerイメージをビルドしています..."
docker build -t "${FRONTEND_ECR_REPO_NAME}:${FRONTEND_IMAGE_TAG}" .

echo "イメージをECRにプッシュしています..."
docker tag "${FRONTEND_ECR_REPO_NAME}:${FRONTEND_IMAGE_TAG}" "${FRONTEND_ECR_URI}:${FRONTEND_IMAGE_TAG}"
docker push "${FRONTEND_ECR_URI}:${FRONTEND_IMAGE_TAG}"

# ルートディレクトリに戻る
cd ..
echo "--- フロントエンドの準備が完了しました ---"


# --- Step 2: バックエンドスタックのデプロイ ---
echo "\n--- バックエンドスタックのデプロイを開始します ---"

# バックエンドのディレクトリに移動
cd backend

cp ../lambda_requirements.txt index_lambda/requirements.txt
cp ../lambda_requirements.txt query_lambda/requirements.txt

sam build --use-container
sam deploy \
    --stack-name "${BACKEND_STACK_NAME}" \
    --region "${AWS_REGION}" \
    --capabilities CAPABILITY_IAM \
    --resolve-s3 \
    --no-confirm-changeset

# バックエンドのAPI URLを取得
API_URL=$(aws cloudformation describe-stacks --stack-name "${BACKEND_STACK_NAME}" --region "${AWS_REGION}" --query "Stacks[0].Outputs[?OutputKey=='QueryApiEndpoint'].OutputValue" --output text)

if [ -z "$API_URL" ]; then
    echo "エラー: バックエンドのAPI URLを取得できませんでした。"
    exit 1
fi

# ルートディレクトリに戻る
cd ..
echo "--- バックエンドのデプロイが完了しました --- API URL: ${API_URL}"


# --- Step 3: フロントエンドスタックのデプロイ ---
echo "\n--- フロントエンドスタックのデプロイを開始します ---"

# フロントエンドのディレクトリに移動
cd frontend

sam build --use-container
sam deploy \
    --stack-name "${FRONTEND_STACK_NAME}" \
    --region "${AWS_REGION}" \
    --parameter-overrides "ApiUrl=${API_URL}" "FrontendImageUri=${FRONTEND_ECR_URI}:${FRONTEND_IMAGE_TAG}" \
    --capabilities CAPABILITY_IAM \
    --resolve-s3 \
    --no-confirm-changeset

# ルートディレクトリに戻る
cd ..

echo "\n--- すべてのデプロイが完了しました！ ---"
aws cloudformation describe-stacks \
    --stack-name "${FRONTEND_STACK_NAME}" \
    --region "${AWS_REGION}" \
    --query "Stacks[0].Outputs" \
    --output table

