
# 完全なクラウドネイティブRAGエージェント (Fargate + Lambda)

このプロジェクトは、AWS Fargate（フロントエンド用）とAWS Lambda（バックエンド用）を組み合わせ、完全にクラウド上で動作する、スケーラブルで本番環境に対応したRAG（Retrieval-Augmented Generation）アプリケーションを構築します。

## アーキテクチャ概要

- **フロントエンド (ECS Fargate)**: **Chainlit** UIを内包したDockerコンテナを**AWS Fargate**で実行します。**Application Load Balancer (ALB)** を介して公開され、高い可用性とWebSocketサポートを提供します。
- **バックエンド (Lambda)**: 以前の設計と同じく、**API Gateway** と **AWS Lambda** を使用して、BedrockとOpenSearchを連携させ、ユーザーの質問に答えます。
- **ドキュメント処理**: **S3**へのファイルアップロードをトリガーに、**AWS Lambda**がドキュメントのベクトル化と**OpenSearch Serverless**への保存を自動的に行います。

---

## デプロイ手順

このデプロイは2つの主要なステップで構成されます：(A) フロントエンドのDockerイメージをビルドしてECRにプッシュする、(B) AWS SAMを使ってすべてのインフラを一度にデプロイする。

### 前提条件

- **AWSアカウント**
- **AWS CLI** (設定済み)
- **Docker** (実行中)
- **AWS SAM CLI** (インストール済み)

--- 

### (A) フロントエンドDockerイメージのビルドとプッシュ

#### ステップ 1: ECRリポジトリの作成

まず、フロントエンドのDockerイメージを保存するためのリポジトリをAmazon ECR (Elastic Container Registry) に作成します。

```bash
# <your-aws-region> をあなたのリージョンに置き換えてください (例: ap-northeast-1)
# <your-repo-name> をリポジトリ名に置き換えてください (例: chainlit-frontend)
aws ecr create-repository --repository-name <your-repo-name> --region <your-aws-region>
```

コマンドが成功すると、`repositoryUri` を含むJSONが出力されます。このURIは後で必要になるので、メモしておいてください。

#### ステップ 2: ECRへのログイン

DockerクライアントをECRに認証させます。

```bash
# <your-aws-account-id> と <your-aws-region> を置き換えてください
aws ecr get-login-password --region <your-aws-region> | docker login --username AWS --password-stdin <your-aws-account-id>.dkr.ecr.<your-aws-region>.amazonaws.com
```

#### ステップ 3: Dockerイメージのビルド

プロジェクトのルートディレクトリ（`Dockerfile`がある場所）で、次のコマンドを実行してイメージをビルドします。

```bash
# <your-repo-name> をステップ1で決めた名前に置き換えてください
docker build -t <your-repo-name> .
```

#### ステップ 4: イメージのタグ付けとプッシュ

ビルドしたイメージに、ECRリポジトリのURIでタグを付け、ECRにプッシュします。

```bash
# <repositoryUri> をステップ1でメモしたURIに置き換えてください
# 例: <your-aws-account-id>.dkr.ecr.<your-aws-region>.amazonaws.com/<your-repo-name>
docker tag <your-repo-name>:latest <repositoryUri>:latest
docker push <repositoryUri>:latest
```

これで、フロントエンドの準備は完了です。

--- 

### (B) SAMによるフルスタックデプロイ

#### ステップ 1: Lambdaの依存関係を準備する

以前と同様に、Lambda関数が必要とするライブラリの準備をします。

```bash
# プロジェクトのルートディレクトリで実行
cp lambda_requirements.txt index_lambda/requirements.txt
cp lambda_requirements.txt query_lambda/requirements.txt
```

#### ステップ 2: SAMビルド

アプリケーション全体をビルドします。

```bash
sam build --use-container
```

#### ステップ 3: SAMデプロイ

すべてのインフラをAWSにデプロイします。

```bash
sam deploy --guided
```

対話形式のプロンプトで、以下の情報を入力します：

- **Stack Name**: スタックの名前（例: `chainlit-full-stack-app`）。
- **AWS Region**: デプロイするリージョン。
- **Parameter OpenSearchCollectionName**: デフォルトのままでOKです。
- **Parameter FrontendImageUri**: **非常に重要**です。ステップAでECRにプッシュしたDockerイメージのURI（`:latest`タグを含む）をここに貼り付けます。
- **Confirm changes before deploy**: `y` を入力します。
- **Allow SAM CLI IAM role creation**: `y` を入力します。
- **Save arguments to samconfig.toml**: `y` を入力します。

SAMがVPC、ALB、Fargateサービス、Lambdaなど、すべてのリソースを作成するため、デプロイには**10〜15分**ほどかかる場合があります。

デプロイが完了すると、**Outputs**に`FrontendURL`が表示されます。これがあなたのアプリケーションの公開URLです。

--- 

## (C) アプリケーションの使用

1.  **フロントエンドにアクセス**: ブラウザで`FrontendURL`を開きます。ChainlitのUIが表示されるはずです。
2.  **ドキュメントのアップロード**: AWSコンソールのS3に移動し、SAMが作成したバケット（`Outputs`の`DocumentsBucketName`）に知識となるファイルをアップロードします。
3.  **質問する**: ファイルがLambdaによって処理された後（CloudWatchでログを確認できます）、フロントエンドのチャット画面から日本語で質問してみてください。
