
import json
import boto3
import os
import urllib.parse
from opensearchpy import OpenSearch, RequestsHttpConnection
from aws_requests_auth.aws_auth import AWSRequestsAuth

# 環境変数から設定を読み込む
S3_BUCKET_NAME = os.environ['S3_BUCKET_NAME']
OPENSEARCH_HOST = os.environ['OPENSEARCH_HOST']
OPENSEARCH_INDEX = os.environ['OPENSEARCH_INDEX']
BEDROCK_EMBEDDING_MODEL = os.environ.get('BEDROCK_EMBEDDING_MODEL', 'amazon.titan-embed-text-v1')

s3 = boto3.client('s3')
bedrock = boto3.client('bedrock-runtime')

# OpenSearch クライアントのセットアップ
def get_opensearch_client():
    auth = AWSRequestsAuth(
        aws_access_key=os.environ['AWS_ACCESS_KEY_ID'],
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
    """S3トリガーで起動し、ドキュメントを処理してOpenSearchにインデックスする"""
    print(f"Received event: {json.dumps(event)}")

    # S3イベントからバケット名とキーを取得
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    
    try:
        # S3からドキュメントをダウンロード
        response = s3.get_object(Bucket=bucket, Key=key)
        document_content = response['Body'].read().decode('utf-8')

        # ドキュメントをチャンクに分割（シンプルな例）
        chunks = [document_content[i:i+500] for i in range(0, len(document_content), 500)]

        opensearch_client = get_opensearch_client()

        for i, chunk in enumerate(chunks):
            # Bedrockでベクトルを生成
            response = bedrock.invoke_model(
                body=json.dumps({"inputText": chunk}),
                modelId=BEDROCK_EMBEDDING_MODEL,
                accept='application/json',
                contentType='application/json'
            )
            result = json.loads(response['body'].read())
            vector = result['embedding']

            # OpenSearchにドキュメントをインデックス
            document = {
                'vector_field': vector,
                'text': chunk,
                'source': key
            }
            opensearch_client.index(index=OPENSEARCH_INDEX, body=document, id=f"{key}-{i}")

        print(f"Successfully indexed {len(chunks)} chunks from {key}")
        return {'statusCode': 200, 'body': json.dumps(f'Successfully indexed {key}')}

    except Exception as e:
        print(f"Error processing {key}: {e}")
        raise e
