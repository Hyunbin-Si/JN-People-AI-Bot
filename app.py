import os
import re
import base64
import requests
from flask import Flask, request
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
import google.generativeai as genai

SLACK_BOT_TOKEN     = os.environ["SLACK_BOT_TOKEN"]
SLACK_SIGNING_SECRET = os.environ["SLACK_SIGNING_SECRET"]
GEMINI_API_KEY      = os.environ["GEMINI_API_KEY"]
GITHUB_TOKEN        = os.environ["GITHUB_TOKEN"]
GITHUB_OWNER        = os.environ.get("GITHUB_OWNER", "Hyunbin-Si")
GITHUB_REPO         = os.environ.get("GITHUB_REPO", "JN-People-AI-Bot")
GITHUB_FILE_PATH    = os.environ.get("GITHhUB_FILE_PATH", "guide_data.txt")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)


def get_guide_content():
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code == 200:
        data = response.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return content
    return None


def ask_gemini(question, guide_content):
    prompt = f"""\ub2f9\uc2e0\uc740 \uc911\uace0\ub098\ub77c \ud53c\ud50c\ud300\uc758 HR \uc5b4\uc2dc\uc2a4\ud134\ud2b8 '\ud53c\ud50cAI\ubd07'\uc785\ub2c8\ub2e4.
\uc544\ub798 HR \uac00\uc774\ub4dc \ubb38\uc11c\ub97c \ucc38\uace0\ud558\uc5ec \uc9c1\uc6d0\uc758 \uc9c8\ubb38\uc5d0 \uce5c\uc808\ud558\uace0 \uc815\ud655\ud558\uac8c \ub2f5\ubcc0\ud574\uc8fc\uc138\uc694.

[\ub2f5\ubcc0 \uaddc\uce59]
1. \ubc18\ub4dc\uc2dc \ud55c\uad6d\uc5b4\ub85c \ub2f5\ubcc0\ud558\uc138\uc694.
2. \ubb38\uc11c\uc5d0 \uc788\ub294 \ub0b4\uc6a9\ub9cc \ub2f5\ubcc0\ud558\uace0, \uc5c6\ub294 \ub0b4\uc6a9\uc740 "\ud574\ub2f9 \ub0b4\uc6a9\uc740 \uac00\uc774\ub4dc\uc5d0 \uc5c6\uc5b4\uc694. \ud53c\ud50c\ud300\uc5d0 \uc9c1\uc811 \ubb38\uc758\ud574\uc8fc\uc138\uc694!"\ub77c\uace0 \ub2f5\ubcc0\ud558\uc138\uc694.
3. \uce5c\uc808\ud558\uace0 \uba85\ud655\ud558\uac8c, \ud575\uc2ec\ub9cc \uac04\uacb0\ud558\uac8c \ub2f5\ubcc0\ud558\uc138\uc694.
4. \uad00\ub828 \uc139\uc158\uc774 \uc788\uc73c\uba74 \ucd9c\cc98\ub97c \ud568\uaed8 \uc54c\ub824\uc8fc\uc138\uc694.

[HR \uac00\uc774\ub4dc \ubb38\uc11c]
{guide_content}

[\uc9c1\uc6d0 \uc9c8\ubb38]
{question}
"""
    response = model.generate_content(prompt)
    return response.text


def build_answer(answer):
    return f"\ud83d\udccb *\ud53c\ud50cAI\ubd07 \ub2f5\ubcc0*\n\n{answer}\n\n_\u203b \uc815\ud655\ud55c \ub0b4\uc6a9\uc740 \ud53c\ud50c\ud300\uc5d0 \ubb38\uc758\ud574\uc8fc\uc138\uc694._"


@app.event("app_mention")
def handle_mention(event, say, logger):
    text = event.get("text", "")
    question = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
    if not question:
        say("\uc548\ub155\ud558\uc138\uc694! \uad81\uae08\ud55c HR \uc815\ubcf4\ub97c \uc9c8\ubb38\ud574\uc8fc\uc138\uc694 \ud83d\ude0a")
        return
    say("\uc7a0\uc2dc\ub9cc\uc694, \ud655\uc778\ud574\ub4dc\ub9b4\uac8c\uc694... \ud83d\udd0d")
    guide_content = get_guide_content()
    if not guide_content:
        say("\u274c \uac00\uc774\ub4dc \ubb38\uc11c\ub97c \ubd88\ub7ec\uc624\uc9c0 \ubabb\ud588\uc5b4\uc694.")
        return
    try:
        answer = ask_gemini(question, guide_content)
        say(build_answer(answer))
    except Exception as e:
        say("\u274c \ub2f5\ubcc0 \uc0dd\uc131 \uc911 \uc624\ub958\uac00 \ubc1c\uc0dd\ud588\uc5b4\uc694.")
        logger.error(f"Gemini API \uc624\ub958: {e}")


@app.event("message")
def handle_dm(event, say, logger):
    if event.get("channel_type") != "im":
        return
    if event.get("bot_id"):
        return
    question = event.get("text", "").strip()
    if not question:
        return
    say("\uc7a0\uc2dc\ub9cc\uc694, \ud655\uc778\ud574\ub4dc\ub9b4\uac8c\uc694... \ud83d\udd0d")
    guide_content = get_guide_content()
    if not guide_content:
        say("\u274c \uac00\uc774\ub4dc \ubb38\uc11c\ub97c \ubd88\ub7ec\uc624\uc9c0 \ubabb\ud588\uc5b4\uc694.")
        return
    try:
        answer = ask_gemini(question, guide_content)
        say(build_answer(answer))
    except Exception as e:
        say("\u274c \ub2f5\ubcc0 \uc0dd\uc131 \uc911 \uc624\ub958\uac00 \ubc1c\uc0dd\ud588\uc5b4\uc694.")
        logger.error(f"Gemini API \uc624\ub958: {e}")


flask_app = Flask(__name__)
handler = SlackRequestHandler(app)


@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)


@flask_app.route("/health", methods=["GET"])
def health():
    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    flask_app.run(host="0.0.0.0", port=port)
