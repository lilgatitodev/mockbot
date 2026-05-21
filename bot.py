import discord
from discord.ext import commands
from discord import app_commands
import json
import random
import os

TOKEN = "put ur token here"
OWNER_IDS = ["1222409071596929046","1279134507915542568", "1288152294851870824", "1232103434757345332"]

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

mocked_users = {}  # guild_id -> {user_id: intensity}
channel_webhooks = {}  # channel_id -> webhook object (this is unused cuz im retarded)

def load_mocked_users():
    global mocked_users
    if os.path.exists("mocked_users.json"):
        with open("mocked_users.json", "r") as f:
            mocked_users = json.load(f)
    else:
        mocked_users = {}

def save_mocked_users():
    with open("mocked_users.json", "w") as f:
        json.dump(mocked_users, f, indent=2)

def mock_message(message: str, intensity: int) -> str:
    def stutter(word):
        if len(word) < 2:
            return word
        if intensity >= 4:
            return f"{word[0]}-" * random.randint(2, 3) + word
        elif intensity >= 3 and random.random() < 0.4:
            return f"{word[0]}-{word}"
        elif intensity == 2 and random.random() < 0.25:
            return f"{word[0]}-{word}"
        return word

    def apply_ny(text):
        chars = list(text)
        result = []
        for i, c in enumerate(chars):
            if c == 'n' and i + 1 < len(chars) and chars[i+1].isalpha():
                chance = 1.0 if intensity >= 5 else 0.2
                if random.random() < chance:
                    result.append(c)
                    result.append('y')
                    continue
            if c == 'N' and i + 1 < len(chars) and chars[i+1].isalpha():
                chance = 1.0 if intensity >= 5 else 0.2
                if random.random() < chance:
                    result.append(c)
                    result.append('Y')
                    continue
            result.append(c)
        return ''.join(result)

    def uwuify(word):
        word = word.replace("r", "w").replace("R", "W")
        word = word.replace("v", "w").replace("V", "W")
        word = apply_ny(word)
        return stutter(word)

    cringe_phrases = [
    "*blushes*", "*giggles*", "*nuzzles u*", "***owo!***", "***uwu!***",
    "***RAWRRR! >W<***", "**notices bulge**", "*whispers to self* senpai~",
    "*glomps u*", "*licks cheek*", "*hides face behind paws*", "*pounces on you*",
    "*starts twerking cutely*", "*squeaks*", "*wiggles ears*", "*meows softly*",
    "*sips chocolate milk*", "***nyaaa~***", "*cuddles u tightly*", "*tail sways excitedly*",
    "***uwu what's this?***", "*giggles and skips away*", "*snuggles into ur chest*",
    "*leans in close and whispers* hiiiii~", "***senpai... you're so dreamy***",
    "*drools*", "*plays with tail cutely*", "*flops into your lap*", "*huffs and pouts*",
    "*whimpers softly*", "*notices you from across the room*", "*nibbles cookie cutely*",
    "*blinks with big sparkly eyes*", "***teehee~***"
]

    emojis = ["🥺", "🤓", "✨", "😳", "😅"]

    words = message.split()
    new_words = []
    insert_indices = set(random.sample(range(len(words)), k=min(2, len(words)))) if intensity >= 2 else set()
    emoji_indices = set(random.sample(range(len(words)), k=min(3, len(words)))) if intensity >= 3 else set()

    for i, word in enumerate(words):
        if i in insert_indices:
            new_words.append(random.choice(cringe_phrases))
        uwu_word = uwuify(word)
        new_words.append(uwu_word)
        if i in emoji_indices:
            new_words.append(random.choice(emojis))

    mocked = " ".join(new_words)
    return mocked

@bot.event
async def on_ready():
    load_mocked_users()
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

@bot.tree.command(name="mock")
@app_commands.describe(user="User to mock", intensity="1 (low) to 5 (maximum)")
async def mock(interaction: discord.Interaction, user: discord.User, intensity: int = 1):
    if str(interaction.user.id) not in OWNER_IDS:
        await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    if guild_id not in mocked_users:
        mocked_users[guild_id] = {}
    mocked_users[guild_id][str(user.id)] = intensity
    save_mocked_users()
    await interaction.response.send_message(f"Now mocking {user.mention} with intensity {intensity} 🤓")

@bot.tree.command(name="unmock")
@app_commands.describe(user="User to stop mocking")
async def unmock(interaction: discord.Interaction, user: discord.User):
    if str(interaction.user.id) not in OWNER_IDS:
        await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    if guild_id in mocked_users and str(user.id) in mocked_users[guild_id]:
        del mocked_users[guild_id][str(user.id)]
        save_mocked_users()
        await interaction.response.send_message(f"Stopped mocking {user.mention}.")
    else:
        await interaction.response.send_message(f"{user.mention} was not being mocked.")

@bot.tree.command(name="mocked_list")
async def mocked_list(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    if guild_id not in mocked_users or not mocked_users[guild_id]:
        await interaction.response.send_message("No users are currently being mocked in this server.")
        return

    lines = [f"<@{uid}> (Intensity {intensity})" for uid, intensity in mocked_users[guild_id].items()]
    await interaction.response.send_message("Currently mocked users:\n" + "\n".join(lines))

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    guild_id = str(message.guild.id)
    user_id = str(message.author.id)
    channel_id = message.channel.id

    if guild_id in mocked_users and user_id in mocked_users[guild_id]:
        intensity = mocked_users[guild_id][user_id]

        webhook = channel_webhooks.get(channel_id)

        try:
            if webhook is None:
                webhooks = await message.channel.webhooks()
                for wh in webhooks:
                    if wh.user == bot.user:
                        webhook = wh
                        break
                if webhook is None:
                    webhook = await message.channel.create_webhook(name="MockBot")
                channel_webhooks[channel_id] = webhook

            await message.delete()
            mocked_text = mock_message(message.content, intensity)
            await webhook.send(mocked_text, username=message.author.display_name, avatar_url=message.author.avatar.url)

        except (discord.NotFound, discord.HTTPException):
            try:
                webhook = await message.channel.create_webhook(name="i-love-penis-inside-me")
                channel_webhooks[channel_id] = webhook
                await message.delete()
                mocked_text = mock_message(message.content, intensity)
                await webhook.send(mocked_text, username=message.author.display_name, avatar_url=message.author.avatar.url)
            except Exception as e:
                print(f"Failed to recreate and use webhook in {message.channel.name}: {e}")

    await bot.process_commands(message)

bot.run(TOKEN)
