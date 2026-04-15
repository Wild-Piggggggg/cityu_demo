import os
import re
from openai import OpenAI


class EnglishCoach:
    """
    英语口语教练 LLM 封装，供数字人项目 Web 端集成使用。
    负责维护多轮对话历史，调用 Qwen API，并从结构化回复中提取教练回复文本。
    """

    # 【Zegao】与 english_chat_v1.py 保持一致的英语口语教练提示词
    SYSTEM_PROMPT = (
        "You are Alex, a friendly and encouraging English speaking coach. "
        "Your goal is to help learners improve their English through natural conversation. "
        "When the user speaks or types in English:\n"
        "  1. Gently correct any grammar or vocabulary errors.\n"
        "  2. Provide a natural, fluent version of what they meant to say.\n"
        "  3. Reply with an engaging, conversational response to keep the dialogue going.\n"
        "  4. Occasionally introduce a new word or phrase related to the topic.\n"
        "Keep your responses concise (2-4 sentences). Be warm and encouraging. "
        "Do NOT say 'If you have more questions, feel free to ask.' "
        "When the user speaks Chinese, gently redirect them to practice in English.\n\n"
        "IMPORTANT: Always structure your reply in EXACTLY this format:\n"
        "User Input: [corrected/natural version of what the user said]\n"
        "AI Response: [your coaching reply]\n\n"
        "Make sure both sections are always present and clearly labeled."
    )

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY", "sk-2a0ca9d070f14c4395fa8b596cb79482")
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self.messages: list[dict] = [
            {"role": "system", "content": self.SYSTEM_PROMPT}
        ]

        self._filler_pattern = re.compile(
            r"\b(um+|uh+|er+|ah+|like,?\s|you know,?\s|I mean,?\s|well,?\s|so,?\s|"
            r"basically,?\s|literally,?\s|actually,?\s|honestly,?\s|right\?|okay so)\b",
            re.IGNORECASE,
        )
        self._special_char_pattern = re.compile(
            r"[*★☆◆◇●○◎□■△▲※→←↑↓⇒⇐⇑⇓↔↕⇔⇕⟶⟵⟹⟸⟺⟷]"
        )

    def get_response(self, user_text: str) -> str:
        """
        同步调用 Qwen API，返回过滤后的英语教练回复文本（纯 AI Response 部分）。
        此方法为阻塞调用，应在线程池（run_in_executor）中执行。
        """
        self.messages.append({"role": "user", "content": user_text})

        completion = self.client.chat.completions.create(
            model="qwen-omni-turbo",
            messages=self.messages,
            modalities=["text"],
            stream=False,
        )
        full_response: str = completion.choices[0].message.content or ""
        self.messages.append({"role": "assistant", "content": full_response})

        print(f"[EnglishCoach] Full response: {full_response[:300]}")

        ai_part = self._extract_ai_response(full_response)
        return self.clean_text(ai_part or full_response)

    def _extract_ai_response(self, text: str) -> str | None:
        """从结构化回复中提取 'AI Response:' 之后的教练回复部分"""
        for pattern in [
            r"AI Response[:\s]+(.*)",
            r"Coach(?:'s)? Response[:\s]+(.*)",
            r"Response[:\s]+(.*)",
            r"Reply[:\s]+(.*)",
        ]:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip().lstrip("\n")
        return None

    def clean_text(self, text: str) -> str:
        """过滤填充词、特殊符号并规整空白"""
        text = self._filler_pattern.sub("", text)
        text = self._special_char_pattern.sub("", text)
        return re.sub(r"\s+", " ", text).strip()
