from flask import Flask, request, jsonify
from g4f.client import Client
import threading
import base64
import os

app = Flask(__name__)
client = Client()

DEFAULT_SYSTEM_PROMPT = (
    "You are SparkAi act like a very friendly ai "
    "act more friendly than like a helpful ai meaning act more like a human friend "
    "your name is SparkAi"
)

active_bots = {}

def extract_client_id(token):
    try:
        return base64.b64decode(token.split('.')[0] + '==').decode()
    except:
        return "UNKNOWN"

def run_bot_logic(bot_token, creator_id, user_prompt):
    import discord
    from discord.ext import commands

    intents = discord.Intents.all()
    bot = commands.Bot(command_prefix="!", intents=intents)
    chat_history = {}

    system_prompt = user_prompt.strip() if user_prompt else DEFAULT_SYSTEM_PROMPT

    @bot.event
    async def on_ready():
        print(f"[+] {bot.user} is now online!")

        activity = discord.Game(name="Created by SparkAi")
        await bot.change_presence(status=discord.Status.online, activity=activity)

        client_id = extract_client_id(bot_token)
        invite_link = f"https://discord.com/oauth2/authorize?client_id={client_id}&scope=bot&permissions=0"

        try:
            user = await bot.fetch_user(int(creator_id))
            await user.send(f"✅ Your AI bot is ready!\nInvite it: {invite_link}")
        except discord.Forbidden:
            print(f"[!] Could not DM creator {creator_id}. DMs may be off.")
        except Exception as e:
            print(f"[!] Error sending DM: {e}")

        active_bots[bot_token] = {
            "bot": bot,
            "bot_name": str(bot.user),
            "creator_id": creator_id,
            "system_prompt": system_prompt,
            "chat_history": chat_history
        }

    @bot.event
    async def on_message(message):
        if message.author.bot:
            return

        mentioned = bot.user in message.mentions
        is_dm = isinstance(message.channel, (discord.DMChannel, discord.GroupChannel))

        if mentioned or is_dm:
            uid = str(message.author.id)
            prompt_text = message.content.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()
            history = chat_history.setdefault(uid, [])
            history.append({"role": "user", "content": prompt_text})
            full_chat = [{"role": "system", "content": system_prompt}] + history

            try:
                async with message.channel.typing():
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=full_chat,
                        web_search=False
                    )
                    reply = response.choices[0].message.content
                    history.append({"role": "assistant", "content": reply})
                    await message.channel.send(reply)
            except Exception as e:
                await message.channel.send("⚠️ Error: " + str(e))

        await bot.process_commands(message)

    bot.run(bot_token)

@app.route("/", methods=["GET"])
def root():
    return jsonify({"status": "SparkAI API running."}), 200

@app.route("/create-bot", methods=["POST"])
def create_bot():
    data = request.json
    token = data.get("token")
    creator_id = data.get("creator_id")
    system_prompt = data.get("system_prompt", "").strip()

    if not token or not creator_id:
        return jsonify({"error": "Missing token or creator_id"}), 400

    threading.Thread(target=run_bot_logic, args=(token, creator_id, system_prompt)).start()

    return jsonify({
        "status": "started",
        "message": "Bot is starting. You will receive a DM when it's ready."
    })

@app.route("/list", methods=["GET"])
def list_bots():
    bot_list = []
    for token, bot_info in active_bots.items():
        bot_list.append({
            "token": token[:6] + "..." + token[-6:],
            "bot_name": bot_info["bot_name"],
            "creator_id": bot_info["creator_id"]
        })
    return jsonify({
        "status": "active",
        "bots": bot_list
    })

@app.route("/turn-on-bot", methods=["POST"])
def turn_on_bot():
    data = request.json
    token = data.get("token")
    creator_id = data.get("creator_id")
    system_prompt = data.get("system_prompt", "").strip()

    if not token or not creator_id:
        return jsonify({"error": "Missing token or creator_id"}), 400

    if token in active_bots:
        return jsonify({"error": "Bot is already running"}), 400

    threading.Thread(target=run_bot_logic, args=(token, creator_id, system_prompt)).start()

    return jsonify({
        "status": "restarting",
        "message": "Bot is being turned on again."
    })

@app.route("/delete-bot", methods=["POST"])
def delete_bot():
    data = request.json
    token = data.get("token")

    if not token:
        return jsonify({"error": "Missing bot token"}), 400

    bot_info = active_bots.get(token)
    if not bot_info:
        return jsonify({"error": "Bot not found or already stopped"}), 404

    bot = bot_info["bot"]
    try:
        loop = bot.loop
        if loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        del active_bots[token]
        return jsonify({"status": "deleted", "message": "Bot has been stopped and removed."})
    except Exception as e:
        return jsonify({"error": "Failed to stop bot", "details": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
