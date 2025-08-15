import os
import discord
from discord.ext import commands, tasks
import datetime
import pytz
from flask import Flask
from threading import Thread

# --- 設定値 ---
# Botのトークンを直接書く代わりに、環境変数から読み込むように変更
TOKEN = os.environ.get('DISCORD_BOT_TOKEN') 
if TOKEN is None:
    print("エラー: 環境変数 'DISCORD_BOT_TOKEN' が設定されていません。")
    exit()
    
# サーバーID
GUILD_ID = 1405243040259375134  # 例: 123456789012345678

# 利用可能ロールと認証待ちロールのID
AVAILABLE_ROLE_ID = 1405603760092483726
WAITING_ROLE_ID = 1405603410287263976

# 利用可能時間帯 (JST: 日本時間)
START_HOUR = 0
END_HOUR = 5

# --- Botの初期化 ---
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# --- Flaskアプリケーションの作成 ---
app = Flask(__name__)

# Webサーバーのルート設定
@app.route('/')
def home():
    return "Hello! The bot is alive."

# Webサーバーをバックグラウンドで起動する関数
def run_server():
    # ホスティングサービスが指定するポートを使用
    app.run(host='0.0.0.0', port=8080)

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
    guild = bot.get_guild(GUILD_ID)
    if not guild:
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
    guild = bot.get_guild(GUILD_ID)
    if not guild:
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

# --- Botがログインした時の処理 ---
@bot.event
async def on_ready():
    print(f'ログインしました: {bot.user}')
    # Webサーバーを別スレッドで起動
    server_thread = Thread(target=run_server)
    server_thread.start()
    # 定期実行タスクを開始
    change_waiting_roles.start()
    enforce_lockdown.start()

# Botの実行

bot.run(TOKEN)
