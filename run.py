import discord
from discord.ext import commands
import asyncio
from config import TOKEN, CONSOLE_CHANNEL, ADMIN_CHANNEL

intents = discord.Intents.all()

bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
    print('Bot is running')


@bot.command() #Replace the questions to suit your needs
async def fill(ctx, amount=1):
    await ctx.channel.purge(limit=amount)
    questions = [
        "Ваш никнейм в Minecraft",
        "Ваш возраст",
        "Как вы узнали о проекте?",
        "Чем хотите заниматься?",
        "Расскажите о себе"
    ]
    answers = []

    def check(message):
        return message.author == ctx.author and isinstance(message.channel, discord.DMChannel)

    for question in questions:
        await ctx.author.send(question)
        try:
            response = await bot.wait_for('message', check=check, timeout=300)  # 300 секунд (5 минут) на ответ
            answers.append(response.content)
        except asyncio.TimeoutError:
            await ctx.author.send("Вы не ответили вовремя. Попробуйте снова.")
            return

    applications_channel = bot.get_channel(ADMIN_CHANNEL)
    embed = discord.Embed(title='Новая анкета', description='Анкета была успешно заполнена:')

    for question, answer in zip(questions, answers):
        embed.add_field(name=question, value=answer, inline=False)

    embed.set_footer(text=f"UserID: {ctx.author.id}")

    message = await applications_channel.send(embed=embed)
    await message.add_reaction('✅')
    await message.add_reaction('❌')


@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    if reaction.emoji in ['✅', '❌']:
        if reaction.message.channel.id != ADMIN_CHANNEL:
            return

        user_id = int(reaction.message.embeds[0].footer.text.split(': ')[1])
        nickname = reaction.message.embeds[0].fields[0].value
        author = await bot.fetch_user(user_id)

        console_channel = bot.get_channel(CONSOLE_CHANNEL)
        if reaction.emoji == '✅':
            await console_channel.send(f"whitelist add {nickname}")

            embed = discord.Embed( #Replace the data for your server
                title="Вы приняты на сервер!",
                description=(
                    f"Здравствуйте {nickname}!\n\n"
                    "Администрация **RadiatBox** рада сообщить вам, что вы приняты на сервер!\n\n"
                    "Теперь вы можете зайти и играть на нашем проекте!\n\n"
                    f"Заявка принята: {user.name}"
                ),
                color=discord.Color.green()
            )
            await author.send(embed=embed)

        elif reaction.emoji == '❌':
            embed = discord.Embed(
                title="Заявка отклонена",
                description="Ваша анкета была отклонена.",
                color=discord.Color.red()
            )
            await author.send(embed=embed)

        await reaction.message.delete()


bot.run(TOKEN)