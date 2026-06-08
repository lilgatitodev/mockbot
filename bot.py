import discord
from discord.ext import commands
from discord import app_commands
import json
import random
import os
import logging
import asyncio
import unicodedata

# ── Config ────────────────────────────────────────────────────────────────────

TOKEN = "token"
OWNER_IDS = {"1422639622093148231","1427299411049840640"}
DATA_FILE = "mocked_users.json"
STATS_FILE = "mock_stats.json"

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
log = logging.getLogger("mockbot")

# ── Bot setup ─────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# guild_id -> { user_id -> {"intensity": int, "style": str} }
mocked_users: dict[str, dict[str, dict]] = {}

# guild_id -> { user_id -> int (message count) }
mock_stats: dict[str, dict[str, int]] = {}

# channel_id -> Webhook
_webhook_cache: dict[int, discord.Webhook] = {}

# (guild_id, user_id) -> asyncio.Task  (for timed mocks)
_timer_tasks: dict[tuple[str, str], asyncio.Task] = {}

# ── Persistence ───────────────────────────────────────────────────────────────

def load_data() -> None:
    global mocked_users, mock_stats
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            raw = json.load(f)
        # Migrate old format (user_id -> int) to new format (user_id -> dict)
        for guild_id, users in raw.items():
            mocked_users[guild_id] = {}
            for uid, val in users.items():
                if isinstance(val, int):
                    mocked_users[guild_id][uid] = {"intensity": val, "style": "uwu"}
                else:
                    mocked_users[guild_id][uid] = val
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            mock_stats.update(json.load(f))

def save_data() -> None:
    with open(DATA_FILE, "w") as f:
        json.dump(mocked_users, f, indent=2)
    with open(STATS_FILE, "w") as f:
        json.dump(mock_stats, f, indent=2)

def increment_stat(guild_id: str, user_id: str) -> None:
    mock_stats.setdefault(guild_id, {})
    mock_stats[guild_id][user_id] = mock_stats[guild_id].get(user_id, 0) + 1
    save_data()

# ── Zalgo data ────────────────────────────────────────────────────────────────

ZALGO_UP = ['\u030d', '\u030e', '\u0304', '\u0305', '\u033f', '\u0311', '\u0306',
            '\u0310', '\u0352', '\u0357', '\u0351', '\u0307', '\u0308', '\u030a',
            '\u0342', '\u0343', '\u0344', '\u034a', '\u034b', '\u034c', '\u0303',
            '\u0302', '\u030c', '\u0350', '\u0300', '\u0301', '\u030b', '\u030f']
ZALGO_DOWN = ['\u0316', '\u0317', '\u0318', '\u0319', '\u031c', '\u031d', '\u031e',
              '\u031f', '\u0320', '\u0324', '\u0325', '\u0326', '\u0329', '\u032a',
              '\u032b', '\u032c', '\u032d', '\u032e', '\u032f', '\u0330', '\u0331',
              '\u0332', '\u0333', '\u0339', '\u033a', '\u033b', '\u033c', '\u0345']
ZALGO_MID  = ['\u0315', '\u031b', '\u0340', '\u0341', '\u0358', '\u0321', '\u0322',
              '\u0327', '\u0328', '\u0334', '\u0335', '\u0336', '\u034f', '\u035c',
              '\u035d', '\u035e', '\u035f', '\u0360', '\u0362', '\u0338', '\u0337']

def zalgo(text: str, intensity: int = 2) -> str:
    result = []
    for char in text:
        result.append(char)
        if char.isalpha():
            up_count   = random.randint(0, intensity)
            down_count = random.randint(0, intensity)
            mid_count  = random.randint(0, 1)
            for _ in range(up_count):
                result.append(random.choice(ZALGO_UP))
            for _ in range(down_count):
                result.append(random.choice(ZALGO_DOWN))
            for _ in range(mid_count):
                result.append(random.choice(ZALGO_MID))
    return "".join(result)

# ── Drunk helpers ─────────────────────────────────────────────────────────────

DRUNK_TYPOS = {
    "a": "aa", "e": "ee", "i": "ii", "o": "oo", "the": "teh",
    "and": "adn", "you": "yuo", "for": "fro", "with": "wiht",
    "that": "taht", "this": "tihs", "have": "ahve", "they": "tehy",
}
DRUNK_SLURS = ["*hic*", "...wait", "wait no", "uhh", "lol no i mean", "im fine", "i swear"]

def drunk(text: str, intensity: int) -> str:
    words = text.split()
    result = []
    slur_chance   = 0.08 * intensity
    typo_chance   = 0.12 * intensity
    space_chance  = 0.07 * intensity
    repeat_chance = 0.06 * intensity

    for word in words:
        lower = word.lower()
        # Random slur insert
        if random.random() < slur_chance:
            result.append(random.choice(DRUNK_SLURS))
        # Known typo
        if lower in DRUNK_TYPOS and random.random() < typo_chance:
            typo = DRUNK_TYPOS[lower]
            result.append(typo if word.islower() else typo.capitalize())
        else:
            # Random double-letter typo
            if len(word) > 2 and random.random() < typo_chance * 0.5:
                idx = random.randint(0, len(word) - 1)
                word = word[:idx] + word[idx] + word[idx:]
            result.append(word)
        # Word repeat (brain slipped)
        if random.random() < repeat_chance:
            result.append(word)
        # Random extra space (smash spacebar)
        if random.random() < space_chance:
            result.append("")

    out = " ".join(result)
    # Trailing hic at high intensity
    if intensity >= 4 and random.random() < 0.5:
        out += " *hic*"
    return out

# ── Spongebob mocking case ────────────────────────────────────────────────────

def spongebob(text: str) -> str:
    result = []
    upper = False
    for char in text:
        if char.isalpha():
            result.append(char.upper() if upper else char.lower())
            upper = not upper
        else:
            result.append(char)
    return "".join(result)

# ── UWU transformation ────────────────────────────────────────────────────────

CRINGE_PHRASES = [
    "*blushes*", "*giggles*", "*nuzzles u*", "***owo!***", "***uwu!***",
    "***RAWRRR! >W<***", "**notices bulge**", "*whispers to self* senpai~",
    "*glomps u*", "*licks cheek*", "*hides face behind paws*", "*pounces on you*",
    "*starts twerking cutely*", "*squeaks*", "*wiggles ears*", "*meows softly*",
    "*sips chocolate milk*", "***nyaaa~***", "*cuddles u tightly*", "*tail sways excitedly*",
    "***uwu what's this?***", "*giggles and skips away*", "*snuggles into ur chest*",
    "*leans in close and whispers* hiiiii~", "***senpai... you're so dreamy***",
    "*drools*", "*plays with tail cutely*", "*flops into your lap*", "*huffs and pouts*",
    "*whimpers softly*", "*notices you from across the room*", "*nibbles cookie cutely*",
    "*blinks with big sparkly eyes*", "***teehee~***",
]
UWU_EMOJIS  = ["🥺", "🤓", "✨", "😳", "😅", "uwu", "owo", "~", "^^", ">w<"]
LISP_MAP    = str.maketrans({"s": "th", "S": "Th", "z": "th", "Z": "Th"})
KEYBOARD_SMASH = ["asdfghjkl", "qwerty", "zxcvbnm", "fjdksalfjdks", "asdfjkl;"]

def _apply_ny(text: str, intensity: int) -> str:
    chance = 1.0 if intensity >= 5 else (0.5 if intensity >= 3 else 0.2)
    result = []
    chars = list(text)
    for i, c in enumerate(chars):
        result.append(c)
        if c.lower() == "n" and i + 1 < len(chars) and chars[i + 1].isalpha():
            if random.random() < chance:
                result.append("Y" if c.isupper() else "y")
    return "".join(result)

def _stutter(word: str, intensity: int) -> str:
    if len(word) < 2:
        return word
    repeats = random.randint(2, 4) if intensity >= 4 else 2
    chance  = 1.0 if intensity >= 4 else (0.4 if intensity >= 3 else 0.2)
    if random.random() < chance:
        return f"{word[0]}-" * repeats + word
    return word

def _uwuify_word(word: str, intensity: int) -> str:
    word = word.replace("r", "w").replace("R", "W")
    word = word.replace("v", "w").replace("V", "W")
    word = _apply_ny(word, intensity)
    word = _stutter(word, intensity)
    return word

def uwu(text: str, intensity: int) -> str:
    if not text.strip():
        return text
    if intensity == 1:
        return text.translate(LISP_MAP)

    words  = text.split()
    n_cringe = {1: 0, 2: 0, 3: min(2, len(words)), 4: min(3, len(words)), 5: min(5, len(words))}.get(intensity, 0)
    n_emoji  = min(max(intensity - 2, 0), len(words))

    cringe_idx = set(random.sample(range(len(words)), k=n_cringe)) if n_cringe else set()
    emoji_idx  = set(random.sample(range(len(words)), k=n_emoji))  if n_emoji  else set()

    new_words = []
    for i, word in enumerate(words):
        if i in cringe_idx:
            new_words.append(random.choice(CRINGE_PHRASES))
        w = _uwuify_word(word, intensity)
        if intensity >= 4 and random.random() < 0.3:
            w = w.upper()
        new_words.append(w)
        if i in emoji_idx:
            new_words.append(random.choice(UWU_EMOJIS))
        # Intensity 5: random keyboard smash inserts
        if intensity >= 5 and random.random() < 0.15:
            new_words.append(random.choice(KEYBOARD_SMASH))

    result = " ".join(new_words)
    if intensity >= 5:
        sign_offs = ["uwu", "OwO", "~ senpai pls ~", "*dies cutely*", "rawr xd"]
        result += f"  {random.choice(sign_offs)}"
    return result

# ── Translator style (replace words with sus synonyms) ───────────────────────

TRANSLATOR_MAP = {
    "you":      ["thou", "u", "ye", "thy beloved", "kind soul"],
    "i":        ["I (the great)", "ya boi", "ur humble servant", "this guy"],
    "the":      ["ye olde", "tHe", "da"],
    "is":       ["doth be", "be", "iz"],
    "are":      ["art", "r", "be"],
    "good":     ["poggers", "valid", "based", "W"],
    "bad":      ["mid", "L", "cringe", "not it"],
    "like":     ["fw", "vibe with", "fw heavy"],
    "very":     ["lowkey", "kinda", "fr fr", "no cap"],
    "yes":      ["W", "based", "fr", "no cap"],
    "no":       ["L", "nah fam", "cap", "not it chief"],
    "ok":       ["ight bet", "say less", "fasho"],
    "hello":    ["sup", "ayo", "greetings traveller"],
    "bye":      ["later", "peace", "deuces", "✌️"],
    "what":     ["bruh", "tf", "wait what"],
    "why":      ["but why tho", "????", "bruh moment"],
    "please":   ["pls", "bestie pls", "i beg"],
    "sorry":    ["my bad", "mb", "oof sorry"],
    "thanks":   ["thx king", "appreciated bestie", "W response"],
    "lol":      ["💀", "LMAOOO", "im crying"],
    "funny":    ["sending me", "I'm deceased", "💀"],
    "think":    ["lowkey feel like", "got a sneaking suspicion"],
    "know":     ["fw the knowledge that", "clocked that"],
    "go":       ["yeet myself to", "slide to"],
    "come":     ["pull up to", "roll up to"],
    "make":     ["cook up", "manifest"],
    "want":     ["fw", "need on god"],
    "need":     ["on god need", "literally dying without"],
    "actually": ["no cap", "fr fr", "real talk"],
    "really":   ["on god", "deadass", "fr"],
    "right":    ["based", "W take", "real"],
    "wrong":    ["L take", "cap", "mid"],
}

def translator(text: str, intensity: int) -> str:
    words = text.split()
    result = []
    swap_chance = 0.15 * intensity
    for word in words:
        stripped = word.strip(".,!?;:'\"").lower()
        if stripped in TRANSLATOR_MAP and random.random() < swap_chance:
            replacement = random.choice(TRANSLATOR_MAP[stripped])
            # Preserve trailing punctuation
            punct = "".join(c for c in word if not c.isalnum())
            result.append(replacement + punct)
        else:
            result.append(word)
    return " ".join(result)

# ── Dispatch ──────────────────────────────────────────────────────────────────

STYLES = ["uwu", "spongebob", "drunk", "zalgo", "translator"]

def transform(text: str, intensity: int, style: str) -> str:
    if not text.strip():
        return text
    if style == "uwu":
        return uwu(text, intensity)
    if style == "spongebob":
        # Spongebob + stutter at higher intensities
        out = spongebob(text)
        if intensity >= 3:
            out = " ".join(_stutter(w, intensity) for w in out.split())
        return out
    if style == "drunk":
        return drunk(text, intensity)
    if style == "zalgo":
        return zalgo(text, min(intensity, 3))
    if style == "translator":
        return translator(text, intensity)
    return text

# ── Webhook helpers ───────────────────────────────────────────────────────────

async def get_webhook(channel: discord.TextChannel) -> discord.Webhook | None:
    cached = _webhook_cache.get(channel.id)
    if cached:
        return cached
    try:
        for wh in await channel.webhooks():
            if wh.user == bot.user:
                _webhook_cache[channel.id] = wh
                return wh
        wh = await channel.create_webhook(name="MockBot")
        _webhook_cache[channel.id] = wh
        return wh
    except discord.Forbidden:
        log.warning("No webhook permissions in #%s", channel.name)
        return None
    except discord.HTTPException as e:
        log.error("Webhook error in #%s: %s", channel.name, e)
        return None

def _invalidate_webhook(channel_id: int) -> None:
    _webhook_cache.pop(channel_id, None)

# ── Timer helpers ─────────────────────────────────────────────────────────────

async def _auto_unmock(guild_id: str, user_id: str, delay: int) -> None:
    await asyncio.sleep(delay)
    if guild_id in mocked_users and user_id in mocked_users[guild_id]:
        del mocked_users[guild_id][user_id]
        save_data()
        log.info("Auto-unmocked %s in guild %s", user_id, guild_id)
    _timer_tasks.pop((guild_id, user_id), None)

def schedule_unmock(guild_id: str, user_id: str, seconds: int) -> None:
    key = (guild_id, user_id)
    existing = _timer_tasks.get(key)
    if existing and not existing.done():
        existing.cancel()
    task = asyncio.create_task(_auto_unmock(guild_id, user_id, seconds))
    _timer_tasks[key] = task

# ── Permission check ──────────────────────────────────────────────────────────

def is_owner(user_id: int) -> bool:
    return str(user_id) in OWNER_IDS

# ── Slash commands ────────────────────────────────────────────────────────────

style_choices = [app_commands.Choice(name=s, value=s) for s in STYLES]
intensity_choices = [
    app_commands.Choice(name="1 – mild",             value=1),
    app_commands.Choice(name="2 – medium",           value=2),
    app_commands.Choice(name="3 – strong",           value=3),
    app_commands.Choice(name="4 – chaos",            value=4),
    app_commands.Choice(name="5 – maximum suffering", value=5),
]


@bot.tree.command(name="mock", description="Start mocking a user's messages")
@app_commands.describe(
    user="The user to mock",
    intensity="How hard to mock them (1–5)",
    style="Transformation style",
    minutes="Auto-unmock after this many minutes (0 = permanent)",
)
@app_commands.choices(intensity=intensity_choices, style=style_choices)
async def mock(
    interaction: discord.Interaction,
    user: discord.Member,
    intensity: int = 2,
    style: str = "uwu",
    minutes: int = 0,
):
    if not is_owner(interaction.user.id):
        await interaction.response.send_message("nope, owners only 👀", ephemeral=True)
        return
    if user.bot:
        await interaction.response.send_message("can't mock bots lol", ephemeral=True)
        return

    guild_id = str(interaction.guild_id)
    user_id  = str(user.id)
    mocked_users.setdefault(guild_id, {})[user_id] = {"intensity": intensity, "style": style}
    save_data()

    if minutes > 0:
        schedule_unmock(guild_id, user_id, minutes * 60)
        timer_note = f" for **{minutes}m**"
    else:
        timer_note = " permanently"

    style_icons = {"uwu": "🥺", "spongebob": "🧽", "drunk": "🍺", "zalgo": "👁️", "translator": "🗣️"}
    await interaction.response.send_message(
        f"{style_icons.get(style, '🤓')} mocking {user.mention} — style **{style}**, intensity **{intensity}/5**{timer_note}"
    )


@bot.tree.command(name="mockmode", description="Change the mock style for an already-mocked user")
@app_commands.describe(user="The mocked user", style="New style to apply")
@app_commands.choices(style=style_choices)
async def mockmode(interaction: discord.Interaction, user: discord.Member, style: str):
    if not is_owner(interaction.user.id):
        await interaction.response.send_message("nope, owners only 👀", ephemeral=True)
        return

    guild_id = str(interaction.guild_id)
    entry = mocked_users.get(guild_id, {}).get(str(user.id))
    if not entry:
        await interaction.response.send_message(f"{user.mention} isn't being mocked rn.", ephemeral=True)
        return

    entry["style"] = style
    save_data()
    await interaction.response.send_message(f"switched {user.mention} to **{style}** mode ✅")


@bot.tree.command(name="unmock", description="Stop mocking a user")
@app_commands.describe(user="The user to stop mocking")
async def unmock(interaction: discord.Interaction, user: discord.Member):
    if not is_owner(interaction.user.id):
        await interaction.response.send_message("nope, owners only 👀", ephemeral=True)
        return

    guild_id = str(interaction.guild_id)
    if guild_id in mocked_users and str(user.id) in mocked_users[guild_id]:
        del mocked_users[guild_id][str(user.id)]
        save_data()
        key = (guild_id, str(user.id))
        if key in _timer_tasks:
            _timer_tasks[key].cancel()
            del _timer_tasks[key]
        await interaction.response.send_message(f"freed {user.mention} from the mock prison 🕊️")
    else:
        await interaction.response.send_message(f"{user.mention} wasn't being mocked.", ephemeral=True)


@bot.tree.command(name="unmockall", description="Unmock everyone in this server")
async def unmockall(interaction: discord.Interaction):
    if not is_owner(interaction.user.id):
        await interaction.response.send_message("nope, owners only 👀", ephemeral=True)
        return

    guild_id = str(interaction.guild_id)
    count = len(mocked_users.get(guild_id, {}))
    mocked_users[guild_id] = {}
    save_data()
    # Cancel all timers for this guild
    for key in [k for k in _timer_tasks if k[0] == guild_id]:
        _timer_tasks[key].cancel()
        del _timer_tasks[key]
    await interaction.response.send_message(f"unmocked **{count}** user(s). peace has been restored 🕊️")


@bot.tree.command(name="mockall", description="Mock everyone in the server (except owners)")
@app_commands.describe(
    intensity="Intensity 1–5",
    style="Style to apply to everyone",
)
@app_commands.choices(intensity=intensity_choices, style=style_choices)
async def mockall(interaction: discord.Interaction, intensity: int = 2, style: str = "uwu"):
    if not is_owner(interaction.user.id):
        await interaction.response.send_message("nope, owners only 👀", ephemeral=True)
        return

    await interaction.response.defer()
    guild_id = str(interaction.guild_id)
    mocked_users.setdefault(guild_id, {})

    count = 0
    for member in interaction.guild.members:
        if member.bot or str(member.id) in OWNER_IDS:
            continue
        mocked_users[guild_id][str(member.id)] = {"intensity": intensity, "style": style}
        count += 1

    save_data()
    await interaction.followup.send(
        f"💀 mocking **{count}** people — style **{style}**, intensity **{intensity}/5**\n"
        f"use `/unmockall` to undo the carnage"
    )


@bot.tree.command(name="mockroulette", description="Randomly picks someone in the server to mock")
@app_commands.describe(intensity="Intensity 1–5", style="Style")
@app_commands.choices(intensity=intensity_choices, style=style_choices)
async def mockroulette(interaction: discord.Interaction, intensity: int = 3, style: str = "uwu"):
    if not is_owner(interaction.user.id):
        await interaction.response.send_message("nope, owners only 👀", ephemeral=True)
        return

    candidates = [
        m for m in interaction.guild.members
        if not m.bot and str(m.id) not in OWNER_IDS and str(m.id) not in mocked_users.get(str(interaction.guild_id), {})
    ]
    if not candidates:
        await interaction.response.send_message("everyone's already mocked lmao", ephemeral=True)
        return

    victim = random.choice(candidates)
    guild_id = str(interaction.guild_id)
    mocked_users.setdefault(guild_id, {})[str(victim.id)] = {"intensity": intensity, "style": style}
    save_data()
    await interaction.response.send_message(
        f"🎰 the roulette lands on... {victim.mention}! style **{style}**, intensity **{intensity}/5** 💀"
    )


@bot.tree.command(name="mocklist", description="Show all mocked users in this server")
async def mocklist(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    users = mocked_users.get(guild_id, {})

    if not users:
        await interaction.response.send_message("nobody's being mocked rn. boring.", ephemeral=True)
        return

    style_icons = {"uwu": "🥺", "spongebob": "🧽", "drunk": "🍺", "zalgo": "👁️", "translator": "🗣️"}
    lines = []
    for uid, data in sorted(users.items(), key=lambda x: -x[1].get("intensity", 1)):
        style     = data.get("style", "uwu")
        intensity = data.get("intensity", 1)
        icon      = style_icons.get(style, "🤓")
        timer_key = (guild_id, uid)
        timer_note = ""
        if timer_key in _timer_tasks and not _timer_tasks[timer_key].done():
            timer_note = " ⏱️"
        lines.append(f"{icon} <@{uid}> — **{style}** intensity **{intensity}/5**{timer_note}")

    embed = discord.Embed(title="🤓 currently mocked", description="\n".join(lines), color=0xFF69B4)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="mockstats", description="See how many messages a user has had mocked")
@app_commands.describe(user="User to check (leave empty for leaderboard)")
async def mockstats(interaction: discord.Interaction, user: discord.Member = None):
    guild_id = str(interaction.guild_id)
    stats = mock_stats.get(guild_id, {})

    if user:
        count = stats.get(str(user.id), 0)
        await interaction.response.send_message(
            f"🤓 {user.mention} has had **{count}** message(s) mocked"
        )
        return

    if not stats:
        await interaction.response.send_message("no stats yet!", ephemeral=True)
        return

    sorted_stats = sorted(stats.items(), key=lambda x: -x[1])[:10]
    lines = [f"**{i+1}.** <@{uid}> — {count} msgs" for i, (uid, count) in enumerate(sorted_stats)]
    embed = discord.Embed(title="📊 mock leaderboard", description="\n".join(lines), color=0xFF69B4)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="mocktimer", description="Mock a user for a set number of minutes")
@app_commands.describe(user="User to mock", minutes="How long to mock them for", intensity="Intensity 1–5", style="Style")
@app_commands.choices(intensity=intensity_choices, style=style_choices)
async def mocktimer(
    interaction: discord.Interaction,
    user: discord.Member,
    minutes: int,
    intensity: int = 2,
    style: str = "uwu",
):
    if not is_owner(interaction.user.id):
        await interaction.response.send_message("nope, owners only 👀", ephemeral=True)
        return
    if minutes < 1 or minutes > 1440:
        await interaction.response.send_message("minutes must be between 1 and 1440 (24h)", ephemeral=True)
        return

    guild_id = str(interaction.guild_id)
    user_id  = str(user.id)
    mocked_users.setdefault(guild_id, {})[user_id] = {"intensity": intensity, "style": style}
    save_data()
    schedule_unmock(guild_id, user_id, minutes * 60)
    await interaction.response.send_message(
        f"⏱️ mocking {user.mention} for **{minutes}m** — style **{style}**, intensity **{intensity}/5**"
    )


@bot.tree.command(name="mockme", description="Preview what your text looks like mocked (only you see this)")
@app_commands.describe(text="Text to preview", intensity="Intensity 1–5", style="Style")
@app_commands.choices(intensity=intensity_choices, style=style_choices)
async def mockme(interaction: discord.Interaction, text: str, intensity: int = 3, style: str = "uwu"):
    result = transform(text, intensity, style)
    await interaction.response.send_message(
        f"**Preview [{style}, intensity {intensity}]:**\n{result}", ephemeral=True
    )

# ── Message listener ──────────────────────────────────────────────────────────

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return

    guild_id = str(message.guild.id)
    user_id  = str(message.author.id)
    entry    = mocked_users.get(guild_id, {}).get(user_id)

    if entry:
        intensity   = entry.get("intensity", 2)
        style       = entry.get("style", "uwu")
        channel     = message.channel
        mocked_text = transform(message.content, intensity, style) if message.content else ""

        files: list[discord.File] = []
        for attachment in message.attachments:
            try:
                files.append(await attachment.to_file())
            except Exception:
                pass

        if mocked_text or files:
            webhook = await get_webhook(channel)
            avatar  = message.author.display_avatar.url

            async def _send(wh: discord.Webhook) -> bool:
                try:
                    await message.delete()
                    await wh.send(
                        content=mocked_text or None,
                        username=message.author.display_name,
                        avatar_url=avatar,
                        files=files,
                    )
                    increment_stat(guild_id, user_id)
                    return True
                except discord.NotFound:
                    _invalidate_webhook(channel.id)
                    return False
                except discord.Forbidden:
                    return False
                except discord.HTTPException as e:
                    log.error("Webhook send error: %s", e)
                    return False

            if webhook and not await _send(webhook):
                # Retry with fresh webhook
                fresh = await get_webhook(channel)
                if fresh:
                    await _send(fresh)

    await bot.process_commands(message)

# ── Startup ───────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    load_data()
    await bot.tree.sync()
    log.info("Logged in as %s (%s)", bot.user, bot.user.id)
    log.info("%d guild(s) with mock data", len(mocked_users))

bot.run(TOKEN)
