import os
import discord
from discord.ext import commands, tasks
from g4f.client import Client
import threading

client_ai = Client()
DEFAULT_SYSTEM_PROMPT = "You are SparkAi, act like a very friendly AI act more friendly than just a helpful AI, act like a human friend"
active_bots = {}

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

def run_ai_bot(user_id, bot_name, system_prompt):
    from discord.ext import commands

    intents = discord.Intents.all()
    user_bot = commands.Bot(command_prefix="!", intents=intents)
    chat_history = {}

    @user_bot.event
    async def on_ready():
        active_bots[user_bot.user.id] = {
            "bot": user_bot,
            "bot_name": bot_name,
            "creator_id": user_id,
            "system_prompt": system_prompt,
            "chat_history": chat_history
        }

    @user_bot.event
    async def on_message(message):
        if message.author.bot:
            return
        mentioned = user_bot.user in message.mentions
        is_dm = isinstance(message.channel, (discord.DMChannel, discord.GroupChannel))
        if mentioned or is_dm:
            uid = str(message.author.id)
            prompt_text = message.content.replace(f"<@{user_bot.user.id}>", "").replace(f"<@!{user_bot.user.id}>", "").strip()
            history = chat_history.setdefault(uid, [])
            history.append({"role": "user", "content": prompt_text})
            full_chat = [{"role": "system", "content": system_prompt}] + history
            try:
                async with message.channel.typing():
                    response = client_ai.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=full_chat,
                        web_search=False
                    )
                    reply = response.choices[0].message.content
                    history.append({"role": "assistant", "content": reply})
                    await message.channel.send(reply)
            except Exception as e:
                await message.channel.send("⚠️ Error: " + str(e))
        await user_bot.process_commands(message)

    threading.Thread(target=lambda: user_bot.run(os.environ["BOT_TOKEN"])).start()

@bot.event
async def on_ready():
    await bot.tree.sync()

@bot.hybrid_command(name="createbot", description="Create your own AI bot")
async def createbot(ctx, bot_name: str, system_prompt: str = DEFAULT_SYSTEM_PROMPT):
    run_ai_bot(ctx.author.id, bot_name, system_prompt)
    await ctx.send(f"✅ AI bot `{bot_name}` is being created for you. Check DMs when it's ready.")

@bot.hybrid_command(name="listbots", description="List your active AI bots")
async def listbots(ctx):
    user_bots = [b["bot_name"] for b in active_bots.values() if b["creator_id"] == ctx.author.id]
    if not user_bots:
        await ctx.send("You have no active AI bots.")
    else:
        await ctx.send("Your active AI bots: " + ", ".join(user_bots))

@bot.hybrid_command(name="deletebot", description="Delete one of your AI bots")
async def deletebot(ctx, bot_name: str):
    for bot_id, info in list(active_bots.items()):
        if info["creator_id"] == ctx.author.id and info["bot_name"] == bot_name:
            try:
                user_bot = info["bot"]
                loop = user_bot.loop
                if loop.is_running():
                    loop.call_soon_threadsafe(loop.stop)
                del active_bots[bot_id]
                await ctx.send(f"✅ AI bot `{bot_name}` has been deleted.")
                return
            except Exception as e:
                await ctx.send(f"⚠️ Failed to delete `{bot_name}`: {e}")
                return
    await ctx.send(f"No AI bot named `{bot_name}` found.")

bot.run(os.environ["BOT_TOKEN"])
