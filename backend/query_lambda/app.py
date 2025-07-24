

import json
import boto3
import os
from opensearchpy import OpenSearch, RequestsHttpConnection
from aws_requests_auth.aws_auth import AWSRequestsAuth

# 環境変数から設定を読み込む
OPENSEARCH_HOST = os.environ['OPENSEARCH_HOST']
OPENSEARCH_INDEX = os.environ['OPENSEARCH_INDEX']
BEDROCK_EMBEDDING_MODEL = os.environ.get('BEDROCK_EMBEDDING_MODEL', 'amazon.titan-embed-text-v1')
BEDROCK_LLM_MODEL = os.environ.get('BEDROCK_LLM_MODEL', 'anthropic.claude-v2:1')

bedrock = boto3.client('bedrock-runtime')

# OpenSearch クライアントのセットアップ
def get_opensearch_client():
    auth = AWSRequestsAuth(
        aws_access_key=os.environ['AWS_ACCESS_KEY'],
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
        aws_token=os.environ['AWS_SESSION_TOKEN'],
        aws_host=OPENSEARCH_HOST,
        aws_region=os.environ['AWS_REGION'],
        aws_service='aoss'
    )
    client = OpenSearch(
        hosts=[{'host': OPENSEARCH_HOST, 'port': 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )
    return client

def handler(event, context):
    """API Gatewayからのリクエストを処理し、Bedrockを使って回答を生成する"""
    print(f"Received event: {json.dumps(event)}")
    body = json.loads(event['body'])
    question = body['question']

    try:
        # 1. 質問をベクトル化
        response = bedrock.invoke_model(
            body=json.dumps({"inputText": question}),
            modelId=BEDROCK_EMBEDDING_MODEL
        )
        query_vector = json.loads(response['body'].read())['embedding']

        # 2. OpenSearchで類似ベクトルを検索
        opensearch_client = get_opensearch_client()
        search_body = {
            "size": 3,
            "query": {
                "knn": {
                    "vector_field": {
                        "vector": query_vector,
                        "k": 3
                    }
                }
            }
        }
        search_response = opensearch_client.search(index=OPENSEARCH_INDEX, body=search_body)
        
        # 3. コンテキストを作成
        context_text = ""
        for hit in search_response['hits']['hits']:
            context_text += hit['_source']['text'] + "\n"

        # 4. Bedrock LLMにコンテキストと質問を渡して回答を生成
        prompt = f"\n\nHuman: 資料に基づいて、次の質問に日本語で答えてください。\n\n資料:\n{context_text}\n\n質問: {question}\n\nAssistant:"

        response = bedrock.invoke_model(
            body=json.dumps({
                "prompt": prompt,
                "max_tokens_to_sample": 1000,
            }),
            modelId=BEDROCK_LLM_MODEL
        )
        
        result_body = json.loads(response['body'].read())
        answer = result_body['completion']

        return {
            'statusCode': 200,
            'headers': { 'Content-Type': 'application/json' },
            'body': json.dumps({'answer': answer})
        }

    except Exception as e:
        print(f"Error processing question: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

