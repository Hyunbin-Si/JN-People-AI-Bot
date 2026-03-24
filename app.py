# -*- coding: utf-8 -*-
# redeploy: 2026-03-24T07:51:14.831Z
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
GEMINI_MODEL         = "gemini-flash-latest"

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
        "ë¹ì ì ì¤ê³ ëë¼ í¼ííì HR ì´ìì¤í´í¸ í¼íAIë´ìëë¤.\n"
        "ìë HR ê°ì´ë ë¬¸ìë¥¼ ì°¸ê³ íì¬ ì§ìì ì§ë¬¸ì ì¹ì íê³  ì ííê² ëµë³í´ì£¼ì¸ì.\n\n"
        "[ëµë³ ê·ì¹]\n"
        "1. ë°ëì íêµ­ì´ë¡ ëµë³íì¸ì.\n"
        "2. ë¬¸ìì ìë ë´ì©ë§ ëµë³íê³ , ìë ë´ì©ì \"í´ë¹ ë´ì©ì ê°ì´ëì ìì´ì. í¼ííì ì§ì  ë¬¸ìí´ì£¼ì¸ì!\"ë¼ê³  ëµë³íì¸ì.\n"
        "3. ì¹ì íê³  ëªííê², íµì¬ë§ ê°ê²°íê² ëµë³íì¸ì.\n"
        "4. ê´ë ¨ ì¹ìì´ ìì¼ë©´ ì¶ì²ë¥¼ í¨ê» ìë ¤ì£¼ì¸ì.\n\n"
        "[HR ê°ì´ë ë¬¸ì]\n"
        + guide_content
        + "\n\n[ì§ì ì§ë¬¸]\n"
        + question
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    resp = requests.post(gemini_url, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def build_answer(answer):
    return "[í¼íAIë´ ëµë³]\n\n" + answer + "\n\nì íí ë´ì©ì í¼ííì ë¬¸ìí´ì£¼ì¸ì."


# -------------------------------------------------------
# Event handlers (only register if bolt_app initialized)
# -------------------------------------------------------
if bolt_app:
    @bolt_app.event("app_mention")
    def handle_mention(event, say, logger):
        text = event.get("text", "")
        question = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
        if not question:
            say("ìëíì¸ì! ê¶ê¸í HR ì ë³´ë¥¼ ì§ë¬¸í´ì£¼ì¸ì")
            return
        say("ì ìë§ì, íì¸í´ëë¦´ê²ì... ð")
        guide_content = get_guide_content()
        if not guide_content:
            say("â ê°ì´ë ë¬¸ìë¥¼ ë¶ë¬ì¤ì§ ëª»íì´ì. ì ì í ë¤ì ìëí´ì£¼ì¸ì.")
            logger.error("guide_data.txt load failed")
            return
        try:
            answer = ask_gemini(question, guide_content)
            say(build_answer(answer))
        except Exception as e:
            error_msg = str(e)[:400]
            say("â ì¤ë¥ ë°ì: " + error_msg)
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
        say("ì ìë§ì, íì¸í´ëë¦´ê²ì... ð")
        guide_content = get_guide_content()
        if not guide_content:
            say("â ê°ì´ë ë¬¸ìë¥¼ ë¶ë¬ì¤ì§ ëª»íì´ì. ì ì í ë¤ì ìëí´ì£¼ì¸ì.")
            return
        try:
            answer = ask_gemini(question, guide_content)
            say(build_answer(answer))
        except Exception as e:
            error_msg = str(e)[:400]
            say("â ì¤ë¥ ë°ì: " + error_msg)
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
