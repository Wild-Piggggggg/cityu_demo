import os
import base64
import numpy as np
import asyncio
import time
import io
import wave
import pyaudio
import requests
import speech_recognition as sr
from openai import OpenAI
import re
import argparse

# --- 音频采集模块 ---
class AudioCollector:
    """
    负责从麦克风采集音频，并使用 VAD（语音活动检测）分割语音片段。
    """
    def __init__(self, sample_rate=16000, channels=1, chunk_size=1024):
        self.format = pyaudio.paInt16
        self.channels = channels
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size

        self.base_volume_threshold = 200
        self.volume_threshold = self.base_volume_threshold
        self.silence_duration = 1.5
        self.adaptive_threshold = True

        self.audio_chunks = []
        self.is_speaking = False
        self.last_speech_time = 0
        self.background_noise_level = 0

        self.pya = pyaudio.PyAudio()
        self.stream = None
        self.is_listening = False

    def _open_stream(self):
        if self.stream and self.stream.is_active():
            return True
        try:
            mic_info = self.pya.get_default_input_device_info()
            self.stream = self.pya.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=mic_info["index"],
                frames_per_buffer=self.chunk_size,
            )
            print("🎤 Microphone stream opened.")
            return True
        except Exception as e:
            print(f"❌ Error opening audio stream: {e}")
            self.stream = None
            return False

    def calculate_volume(self, data):
        audio_data = np.frombuffer(data, dtype=np.int16)
        return np.abs(audio_data).mean()

    async def calibrate_microphone(self, duration=2.0):
        if not self._open_stream():
            return False

        print(f"🔊 Calibrating microphone - please be silent for {duration} seconds...")
        noise_levels = []

        end_time = time.time() + duration
        while time.time() < end_time:
            try:
                data = await asyncio.to_thread(self.stream.read, self.chunk_size, exception_on_overflow=False)
                volume = self.calculate_volume(data)
                noise_levels.append(volume)
            except IOError as e:
                print(f"⚠️ Warning during calibration: {e}")
            await asyncio.sleep(0.01)

        if not noise_levels:
            print("⚠️ Calibration failed: no audio data read.")
            return False

        self.background_noise_level = np.mean(noise_levels)
        self.volume_threshold = max(self.background_noise_level * 2.5, self.base_volume_threshold)

        print(f"🔊 Calibration complete: Background noise = {self.background_noise_level:.2f}")
        print(f"🔊 Volume threshold set to {self.volume_threshold:.2f}")
        return True

    async def listen_and_collect(self, stop_event):
        if self.adaptive_threshold:
            if not await self.calibrate_microphone():
                return None

        if not self._open_stream():
            return None

        print("🎤 Listening... Please speak in English.")
        self.is_listening = True

        while not stop_event.is_set():
            try:
                data = await asyncio.to_thread(self.stream.read, self.chunk_size, exception_on_overflow=False)
                volume = self.calculate_volume(data)
                current_threshold = self.volume_threshold * 0.7 if self.is_speaking else self.volume_threshold

                if volume > current_threshold:
                    if not self.is_speaking:
                        print("🎤 Recording started...")
                        self.is_speaking = True
                        self.audio_chunks = []

                    self.audio_chunks.append(data)
                    self.last_speech_time = time.time()

                elif self.is_speaking:
                    self.audio_chunks.append(data)
                    silence_time = time.time() - self.last_speech_time
                    if silence_time >= self.silence_duration:
                        print(f"🎤 Recording stopped after {silence_time:.2f}s of silence.")
                        self.is_speaking = False
                        if self.audio_chunks:
                            return self.process_audio(self.audio_chunks)

                await asyncio.sleep(0.01)

            except IOError as e:
                print(f"⚠️ Warning during listening: {e}")
                continue
            except Exception as e:
                print(f"❌ Error in audio collection: {e}")
                self.is_listening = False
                return None

        self.is_listening = False
        print("🎤 Listening stopped.")
        return None

    def process_audio(self, audio_chunks):
        """将采集到的 PCM 块合并，返回原始字节及元数据，供 speech_recognition 使用"""
        combined_audio = b"".join(audio_chunks)
        duration = len(audio_chunks) * self.chunk_size / self.sample_rate
        sample_width = self.pya.get_sample_size(self.format)
        print(f"🎤 Collected audio: {duration:.2f} seconds")

        return {
            "raw_audio": combined_audio,
            "sample_rate": self.sample_rate,
            "sample_width": sample_width,
            "duration": duration,
        }

    def cleanup(self):
        print("🧹 Cleaning up AudioCollector resources...")
        if self.stream:
            try:
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                print(f"⚠️ Error closing stream: {e}")
            self.stream = None

        if self.pya:
            try:
                self.pya.terminate()
            except Exception as e:
                print(f"⚠️ Error terminating PyAudio: {e}")
            self.pya = None


# --- 英语聊天系统 ---
class EnglishChatSystem:
    """
    专注于英语口语练习的语音聊天系统。
    AI 角色为英语口语教练，负责纠错、示范和鼓励，同时保留 HTTP 转发功能。
    """
    def __init__(self, api_key, session_id=0, enable_audio_playback=True, http_forward_enabled=True):
        if not api_key:
            raise ValueError("API key is required.")

        self.api_key = api_key
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        self.session_id = session_id
        self.enable_audio_playback = enable_audio_playback
        self.http_forward_enabled = http_forward_enabled
        self.http_endpoint = "http://127.0.0.1:8010/human"

        # 【Zegao】英语口语教练系统提示词，使用固定格式方便提取转发内容
        self.messages = [
            {
                "role": "system",
                "content": (
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
                ),
            }
        ]

        self.local_knowledge_base = self._load_knowledge_base()

        # 【Zegao】英语常见口头禅和填充词过滤模式
        self.filler_words_pattern = re.compile(
            r"\b(um+|uh+|er+|ah+|like,?\s|you know,?\s|I mean,?\s|well,?\s|so,?\s|"
            r"basically,?\s|literally,?\s|actually,?\s|honestly,?\s|right\?|okay so)\b",
            re.IGNORECASE,
        )

        # 特殊符号过滤
        self.special_chars_pattern = re.compile(
            r"[*★☆◆◇●○◎□■△▲※→←↑↓⇒⇐⇑⇓↔↕⇔⇕⟶⟵⟹⟸⟺⟷]"
        )

        self.audio_collector = AudioCollector()
        self.pya_player = pyaudio.PyAudio()
        self.player_stream = None

        # 【Zegao】使用 speech_recognition 做本地 STT，所有语音最终转为文字再交互
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.stt_language = "en-US"

    async def transcribe_audio(self, audio_data: dict) -> str | None:
        """
        将 AudioCollector 返回的原始 PCM 数据通过 speech_recognition 转为文字。
        优先使用 Google Web Speech API（免费、英文识别准确）；
        网络不可用时自动回退提示用户手动输入。
        """
        raw_audio = audio_data["raw_audio"]
        sample_rate = audio_data["sample_rate"]
        sample_width = audio_data["sample_width"]

        audio_obj = sr.AudioData(raw_audio, sample_rate, sample_width)

        def _recognize():
            try:
                text = self.recognizer.recognize_google(audio_obj, language=self.stt_language)
                return text
            except sr.UnknownValueError:
                return None
            except sr.RequestError as e:
                raise RuntimeError(f"Google STT service error: {e}")

        try:
            print("🔍 Transcribing speech via Google STT...")
            text = await asyncio.to_thread(_recognize)
            if text:
                print(f"📝 Recognized: {text}")
            else:
                print("⚠️ Could not understand the audio. Please speak more clearly.")
            return text
        except RuntimeError as e:
            print(f"⚠️ {e}")
            return None

    def _load_knowledge_base(self):
        """
        英语口语学习知识库。
        关键词匹配用户问题，命中后优先转发预设的教学内容。
        """
        return [
            {
                "keywords": ["self-introduction", "introduce myself", "how to introduce"],
                "answer": (
                    "Great question! Here's a classic self-introduction structure: "
                    "Start with your name, where you're from, what you do, and one personal interest. "
                    "For example: 'Hi, I'm [Name]. I'm from [City]. I work as a [Job]. "
                    "In my free time, I love [Hobby].' Keep it natural and smile!"
                ),
            },
            {
                "keywords": ["small talk", "how are you", "how to start a conversation"],
                "answer": (
                    "Small talk is the key to breaking the ice! Common openers include: "
                    "'How's your day going?', 'What have you been up to lately?', or comments about the weather. "
                    "Always listen actively and ask follow-up questions to keep the conversation flowing. "
                    "Remember, showing genuine interest is more important than perfect grammar!"
                ),
            },
            {
                "keywords": ["past tense", "irregular verbs", "verb conjugation"],
                "answer": (
                    "Irregular verbs can be tricky! The most common ones to memorize are: "
                    "go → went, have → had, see → saw, do → did, get → got, make → made. "
                    "A great trick is to use them in short sentences you repeat daily, like "
                    "'I went to the store' or 'I had a great day.' Practice makes perfect!"
                ),
            },
            {
                "keywords": ["pronunciation", "how to pronounce", "accent"],
                "answer": (
                    "Improving pronunciation takes consistent practice. Three key tips: "
                    "1. Shadow native speakers — repeat what you hear immediately after. "
                    "2. Focus on word stress, not individual letters. For example, 'PHOtograph' vs 'phoTOgraphy'. "
                    "3. Record yourself and compare. Don't aim for a perfect accent — aim for clarity!"
                ),
            },
            {
                "keywords": ["job interview", "interview in english", "work english"],
                "answer": (
                    "For a job interview in English, remember these key phrases: "
                    "'I have X years of experience in...', 'My greatest strength is...', "
                    "'I'm particularly proud of...', and 'I'm looking forward to contributing to your team.' "
                    "Prepare a 60-second personal pitch and practice answering 'Tell me about yourself' fluently."
                ),
            },
            {
                "keywords": ["daily conversation", "everyday english", "common phrases"],
                "answer": (
                    "Here are 5 everyday English phrases you should master: "
                    "1. 'Could you say that again, please?' — asking for repetition politely. "
                    "2. 'What do you mean by...?' — asking for clarification. "
                    "3. 'That makes sense.' — showing understanding. "
                    "4. 'I was wondering if...' — making a polite request. "
                    "5. 'To be honest,...' — introducing a candid opinion. Use them naturally!"
                ),
            },
            {
                "keywords": ["shopping", "at the store", "buying"],
                "answer": (
                    "Shopping vocabulary essentials: "
                    "'Do you have this in a different size/color?', "
                    "'How much does this cost?', 'Is there a discount?', "
                    "'Can I try this on?', 'I'd like to return/exchange this, please.' "
                    "Pro tip: when paying, say 'Keep the change' or 'Can I get a receipt, please?'"
                ),
            },
            {
                "keywords": ["ordering food", "restaurant english", "at the cafe"],
                "answer": (
                    "Ordering at a restaurant is easier with these phrases: "
                    "'I'd like to have...', 'Could I get the check, please?', "
                    "'What do you recommend?', 'I'm allergic to...', "
                    "'Can I have that without [ingredient]?' "
                    "When the server asks 'How was everything?' a great reply is "
                    "'It was delicious, thank you!'"
                ),
            },
            {
                "keywords": ["traveling", "at the airport", "hotel check-in"],
                "answer": (
                    "Travel English essentials: "
                    "At the airport: 'I'd like a window seat, please.' / 'Where is the boarding gate?' "
                    "At the hotel: 'I have a reservation under [Name].' / 'Could I have a late checkout?' "
                    "Asking for directions: 'Excuse me, how do I get to...?' / 'Is it within walking distance?' "
                    "Always say 'thank you' and 'excuse me' — politeness goes a long way!"
                ),
            },
            {
                "keywords": ["phrasal verbs", "phrasal verb", "look up", "give up"],
                "answer": (
                    "Phrasal verbs are everywhere in natural English! Top ones to learn: "
                    "'give up' (stop trying), 'figure out' (understand), 'look forward to' (anticipate), "
                    "'bring up' (mention a topic), 'carry on' (continue), 'come up with' (think of an idea). "
                    "The best way to learn them is in context — notice them when reading or watching shows!"
                ),
            },
        ]

    def match_local_knowledge(self, user_text):
        """本地知识库关键词匹配，命中任一关键词即返回预设答案"""
        user_lower = user_text.lower()
        for item in self.local_knowledge_base:
            if any(kw.lower() in user_lower for kw in item["keywords"]):
                return item["answer"]
        return None

    def filter_filler_words(self, text):
        """过滤英语口头禅、填充词和特殊符号"""
        text = self.filler_words_pattern.sub("", text)
        text = self.special_chars_pattern.sub("", text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def extract_user_input_from_response(self, response_text):
        """从 AI 回复中提取 'User Input:' 部分（即纠正后的用户语句）"""
        try:
            pattern = r"User Input[:\s]+(.+?)(?=\nAI Response|$)"
            match = re.search(pattern, response_text, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip().lstrip('\n')

            # 【Zegao】备用格式兼容
            for alt_pattern in [
                r"User['']?s? (?:Input|Words|Text)[:\s]+(.+?)(?=\nAI|$)",
                r"Corrected[:\s]+(.+?)(?=\nAI|$)",
            ]:
                match = re.search(alt_pattern, response_text, re.DOTALL | re.IGNORECASE)
                if match:
                    return match.group(1).strip().lstrip('\n')

            return None
        except Exception as e:
            print(f"⚠️ Error extracting user input: {e}")
            return None

    def extract_answer_from_response(self, response_text):
        """从 AI 回复中提取 'AI Response:' 部分（即教练回复，用于转发）"""
        try:
            pattern = r"AI Response[:\s]+(.*)"
            match = re.search(pattern, response_text, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip().lstrip('\n')

            # 【Zegao】备用格式兼容
            for alt_pattern in [
                r"Coach(?:'s)? Response[:\s]+(.*)",
                r"Response[:\s]+(.*)",
                r"Reply[:\s]+(.*)",
            ]:
                match = re.search(alt_pattern, response_text, re.DOTALL | re.IGNORECASE)
                if match:
                    return match.group(1).strip().lstrip('\n')

            return None
        except Exception as e:
            print(f"⚠️ Error extracting AI answer: {e}")
            return None

    async def forward_to_http_server(self, text):
        """将教练回复异步转发到本地 HTTP 服务器（LiveTalking）"""
        if not self.http_forward_enabled:
            return

        clean_text = self.filter_filler_words(text)
        print(f"[Forward] clean_text: {clean_text}")
        data = {
            'text': clean_text,
            'type': 'echo',
            'interrupt': True,
            'sessionid': self.session_id,
        }

        try:
            response = await asyncio.to_thread(
                lambda: requests.post(self.http_endpoint, json=data, timeout=5)
            )
            if response.status_code == 200:
                print("✓ Successfully forwarded response to LiveTalking server.")
            else:
                print(f"⚠️ Forward failed. Status code: {response.status_code}")
        except Exception as e:
            print(f"⚠️ Error forwarding to HTTP server: {e}")

    async def handle_response(self, user_input: str):
        """
        处理用户文字输入（语音已在调用前由 STT 转为文字）：
        调用 Qwen 云端 API，解析响应，优先匹配本地知识库后转发。
        """
        print("\n🤖 Alex is thinking...")
        user_message = {"role": "user", "content": user_input}
        self.messages.append(user_message)

        try:
            completion_stream = await asyncio.to_thread(
                lambda: self.client.chat.completions.create(
                    model="qwen-omni-turbo",
                    messages=self.messages,
                    modalities=["text"],
                    stream=True,
                )
            )

            def process_stream_sync(stream):
                full_text_response = ""
                audio_data_list = []
                print("🤖 Alex: ", end="", flush=True)
                for chunk in stream:
                    if chunk.choices:
                        delta = chunk.choices[0].delta
                        if hasattr(delta, 'content') and delta.content:
                            full_text_response += delta.content
                        if hasattr(delta, 'audio') and delta.audio and "transcript" in delta.audio:
                            full_text_response += delta.audio["transcript"]
                        if hasattr(delta, 'audio') and delta.audio and "data" in delta.audio:
                            audio_data_list.append(base64.b64decode(delta.audio["data"]))
                print(f"\n[Full response] {full_text_response}")
                return full_text_response, audio_data_list

            full_text_response, audio_data_list = await asyncio.to_thread(
                process_stream_sync, completion_stream
            )

            if full_text_response:
                self.messages.append({"role": "assistant", "content": full_text_response})

                # 提取 'User Input' 部分，用于本地知识库匹配
                extracted_user_input = self.extract_user_input_from_response(full_text_response)

                if extracted_user_input:
                    local_answer = self.match_local_knowledge(extracted_user_input)
                    if local_answer:
                        print(f"\n📚 Matched local knowledge base — forwarding preset answer.")
                        await self.forward_to_http_server(local_answer)
                    else:
                        # 转发 AI 教练回复部分
                        answer_part = self.extract_answer_from_response(full_text_response)
                        if answer_part:
                            print(f"\n🤖 Forwarding AI coach response.")
                            await self.forward_to_http_server(answer_part)
                        else:
                            await self.forward_to_http_server(full_text_response)
                else:
                    # 无法解析结构，尝试提取回答部分后转发
                    answer_part = self.extract_answer_from_response(full_text_response)
                    if answer_part:
                        print(f"\n🤖 Forwarding AI coach response.")
                        await self.forward_to_http_server(answer_part)
                    else:
                        await self.forward_to_http_server(full_text_response)

            if audio_data_list and self.enable_audio_playback:
                print("🔊 Playing audio response...")
                try:
                    self.player_stream = self.pya_player.open(
                        format=pyaudio.paInt16, channels=1, rate=24000, output=True
                    )
                    for audio_data in audio_data_list:
                        self.player_stream.write(audio_data)
                finally:
                    if self.player_stream:
                        self.player_stream.stop_stream()
                        self.player_stream.close()
                        self.player_stream = None
                        print("🔊 Audio playback finished.")

        except Exception as e:
            print(f"❌ Error calling API: {e}")

    async def chat_loop(self):
        """主对话循环"""
        print("=" * 60)
        print("  English Speaking Coach — Powered by Qwen")
        print("=" * 60)
        print("  Commands:")
        print("    voice  — speak English into the microphone")
        print("    exit   — quit the program")
        print("    (or just type your English sentence directly)")
        print("=" * 60)

        while True:
            try:
                choice = await asyncio.to_thread(input, "\n> Your input: ")

                if choice.lower() == "exit":
                    break
                elif choice.lower() == "voice":
                    stop_event = asyncio.Event()
                    audio_data = await self.audio_collector.listen_and_collect(stop_event)
                    if audio_data:
                        # 【Zegao】语音→文字，后续全部走文字通道，避免直接传音频给 API 识别不准的问题
                        recognized_text = await self.transcribe_audio(audio_data)
                        if recognized_text:
                            print(f"\n> [Voice → Text]: {recognized_text}")
                            await self.handle_response(recognized_text)
                        else:
                            print("❌ Speech not recognized. Please try again or type your message.")
                    else:
                        print("❌ No audio captured. Please try again.")
                else:
                    await self.handle_response(choice)

            except (KeyboardInterrupt, EOFError):
                break

        print("\n💬 Session ended. Keep practicing your English!")

    def cleanup(self):
        """清理所有资源"""
        print("🧹 Cleaning up EnglishChatSystem resources...")
        self.audio_collector.cleanup()
        if self.player_stream:
            try:
                self.player_stream.stop_stream()
                self.player_stream.close()
            except Exception as e:
                print(f"⚠️ Error closing player stream: {e}")
        if self.pya_player:
            self.pya_player.terminate()


async def main():
    parser = argparse.ArgumentParser(description="English Speaking Coach with Qwen + LiveTalking forwarding.")
    parser.add_argument('--sessionid', type=int, default=0, help='Session ID for the HTTP forwarder.')
    parser.add_argument('--disable-audio', action='store_true', help='Disable local audio playback.')
    parser.add_argument('--disable-http', action='store_true', help='Disable HTTP forwarding to LiveTalking.')
    args = parser.parse_args()

    api_key = os.environ.get("DASHSCOPE_API_KEY", "sk-2a0ca9d070f14c4395fa8b596cb79482")
    if api_key == "sk-2a0ca9d070f14c4395fa8b596cb79482":
        print("⚠️ Using default API key. Please set the DASHSCOPE_API_KEY environment variable.")

    chat_system = None
    try:
        chat_system = EnglishChatSystem(
            api_key=api_key,
            session_id=args.sessionid,
            enable_audio_playback=not args.disable_audio,
            http_forward_enabled=not args.disable_http,
        )
        await chat_system.chat_loop()
    finally:
        if chat_system:
            chat_system.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted by user.")
