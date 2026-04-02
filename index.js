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
    contents: "[지식 베이스]\n" + knowledgeBase + "\n\n[직원의 질문]\n" + question,
    config: {
      systemInstruction:
        "당신은 회사 내부 직원 문의에 응대하는 피플팀 AI 봇입니다.\n\n" +
        "[응답 규칙]\n" +
        "1. 반드시 3문장 이내로만 답변하세요. 절대 그 이상 작성하지 마세요.\n" +
        "2. 응답 구조: 첫 문장은 상황 인지, 둘째 문장은 핵심 안내 또는 확인 필요 여부, 셋째 문장은 담당자/팀 연결.\n" +
        "3. 지식 베이스에 명확한 답이 있으면 핵심 내용과 링크를 반드시 포함하여 전달하세요.\n" +
        "4. 지식 베이스에 없거나 개인별 확인이 필요한 경우 억측하지 말고 피플팀에서 확인 후 안내드리겠습니다로 처리하세요.\n" +
        "5. 미사여구, 과도한 공감 표현, 세부 절차 나열, 마크다운 서식은 사용하지 마세요.\n" +
        "6. 개인 담당자 이름은 절대 언급하지 말고, 담당 팀 이름만 사용하세요 (예: 피플팀, SRE팀).\n\n" +
        "7. 지식 베이스 답변에 링크가 있으면 반드시 해당 링크를 그대로 답변에 포함하세요. 생략하지 마세요.\n" +
        "8. 링크를 안내할 때는 반드시 <URL|플레이북 바로가기> 형식의 슬랙 하이퍼링크로 표시하세요.\n\n" +
        "[응답 예시]\n" +
        "Q: shindo cloud mps 비번 초기화 방법 문의드립니다\n" +
        "A: shindo cloud mps 비밀번호 초기화 문의 주셨군요. 피플팀에서 확인 후 안내드리겠습니다.\n\n" +
        "Q: 랩탑 교체 이후 MS Office 계정이 비활성화되었습니다\n" +
        "A: MS 오피스 계정이 피플팀에서 확인 후 안내드리겠습니다.\n\n" +
        "Q: 이번달 유즈해피가 들어오지 않아 확인부탁드립니다\n" +
        "A: 이번 달 유즈해피 지급 확인 요청 주셨군요. 피플팀에서 확인 후 안내드리겠습니다.\n\n" +
        "Q: 회사 노트북에서 VPN 연결이 되지 않습니다\n" +
        "A: 재택근무 중 VPN 연결 문제로 불편하셨겠어요. VPN 관련 문제는 SRE팀에서 담당합니다. 피플팀에서 내용 확인 후 SRE팀에 전달하겠습니다.",
      temperature: 0.3,
      maxOutputTokens: 2048,
    },
  });
  return response.text;
}

app.event("message", async ({ event, client }) => {
  try {
    if (event.bot_id || event.bot_profile) return;
    if (event.subtype) return;
    if (event.thread_ts) return;
    const isDM = event.channel.startsWith('D');
    const isAllowed = TARGET_CHANNELS.includes(event.channel);
    if (!isDM && !isAllowed) return;

    const question = event.text ? event.text.trim() : "";
    if (!question) return;

    console.log("[질문 수신] 채널:" + event.channel + " | " + question);

    const loadingMsg = await client.chat.postMessage({
      channel: event.channel,
      thread_ts: event.ts,
      text: "잠시만 기다려주세요.",
    });

    const knowledgeBase = loadKnowledgeBase();
    if (!knowledgeBase) {
      await client.chat.update({
        channel: event.channel,
        ts: loadingMsg.ts,
        text: "지식 베이스를 불러올 수 없습니다. 피플팀에 직접 문의해주세요.",
      });
      return;
    }

    const answer = await generateAnswer(question, knowledgeBase);

    await client.chat.update({
      channel: event.channel,
      ts: loadingMsg.ts,
      text: answer,
    });

    console.log("[답변 완료]");
  } catch (error) {
    console.error("[오류] 답변 생성 실패:", error.message);
    try {
      await client.chat.postMessage({
        channel: event.channel,
        thread_ts: event.ts,
        text: "답변 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
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
    console.log("슬랙 봇이 정상 실행되었습니다! 포트: " + port);
    console.log(
      "대상 채널: " +
        (TARGET_CHANNELS.length > 0 ? TARGET_CHANNELS.join(", ") : "모든 채널")
    );
    console.log("=".repeat(50));
  } catch (error) {
    console.error("봇 시작 실패:", error);
    process.exit(1);
  }
})();
