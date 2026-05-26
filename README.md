# Telegram bots

- `cecoach_bot` for mistakes correction in English, commands: /fix, /fixa - for academic stile
```
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

export TELEGRAM_BOT_TOKEN="..."
export GROQ_API_KEY="..."

python3 cecoach_bot.py
```
