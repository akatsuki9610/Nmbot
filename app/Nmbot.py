# coding: utf-8

import os
import discord
from discord.ext import commands, tasks
import datetime
import pytz
from flask import Flask
from threading import Thread
import asyncio

# --- 設定値 ---
TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
if TOKEN is None:
    print("エラー: 環境変数 'DISCORD_BOT_TOKEN' が設定されていません。")
    exit()

# サーバーID
GUILD_ID = 1405243040259375134

# 利用可能ロールと認証待ちロールのID
AVAILABLE_ROLE_ID = 1405603760092483726
WAITING_ROLE_ID = 1405603410287263976

# 利用可能時間帯 (JST: 日本時間)
START_HOUR = 0
END_HOUR = 5

# --- Botの初期化 ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True # この行を追加
bot = commands.Bot(command_prefix='!', intents=intents)

# --- Flaskアプリケーションの作成 ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Hello! The bot is alive."

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- 1. メンバー参加時にロールを自動付与 ---
@bot.event
async def on_member_join(member):
    guild = member.guild
    if guild.id != GUILD_ID:
        return

    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    current_hour = now.hour

    is_available_time = False
    if START_HOUR <= END_HOUR:
        if START_HOUR <= current_hour < END_HOUR:
            is_available_time = True
    else:
        if current_hour >= START_HOUR or current_hour < END_HOUR:
            is_available_time = True

    if is_available_time:
        role = guild.get_role(AVAILABLE_ROLE_ID)
        await member.add_roles(role)
        print(f'{member.name}に利用可能ロールを付与しました')
    else:
        role = guild.get_role(WAITING_ROLE_ID)
        await member.add_roles(role)
        print(f'{member.name}に認証待ちロールを付与しました')

# --- 2. 指定時間に認証待ちロールを変更 ---
@tasks.loop(time=datetime.time(hour=START_HOUR, tzinfo=pytz.timezone('Asia/Tokyo')))
async def change_waiting_roles():
    print(f"[{datetime.datetime.now()}] change_waiting_roles タスクを実行します。")
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        print("ギルドが見つかりません。")
        return

    waiting_role = guild.get_role(WAITING_ROLE_ID)
    available_role = guild.get_role(AVAILABLE_ROLE_ID)

    if waiting_role and available_role:
        for member in waiting_role.members:
            await member.remove_roles(waiting_role)
            await member.add_roles(available_role)
            print(f'{member.name}の認証待ちロールを利用可能ロールに変更しました')

# --- 3. 指定時間に全員をタイムアウト・VC切断 ---
@tasks.loop(time=datetime.time(hour=END_HOUR, tzinfo=pytz.timezone('Asia/Tokyo')))
async def enforce_lockdown():
    print(f"[{datetime.datetime.now()}] enforce_lockdown タスクを実行します。")
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        print("ギルドが見つかりません。")
        return

    owner = guild.owner
    bot_member = guild.get_member(bot.user.id)
    waiting_role = guild.get_role(WAITING_ROLE_ID)

    for member in guild.members:
        if member == owner or member == bot_member:
            continue
        try:
            if member.voice:
                await member.move_to(None)
                print(f'{member.name}をVCから切断しました')
            await member.edit(roles=[waiting_role])
            print(f'{member.name}のロールを認証待ちに変更しました')
            await member.timeout(datetime.timedelta(hours=1))
            print(f'{member.name}を1時間タイムアウトしました')
        except discord.Forbidden:
            print(f'{member.name}への処理に失敗しました（Botの権限不足）')

# --- コマンドを追加 ---
@bot.command()
async def check_time(ctx):
    """サーバーの現在の時刻を表示するコマンド"""
    utc_now = datetime.datetime.now(pytz.utc)
    jst = pytz.timezone('Asia/Tokyo')
    jst_now = utc_now.astimezone(jst)
    await ctx.send(f'サーバー時間 (UTC): {utc_now.strftime("%Y-%m-%d %H:%M:%S %Z%z")}\n日本時間 (JST): {jst_now.strftime("%Y-%m-%d %H:%M:%S %Z%z")}')
    print(f'サーバー時間 (UTC): {utc_now.strftime("%Y-%m-%d %H:%M:%S %Z%z")}')
    print(f'日本時間 (JST): {jst_now.strftime("%Y-%m-%d %H:%M:%S %Z%z")}')

@bot.command()
async def run_roles_change(ctx):
    """手動でロール付け替えタスクを実行するコマンド"""
    await ctx.send("認証待ちロールの変更タスクを手動で実行します。")
    await change_waiting_roles()
    await ctx.send("完了しました。")

# --- Botがログインした時の処理 ---
@bot.event
async def on_ready():
    print(f'ログインしました: {bot.user}')
    print("Bot is ready to accept commands.")
    server_thread = Thread(target=run_server)
    server_thread.start()
    change_waiting_roles.start()
    enforce_lockdown.start()
    print("定期実行タスクを開始しました。")

# Botの実行
bot.run(TOKEN)
