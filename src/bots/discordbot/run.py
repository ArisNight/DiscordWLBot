import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Modal, TextInput
import sqlite3
from mcrcon import MCRcon
from mcrcon import MCRconException
import config
import asyncio
import os
from datetime import datetime
import logging

# Настройка логгирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Инициализация базы данных
def init_db():
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'users.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        discord_id INTEGER NOT NULL,
        minecraft_nickname TEXT NOT NULL UNIQUE,
        age TEXT,
        how_found TEXT,
        interests TEXT,
        about TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        processed_at TIMESTAMP,
        processed_by TEXT
    )
    ''')
    conn.commit()
    conn.close()

init_db()

class ApplicationForm(Modal, title='Заявка на сервер'):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.minecraft_nickname = TextInput(
            label='Ваш никнейм в Minecraft',
            placeholder='Введите ваш никнейм точно как в игре',
            required=True,
            max_length=16
        )
        self.age = TextInput(
            label='Ваш возраст',
            placeholder='Сколько вам лет?',
            required=True,
            max_length=3
        )
        self.how_found = TextInput(
            label='Как вы узнали о проекте?',
            placeholder='Откуда вы узнали о нашем сервере?',
            required=True,
            max_length=100
        )
        self.interests = TextInput(
            label='Чем хотите заниматься?',
            placeholder='Что вас интересует на нашем сервере?',
            required=True,
            max_length=100
        )
        self.about = TextInput(
            label='Расскажите о себе',
            placeholder='Коротко расскажите о себе',
            required=True,
            style=discord.TextStyle.long,
            max_length=4096
        )
        self.add_item(self.minecraft_nickname)
        self.add_item(self.age)
        self.add_item(self.how_found)
        self.add_item(self.interests)
        self.add_item(self.about)
    
    async def on_submit(self, interaction: discord.Interaction):
        if check_nickname_exists(self.minecraft_nickname.value):
            await interaction.response.send_message(
                f"❌ Никнейм `{self.minecraft_nickname.value}` уже зарегистрирован в системе.",
                ephemeral=True
            )
            return
        
        success = add_user_to_db(
            discord_id=interaction.user.id,
            minecraft_nickname=self.minecraft_nickname.value,
            age=self.age.value,
            how_found=self.how_found.value,
            interests=self.interests.value,
            about=self.about.value
        )
        
        if not success:
            await interaction.response.send_message(
                "❌ Произошла ошибка при обработке вашей анкеты. Попробуйте позже.",
                ephemeral=True
            )
            return
        
        applications_channel = bot.get_channel(config.ADMIN_CHANNEL)
        
        if applications_channel:
            embed = discord.Embed(
                title='📝 Новая анкета',
                description=f'Игрок {interaction.user.mention} (`{interaction.user}`) заполнил анкету',
                color=discord.Color.blue()
            )
            
            embed.add_field(name="Ник в Minecraft", value=self.minecraft_nickname.value, inline=False)
            embed.add_field(name="Возраст", value=self.age.value, inline=True)
            embed.add_field(name="Узнал о проекте", value=self.how_found.value, inline=True)
            embed.add_field(name="Интересы", value=self.interests.value, inline=False)
            embed.add_field(name="О себе", value=self.about.value, inline=False)
            
            embed.set_footer(text=f"UserID: {interaction.user.id} | Ник: {self.minecraft_nickname.value} | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            
            message = await applications_channel.send(embed=embed)
            await message.add_reaction('✅')
            await message.add_reaction('❌')
            
            await interaction.response.send_message(
                "✅ Ваша анкета успешно отправлена на рассмотрение администрации!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Не удалось отправить анкету.  Укажите правильный ID канала.",
                ephemeral=True
            )

def check_nickname_exists(nickname):
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'users.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM users WHERE minecraft_nickname = ?', (nickname,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def add_user_to_db(discord_id, minecraft_nickname, age, how_found, interests, about):
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'users.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute('''
        INSERT INTO users (discord_id, minecraft_nickname, age, how_found, interests, about)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (discord_id, minecraft_nickname, age, how_found, interests, about))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def update_user_status(minecraft_nickname, status, processed_by):
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'users.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE users 
    SET status = ?, processed_at = ?, processed_by = ?
    WHERE minecraft_nickname = ?
    ''', (status, datetime.now(), processed_by, minecraft_nickname))
    conn.commit()
    conn.close()

async def send_rcon_command(command):
    try:
        with MCRcon(config.HOST, config.PASSWD, port=config.PORT) as mcr:
            resp = mcr.command(command)
            logging.info(f"RCON command '{command}' executed successfully.")
            return resp
    except ConnectionRefusedError as e:
        logging.error(f"RCON connection refused: {e}")
        return None
    except MCRconException as e:
        logging.error(f"RCON error: {e}")
        return None
    except Exception as e:
        logging.exception(f"Unexpected RCON error: {e}")
        return None

@bot.event
async def on_ready():
    print(f'Бот готов к работе как {bot.user.name}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
        channel = bot.get_channel(config.ADMIN_CHANNEL)
        if channel:
            print(f"Успешно подключился к каналу администраторов: {channel.name}")
        else:
            print(f"Не удалось подключиться к каналу администраторов. Проверьте ID канала: {config.ADMIN_CHANNEL}")

    except Exception as e:
        print(e)

@bot.tree.command(name="apply", description="Открыть форму заявки")
async def apply_command(interaction: discord.Interaction):
    await interaction.response.send_message("Нажмите на кнопку ниже, чтобы открыть форму заявки:", view=ApplyButtonView(), ephemeral=True)

class ApplyButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Заполнить анкету", style=discord.ButtonStyle.primary, custom_id="apply_button")
    async def apply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ApplicationForm())

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    if reaction.emoji in ['✅', '❌']:
        if reaction.message.channel.id != config.ADMIN_CHANNEL:
            return

        if not reaction.message.embeds:
            return

        embed = reaction.message.embeds[0]
        if not embed.footer.text:
            return

        try:
            footer_data = embed.footer.text.split(' | ')
            user_id = int(footer_data[0].split('UserID: ')[1])
            nickname = footer_data[1].split('Ник: ')[1]
        except (IndexError, ValueError):
            return

        author = await bot.fetch_user(user_id)

        if reaction.emoji == '✅':
            # Retry mechanism
            max_retries = 3
            for attempt in range(max_retries):
                rcon_response = await send_rcon_command(f"whitelist add {nickname}")

                if rcon_response is not None:
                    update_user_status(nickname, 'approved', str(user))

                    embed = discord.Embed(
                        title="🎉 Поздравляем! Вы приняты на сервер!",
                        description=(
                            f"Здравствуйте, {nickname}!\n\n"
                            "Ваша заявка на вступление была **одобрена** администрацией.\n\n"
                            "Теперь вы можете присоединиться к нашему серверу!\n\n"
                            f"**Администратор:** {user.mention}\n"
                            "**Дата:** " + datetime.now().strftime('%Y-%m-%d %H:%M')
                        ),
                        color=discord.Color.green()
                    )
                    await author.send(embed=embed)
                    break  # Exit the retry loop on success
                else:
                    logging.warning(f"RCON failed for {nickname} (attempt {attempt + 1}/{max_retries}).")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2)  # Wait before retrying
            else:
                await user.send(f"⚠ Ошибка при добавлении {nickname} в вайтлист после нескольких попыток. Проверьте RCON соединение и настройки сервера.")

        elif reaction.emoji == '❌':
            update_user_status(nickname, 'rejected', str(user))

            embed = discord.Embed(
                title="❌ Ваша заявка отклонена",
                description=(
                    "К сожалению, ваша заявка на вступление была отклонена администрацией.\n\n"
                    f"**Администратор:** {user.mention}\n"
                    "**Дата:** " + datetime.now().strftime('%Y-%m-%d %H:%M') + "\n\n"
                    "Если у вас есть вопросы, вы можете обратиться к администрации."
                ),
                color=discord.Color.red()
            )
            await author.send(embed=embed)

        await reaction.message.delete()

@bot.tree.command(name="check", description="Проверить статус игрока по нику")
@app_commands.describe(nickname='Никнейм игрока для проверки')
@app_commands.checks.has_permissions(administrator=True)
async def check_command(interaction: discord.Interaction, nickname: str):
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'users.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
    SELECT discord_id, minecraft_nickname, status, created_at, processed_at, processed_by
    FROM users WHERE minecraft_nickname = ?
    ''', (nickname,))
    user_data = cursor.fetchone()
    conn.close()
    
    if not user_data:
        await interaction.response.send_message(f"Игрок с ником `{nickname}` не найден в базе данных.", ephemeral=True)
        return
    
    discord_id, mc_nick, status, created_at, processed_at, processed_by = user_data
    
    embed = discord.Embed(
        title=f"Информация об игроке {mc_nick}",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="Discord ID", value=discord_id, inline=True)
    embed.add_field(name="Статус", value=status, inline=True)
    embed.add_field(name="Дата подачи", value=created_at, inline=False)
    
    if processed_at:
        embed.add_field(name="Дата обработки", value=processed_at, inline=True)
        embed.add_field(name="Обработано", value=processed_by, inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

def delete_user_data(nickname):
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'users.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM users WHERE minecraft_nickname = ?", (nickname,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Ошибка при удалении данных пользователя: {e}")
        return False
    finally:
        conn.close()

@bot.tree.command(name="rnick", description="Удалить все данные о нике (только для администраторов)")
@app_commands.describe(nickname="Никнейм игрока для удаления")
@app_commands.checks.has_permissions(administrator=True)
async def rnick_command(interaction: discord.Interaction, nickname: str):
    if delete_user_data(nickname):
        await interaction.response.send_message(f"Данные о нике `{nickname}` были успешно удалены.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Не удалось удалить данные о нике `{nickname}`.", ephemeral=True)

bot.run(config.DIS_TOKEN)
