import chainlit as cl
import requests
import json
import os

# API Gateway の URL を環境変数から取得
# この URL は AWS SAM のデプロイ後に設定する必要があります
API_URL = os.environ.get("API_URL")

@cl.on_chat_start
async def on_chat_start():
    """チャットセッションの初期化"""
    if not API_URL:
        await cl.Message(
            content="エラー: API_URLが設定されていません。管理者に連絡してください。"
        ).send()
        return

    cl.user_session.set("history", [])
    await cl.Message(
        content="こんにちは！私はあなたのドキュメントに関する質問に答えることができます。"
    ).send()

@cl.on_message
async def on_message(message: cl.Message):
    """ユーザーからのメッセージを処理し、API Gateway を介して Lambda を呼び出す"""
    if not API_URL:
        await cl.Message(
            content="エラー: API_URLが設定されていません。管理者に連絡してください。"
        ).send()
        return

    # ユーザーの質問と履歴をペイロードに含める
    history = cl.user_session.get("history")
    payload = {
        "question": message.content,
        "history": history
    }

    # 応答を待っている間にメッセージを表示
    msg = cl.Message(content="")
    await msg.send()

    try:
        # API Gateway エンドポイントを呼び出す
        response = requests.post(API_URL, json=payload, timeout=180)
        response.raise_for_status()  # HTTPエラーがあれば例外を発生させる

        # レスポンスをストリーミングで処理
        full_response = ""
        for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
            full_response += chunk
            await msg.stream_token(chunk)
        
        await msg.update()

        # 履歴を更新
        history.append({"type": "user", "data": message.content})
        history.append({"type": "ai", "data": full_response})
        cl.user_session.set("history", history)

    except requests.exceptions.RequestException as e:
        await cl.Message(content=f"エラー: APIの呼び出しに失敗しました。\n{e}").send()
    except Exception as e:
        await cl.Message(content=f"予期せぬエラーが発生しました。\n{e}").send()