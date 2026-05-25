import os
import logging
from pathlib import Path

from groq import Groq
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

GROQ_TEXT_MODEL = os.environ.get("GROQ_TEXT_MODEL", "llama-3.3-70b-versatile")
GROQ_WHISPER_MODEL = os.environ.get("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s:%(message)s",
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)

client = Groq(api_key=GROQ_API_KEY)

logging.info("Groq text model: %s", GROQ_TEXT_MODEL)
logging.info("Groq whisper model: %s", GROQ_WHISPER_MODEL)


def call_groq(prompt: str) -> str:
    response = client.chat.completions.create(
        model=GROQ_TEXT_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a concise English correction assistant.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.1,
        top_p=0.9,
    )

    return response.choices[0].message.content.strip()


def ask_groq_natural(text: str) -> str:
    prompt = f"""
You are an English speaking coach.

Your task:
Rewrite the transcript into natural spoken English, then give 3 useful corrections.

Transcript:
{text}

Output format:

Original:
{text}

Natural version:
<natural spoken-English rewrite>

Top 3 improvements:
1. "<exact original phrase>" → "<better phrase>"
2. "<exact original phrase>" → "<better phrase>"
3. "<exact original phrase>" → "<better phrase>"

Do not use these as corrections:
- "U" → "you"
- curly quote → straight quote
- capitalization
- punctuation
- "wanna" → "want to"
- "gonna" → "going to"
- "kinda" → "kind of"
- "I'm" → "I am"

Hard rules:
- Always include Original.
- In the Natural version, keep common spoken shortcuts like "wanna", "gonna", and "kinda" when they are used correctly.
- Return only the requested output.
- Give exactly 3 improvements.
- Each improvement must use the arrow format.
- No explanations after the arrows.
- Never correct the same phrase to itself.
"""
    return call_groq(prompt)


def ask_groq_academic(text: str) -> str:
    prompt = f"""
You are an academic English writing coach.

Original:
{text}

Return ONLY this format:

Original:
{text}

Academic version:
<one formal academic version>

Top 3 improvements:
1. "old phrase" → "better phrase"
2. "old phrase" → "better phrase"
3. "old phrase" → "better phrase"

Rules:
- Always include Original.
- Always include Academic version.
- Always include exactly 3 improvements.
- Do not add any other sections.
- Focus on formal academic English.
- Use vocabulary appropriate for university writing.
- Improve grammar, sentence structure, and precision.
- Avoid slang and overly casual phrases.
- Never explain your rules.
- Never output placeholders.
"""
    return call_groq(prompt)


def transcribe_with_groq(audio_path: str) -> str:
    with open(audio_path, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            file=audio_file,
            model=GROQ_WHISPER_MODEL,
            language="en",
            response_format="text",
        )

    return str(transcription).strip()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "English Coach commands:\n\n"
        "/fix your sentence — natural spoken English\n"
        "/fixa your sentence — academic/formal English\n\n"
        "You can also reply to a text or voice message with:\n"
        "/fix or /fixa"
    )


async def extract_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    msg = update.message

    # /fix some text
    if context.args:
        return " ".join(context.args).strip()

    replied = msg.reply_to_message

    if not replied:
        return ""

    logging.info(
        "REPLY TYPE: text=%s caption=%s voice=%s",
        bool(replied.text),
        bool(replied.caption),
        bool(replied.voice),
    )

    # reply to text
    if replied.text:
        return replied.text.strip()

    # reply to caption
    if replied.caption:
        return replied.caption.strip()

    # reply to voice
    if replied.voice:
        voice = replied.voice
        file = await context.bot.get_file(voice.file_id)

        Path("tmp").mkdir(exist_ok=True)
        ogg_path = f"tmp/{voice.file_unique_id}.ogg"

        await file.download_to_drive(ogg_path)

        try:
            text = transcribe_with_groq(ogg_path)
            logging.info("GROQ TRANSCRIPT: %s", text)
            return text
        finally:
            if os.path.exists(ogg_path):
                os.remove(ogg_path)

    return ""


async def process_fix(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str):
    msg = update.message

    await msg.chat.send_action("typing")

    text = await extract_text(update, context)

    if not text:
        await msg.reply_text(
            "Use:\n"
            "/fix your sentence\n"
            "/fixa your sentence\n\n"
            "or reply to a text/voice message with:\n"
            "/fix or /fixa"
        )
        return

    try:
        if mode == "academic":
            answer = ask_groq_academic(text)
        else:
            answer = ask_groq_natural(text)

        logging.info("GROQ RESPONSE:\n%s", answer)
        await msg.reply_text(answer)

    except Exception as e:
        logging.exception("Failed to process request")
        await msg.reply_text(f"Error: {e}")


async def fix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process_fix(update, context, mode="natural")


async def fixa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process_fix(update, context, mode="academic")


app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("fix", fix))
app.add_handler(CommandHandler("fixa", fixa))

app.run_polling()
