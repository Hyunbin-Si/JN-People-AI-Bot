import os
import re
import base64
import requests
from flask import Flask, request
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from google import genai

# -------------------------------------------------------
# 환경 변수
# -------------------------------------------------------
SLACK_BOT_TOKEN     = os.environ["SLACK_BOT_TOKEN"]
SLACK_SIGNING_SECRET = os.environ["SLACK_SIGNING_SECRET"]
GEMINI_API_KEY      = os.environ["GEMINI_API_KEY"]
GITHUB_TOKEN        = os.environ["GITHUB_TOKEN"]
GITHUB_OWNER        = os.environ.get("GITHUB_OWNER", "Hyunbin-Si")
GITHUB_REPO         = os.environ.get("GITHUB_REPO", "JN-People-AI-Bot")
GITHUB_FILE_PATH    = os.environ.get("GITHUB_FILE_PATH", "guide_data.txt")

# -------------------------------------------------------
# Gemini 설정
# -------------------------------------------------------
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# -------------------------------------------------------
# Slack 앱
# -------------------------------------------------------
app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)


def get_guide_content():
    """GitHub에서 guide_data.txt 내용을 가져옵니다."""
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


def ask_gemini(question: str, guide_content: str) -> str:
    """Gemini API로 HR 질문에 답변합니다."""
    prompt = f"""당신은 중고나라 피플팀의 HR 어시스턴트 '피플AI봇'입니다.
아래 HR 가이드 문서를 참고하여 직원의 질문에 친절하고 정확하게 답변해주세요.

[답변 규칙]
1. 반드시 한국어로 답변하세요.
2. 문서에 있는 내용만 답변하고, 없는 내용은 "해당 내용은 가이드에 없어요. 피플팀에 직접 문의해주세요! 😊"라고 답변하세요.
3. 친절하고 명확하게, 핵심만 간결하게 답변하세요.
4. 관련 섹션이 있으면 출처를 함께 알려주세요.

[HR 가이드 문서]
{guide_content}

[직원 질문]
{question}
"""
    response = gemini_client.models.generate_content(
        model="gemini-1.5-flash",
        contents=prompt
    )
    return response.text


def build_answer(answer: str) -> str:
    return f"📋 *피플AI봇 답변*\n\n{answer}\n\n_※ 정확한 내용은 피플팀에 문의해주세요._"


# -------------------------------------------------------
# 이벤트 핸들러: 채널에서 봇 멘션
# -------------------------------------------------------
@app.event("app_mention")
def handle_mention(event, say, logger):
    text = event.get("text", "")
    question = re.sub(r"<@[A-Z0-9]+>", "", text).strip()

    if not question:
        say("안녕하세요! 궁금한 HR 정보를 질문해주세요 😊\n예: `@피플AI봇 연차는 몇 개 발생하나요?`")
        return

    say("잠시만요, 확인해드릴게요... 🔍")

    guide_content = get_guide_content()
    if not guide_content:
        say("❌ 가이드 문서를 불러오지 못했어요. 잠시 후 다시 시도해주세요.")
        logger.error("guide_data.txt 로드 실패")
        return

    try:
        answer = ask_gemini(question, guide_content)
        say(build_answer(answer))
    except Exception as e:
        error_msg = str(e)[:400]
        say(f"❌ 오류 발생: {error_msg}")
        logger.error(f"Gemini API 오류: {e}")


# -------------------------------------------------------
# 이벤트 핸들러: DM (1:1 메시지)
# -------------------------------------------------------
@app.event("message")
def handle_dm(event, say, logger):
    # DM만 처리 (채널 메시지는 멘션으로만 응답)
    if event.get("channel_type") != "im":
        return
    # 봇 자신의 메시지 무시
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
        say(f"❌ 오류 발생: {error_msg}")
        logger.error(f"Gemini API 오류: {e}")


# -------------------------------------------------------
# Flask 서버 (Railway용)
# -------------------------------------------------------
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
