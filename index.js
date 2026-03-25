```javascript
const { App } = require("@slack/bolt");
const { GoogleGenAI } = require("@google/genai");
const fs = require("fs");
const path = require("path");
const http = require("http");

const app = new App({
  token: process.env.SLACK_BOT_TOKEN,
  signingSecret: process.env.SLACK_SIGNING_SECRET,
  socketMode: true,
  appToken: process.env.SLACK_APP_TOKEN,
});

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

const TARGET_CHANNELS = process.env.SLACK_CHANNEL_ID
  ? process.env.SLACK_CHANNEL_ID.split(",").map((id) => id.trim())
  : [];

function loadKnowledgeBase() {
  const knowledgeDir = path.join(__dirname, "knowledge");
  if (!fs.existsSync(knowledgeDir)) {
    console.error("[오류] knowledge 폴더가 없습니다!");
    return null;
  }
  const files = fs
    .readdirSync(knowledgeDir)
    .filter((f) => f.endsWith(".md") || f.endsWith(".txt"));
  if (files.length === 0) {
    console.error("[오류] knowledge 폴더에 파일이 없습니다!");
    return null;
  }
  let content = "";
  for (const file of files) {
    const text = fs.readFileSync(path.join(knowledgeDir, file), "utf-8");
    content += "\n\n=== " + file + " ===\n" + text;
    console.log("[지식베이스] " + file + " 로드 완료");
  }
  console.log("[지식베이스] 총 " + files.length + "개 파일 로드 완료");
  return content;
}

async function generateAnswer(question, knowledgeBase) {
  const response = await ai.models.generateContent({
    model: "gemini-2.5-flash",
    contents:
      "[지식 베이스]\n" +
      knowledgeBase +
      "\n\n[직원의 질문]\n" +
      question,
    config: {
      systemInstruction:
        "당신은 회사 내부 직원들의 질문에 답변하는 친절한 도우미 봇입니다.\n\n" +
        "[답변 규칙]\n" +
        "1. 반드시 지식 베이스에 있는 정보만 사용하여 답변하세요.\n" +
        "2. 간결하고 명확하게 한국어로 답변하세요.\n" +
        "3. 지식 베이스에 관련 정보가 없으면 '해당 정보를 찾을 수 없습니다. 담당자에게 직접 문의해주세요.'라고 답변하세요.\n" +
        "4. 답변은 Slack 메시지 형식에 맞게 작성하세요. (볼드: *텍스트*, 리스트: • 항목)\n" +
        "5. 너무 길지 않게, 핵심만 요약해서 답변하세요.",
      temperature: 0.3,
      maxOutputTokens: 1024,
    },
  });
  return response.text;
}

app.event("message", async ({ event, client }) => {
  try {
    if (event.bot_id || event.bot_profile) return;
    if (event.subtype) return;
    if (event.thread_ts) return;
    if (TARGET_CHANNELS.length > 0 && !TARGET_CHANNELS.includes(event.channel))
      return;

    const question = event.text ? event.text.trim() : "";
    if (!question) return;

    console.log("[질문 수신] 채널:" + event.channel + " | " + question);

    const loadingMsg = await client.chat.postMessage({
      channel: event.channel,
      thread_ts: event.ts,
      text: "🔍 답변을 준비하고 있습니다... 잠시만 기다려주세요!",
    });

    const knowledgeBase = loadKnowledgeBase();

    if (!knowledgeBase) {
      await client.chat.update({
        channel: event.channel,
        ts: loadingMsg.ts,
        text: "⚠️ 지식 베이스를 불러올 수 없습니다. 관리자에게 문의해주세요.",
      });
      return;
    }

    const answer = await generateAnswer(question, knowledgeBase);

    await client.chat.update({
      channel: event.channel,
      ts: loadingMsg.ts,
      text:
        "💡 *답변*\n\n" +
        answer +
        "\n\n---\n_이 답변은 AI가 내부 자료를 기반으로 생성했습니다. 정확하지 않을 수 있으니 참고용으로 활용해주세요._",
    });

    console.log("[답변 완료]");
  } catch (error) {
    console.error("[오류] 답변 생성 실패:", error.message);
    try {
      await client.chat.postMessage({
        channel: event.channel,
        thread_ts: event.ts,
        text: "❗ 답변 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
      });
    } catch (e) {
      console.error("[오류] 에러 메시지 전송 실패:", e.message);
    }
  }
});

const healthServer = http.createServer((req, res) => {
  res.writeHead(200, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ status: "ok", message: "Slack Bot is running!" }));
});

(async () => {
  try {
    await app.start();
    const port = process.env.PORT || 3000;
    healthServer.listen(port);
    console.log("=".repeat(50));
    console.log("⚡️ 슬랙 봇이 정상 실행되었습니다! 포트: " + port);
    console.log(
      "📡 대상 채널: " +
        (TARGET_CHANNELS.length > 0
          ? TARGET_CHANNELS.join(", ")
          : "모든 채널")
    );
    console.log("=".repeat(50));
  } catch (error) {
    console.error("봇 시작 실패:", error);
    process.exit(1);
  }
})();
```
