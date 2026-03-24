# -*- coding: utf-8 -*-
import os
import re
import base64
import logging
import requests
from flask import Flask, request
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SLACK_BOT_TOKEN      = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")
GEMINI_API_KEY       = os.environ.get("GEMINI_API_KEY", "")
GITHUB_TOKEN         = os.environ.get("GITHUB_TOKEN", "")
GITHUB_OWNER         = os.environ.get("GITHUB_OWNER", "Hyunbin-Si")
GITHUB_REPO          = os.environ.get("GITHUB_REPO", "JN-People-AI-Bot")
GITHUB_FILE_PATH     = os.environ.get("GITHUB_FILE_PATH", "guide_data.txt")
GEMINI_MODEL         = "gemini-2.0-flash"

# -------------------------------------------------------
# Flask app starts FIRST so healthcheck always passes
# -------------------------------------------------------
flask_app = Flask(__name__)

@flask_app.route("/health", methods=["GET"])
def health():
    return "OK", 200

# -------------------------------------------------------
# Slack app (wrapped in try-except so Flask still starts)
# -------------------------------------------------------
try:
    bolt_app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)
    handler = SlackRequestHandler(bolt_app)
except Exception as e:
    logger.error("Slack App init failed: " + str(e))
    bolt_app = None
    handler = None


def get_guide_content():
    url = (
        "https://api.github.com/repos/"
        + GITHUB_OWNER + "/" + GITHUB_REPO
        + "/contents/" + GITHUB_FILE_PATH
    )
    hdrs = {
        "Authorization": "token " + GITHUB_TOKEN,
        "Accept": "application/vnd.github.v3+json"
    }
    resp = requests.get(url, headers=hdrs, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        return base64.b64decode(data["content"]).decode("utf-8")
    return None


def ask_gemini(question, guide_content):
    gemini_url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + GEMINI_MODEL
        + ":generateContent?key=" + GEMINI_API_KEY
    )
    prompt = (
        "당신은 중고나라 피플팀의 HR 어시스턴트 피플AI봇입니다.\n"
        "아래 HR 가이드 문서를 참고하여 직원의 질문에 친절하고 정확하게 답변해주세요.\n\n"
        "[답변 규칙]\n"
        "1. 반드시 한국어로 답변하세요.\n"
        "2. 문서에 있는 내용만 답변하고, 없는 내용은 \"해당 내용은 가이드에 없어요. 피플팀에 직접 문의해주세요!\"라고 답변하세요.\n"
        "3. 친절하고 명확하게, 핵심만 간결하게 답변하세요.\n"
        "4. 관련 섹션이 있으면 출처를 함께 알려주세요.\n\n"
        "[HR 가이드 문서]\n"
        + guide_content
        + "\n\n[직원 질문]\n"
        + question
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    resp = requests.post(gemini_url, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def build_answer(answer):
    return "[피플AI봇 답변]\n\n" + answer + "\n\n정확한 내용은 피플팀에 문의해주세요."


# -------------------------------------------------------
# Event handlers (only register if bolt_app initialized)
# -------------------------------------------------------
if bolt_app:
    @bolt_app.event("app_mention")
    def handle_mention(event, say, logger):
        text = event.get("text", "")
        question = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
        if not question:
            say("안녕하세요! 궁금한 HR 정보를 질문해주세요")
            return
        say("잠시만요, 확인해드릴게요... 🔍")
        guide_content = get_guide_content()
        if not guide_content:
            say("❌ 가이드 문서를 불러오지 못했어요. 잠시 후 다시 시도해주세요.")
            logger.error("guide_data.txt load failed")
            return
        try:
            answer = ask_gemini(question, guide_content)
            say(build_answer(answer))
        except Exception as e:
            error_msg = str(e)[:400]
            say("❌ 오류 발생: " + error_msg)
            logger.error("Gemini API error: " + str(e))

    @bolt_app.event("message")
    def handle_dm(event, say, logger):
        if event.get("channel_type") != "im":
            return
        if event.get("bot_id"):
            return
        question = event.get("text", "").strip()
        if not question:
            return
        say("잠시만요, 확인해드릴게요... 🔍")
        guide_content = get_guide_content()
        if not guide_content:
            say("❌ 가이드 문서를 불러오지 못했어요. 잠시 후 다시 시도해주세요.")
            return
        try:
            answer = ask_gemini(question, guide_content)
            say(build_answer(answer))
        except Exception as e:
            error_msg = str(e)[:400]
            say("❌ 오류 발생: " + error_msg)
            logger.error("Gemini API error: " + str(e))


# -------------------------------------------------------
# Flask routes
# -------------------------------------------------------
@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    if handler is None:
        return "Slack not initialized", 500
    return handler.handle(request)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    flask_app.run(host="0.0.0.0", port=port)
