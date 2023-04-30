import discord
import requests
import json
from discord.ext import commands, tasks
import sqlite3
import random
import asyncio

conn = sqlite3.connect('balances.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS balances
             (id INTEGER PRIMARY KEY, user_id INTEGER, balance INTEGER)''')

c.execute('''CREATE TABLE IF NOT EXISTS warnings
             (user_id integer, moderator_id integer, reason text)''')

intents = discord.Intents.all()

bot = commands.Bot(command_prefix='PREFIX_HERE', intents=intents)
bot.remove_command('help')

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    update_members.start()

@bot.event
async def on_member_join(member):
    webhook_url = 'WEBHOOK_TOKEN'
    message = f"🎉 {member.mention} has joined, we are now at {len(member.guild.members)} members!"
    data = {"content": message}
    headers = {"Content-Type": "application/json"}
    response = requests.post(webhook_url, data=json.dumps(data), headers=headers)

@tasks.loop(minutes=1)
async def update_members():
    member_count = len(bot.guilds[0].members)
    activity = discord.Activity(type=discord.ActivityType.watching, name=f"{member_count} members")
    await bot.change_presence(activity=activity)

@bot.command(name='help')
async def help_command(ctx):
    await ctx.send(f'{ctx.author.mention}, Here are commands we have to offer.\n**Economy**\nBalance - Checks coins\nWork - Work for coins\nCheck-balance - Checks a user coins.\nLeaderboard - Shows highest users.\nTransfer (user) (amount) - Transfers coins.\n**Giveaway 🎉**\ngiveaway (prize) (winner amount) (duration (minutes))- Starts a giveaway\nreroll - Rerolls a giveaway\n**Fun Commands**\nMeme (imgflip id) (caption 1) (caption 2) - Creates a meme!\nCat - Shows random cats\nDog - Shows random dogs\n**Moderation**\nPurge (message amount) - Delete most messgaes\nSlowmode (delay) - Add slowmode to the channel\nLockdown - Locks down a channel\nUnlockdown - Unlocks a channel\nWarn (user) (reason) - Warns a user\nWarnings (user) - View warnings\nBan (member) - Bans a user\nKick (user) - Kicks a user\nMute (user) (duration) - Mutes a user\nUnmute (user) Unmutes a user\n**Misc Commands**\nuserinfo (user) - Shows information about the user\nserverinfo - Shows info about the server')

# Misc Commands

@bot.command(name='serverinfo')
async def server_info(ctx):
    name = str(ctx.guild.name)
    description = str(ctx.guild.description)
    owner = str(ctx.guild.owner)
    id = str(ctx.guild.id)
    memberCount = str(ctx.guild.member_count)

    icon = str(ctx.guild.icon.url) if ctx.guild.icon else "https://cdn.discordapp.com/embed/avatars/0.png"

    embed = discord.Embed(
        title=name + " Server Information",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=icon)
    embed.add_field(name="Owner", value=owner, inline=True)
    embed.add_field(name="Server ID", value=id, inline=True)
    embed.add_field(name="Member Count", value=memberCount, inline=True)

    await ctx.send(embed=embed)

@bot.command(name='userinfo')
async def userinfo(ctx, *, user:discord.Member = None):      
    date_format = "%a, %d %b %Y %I:%M %p"
    embed = discord.Embed(color=0xdfa3ff, description=user.mention)

    embed.add_field(name="Joined", value=user.joined_at.strftime(date_format))
    members = sorted(ctx.guild.members, key=lambda m: m.joined_at)
    embed.add_field(name="Join position", value=str(members.index(user)+1))
    embed.add_field(name="Registered", value=user.created_at.strftime(date_format))
    return await ctx.send(embed=embed)

# Moderation Commands

@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
async def ban_member(ctx, member: discord.Member, *, reason=None):
    await member.ban(reason=reason)
    await ctx.send(f'{member} has been banned from the server.')

@bot.command(name='kick')
@commands.has_permissions(kick_members=True)
async def kick_member(ctx, member: discord.Member, *, reason=None):
    await member.kick(reason=reason)
    await ctx.send(f'{member} has been kicked from the server.')

@bot.command(name='mute')
@commands.has_permissions(manage_roles=True)
async def mute_member(ctx, member: discord.Member, duration: int, *, reason=None):
    mute_role = discord.utils.get(ctx.guild.roles, name='Muted')
    if not mute_role:
        mute_role = await ctx.guild.create_role(name='Muted')
        for channel in ctx.guild.channels:
            await channel.set_permissions(mute_role, speak=False, send_messages=False)
    await member.add_roles(mute_role, reason=reason)
    await ctx.send(f'{member} has been muted for {duration} minute(s).')
    await asyncio.sleep(duration * 60)
    await member.remove_roles(mute_role, reason='Mute duration expired.')
    await ctx.send(f'{member} has been unmuted.')

@bot.command(name='unmute')
@commands.has_permissions(manage_roles=True)
async def unmute_member(ctx, member: discord.Member, *, reason=None):
    mute_role = discord.utils.get(ctx.guild.roles, name='Muted')
    if not mute_role:
        await ctx.send('No Muted role found.')
        return
    await member.remove_roles(mute_role, reason=reason)
    await ctx.send(f'{member} has been unmuted.')

@bot.command(name='warn')
@commands.has_permissions(kick_members=True)
async def warn(ctx, member: discord.Member, *, reason: str):
    """
    Warn a user and store the warning in the database.
    """
    # Insert the warning into the database
    c.execute("INSERT INTO warnings VALUES (?, ?, ?)", (member.id, ctx.author.id, reason))
    conn.commit()

    # Send a message to the user who was warned
    await member.send(f"You have been warned by {ctx.author.name} for the following reason: {reason}")

    # Send a message to the channel to confirm the warning
    await ctx.send(f"{member.mention} has been warned by {ctx.author.mention} for the following reason: {reason}")

@bot.command(name='warnings')
@commands.has_permissions(kick_members=True)
async def view_warnings(ctx, member: discord.Member):
    """
    View all warnings for a user.
    """
    # Retrieve the warnings from the database
    c.execute("SELECT * FROM warnings WHERE user_id=?", (member.id,))
    rows = c.fetchall()

    # Send a message with the warnings
    if len(rows) == 0:
        await ctx.send(f"{member.mention} has no warnings.")
    else:
        message = f"Warnings for {member.mention}:\n"
        for row in rows:
            moderator = await bot.fetch_user(row[1])
            message += f"- {moderator.name}: {row[2]}\n"
        await ctx.send(message)

@bot.command(name='unlockdown')
@commands.has_permissions(manage_channels=True)
async def unlockdown(ctx):
    channel = ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send(f'{channel.mention} has been unlocked. 🚪🔓')

@bot.command(name='lockdown')
@commands.has_permissions(manage_channels=True)
async def lockdown(ctx):
    """
    Locks down the current channel, preventing users from sending messages.
    """
    # Get the current channel and set the permission overrides for @everyone
    channel = ctx.channel
    role = ctx.guild.default_role
    await channel.set_permissions(role, send_messages=False)

    # Notify users that the channel is in lockdown
    await channel.send(f'🚨 **{channel.name} is now in lockdown.** 🚨\n\nNo one can send messages here until further notice.')

@bot.command(name='purge')
@commands.has_permissions(manage_messages=True)  # restrict the command to users with the "Manage Messages" permission
async def purge_messages(ctx, num_messages: int):
    """
    Delete the specified number of messages from the current channel.
    Example usage: !purge 10
    """
    await ctx.channel.purge(limit=num_messages+1)  # delete the specified number of messages + the command message
    await ctx.send(f'{num_messages} messages deleted. 👍')

@bot.command(name='slowmode')
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, delay: int):
    """
    Enables slowmode in the current channel with the specified delay (in seconds).
    Example usage: !slowmode 30
    """
    await ctx.channel.edit(slowmode_delay=delay)
    await ctx.send(f"Slowmode has been enabled with a delay of {delay} seconds.")

# Fun Commands

@bot.command(name='cat')
async def cat_picture(ctx):
    response = requests.get('https://api.thecatapi.com/v1/images/search')
    data = response.json()
    image_url = data[0]['url']
    await ctx.send(image_url)

@bot.command(name='dog')
async def dog_picture(ctx):
    response = requests.get('https://dog.ceo/api/breeds/image/random')
    data = response.json()
    image_url = data['message']
    await ctx.send(image_url)

@bot.command(name='meme')
async def generate_meme(ctx, meme_id: int, caption1: str, caption2: str):
    """
    Generate a meme with the specified ID and captions.
    Example usage: !meme 181913649 "Caption 1" "Caption 2"
    """
    # Make a request to the Imgflip API to generate the meme
    response = requests.post("https://api.imgflip.com/caption_image",
        data={
            "template_id": meme_id,
            "username": "HELPERBOT",
            "password": "jewsD5@T$r7#W4S",
            "text0": caption1,
            "text1": caption2,
        }
    )

    # Check if the request was successful
    if response.status_code == 200:
        # Get the URL of the generated meme
        meme_url = response.json()["data"]["url"]

        # Send the meme as a message
        await ctx.send(meme_url)
    else:
        await ctx.send("Sorry, I couldn't generate a meme. 😔")

# Giveaway commands

giveaway_channel_id = 1102141288964431984

@bot.command(name='giveaway')
@commands.has_role('Giveaway Hosters')  # restrict the command to users with the "Admin" role
async def start_giveaway(ctx, prize: str, winners: int, duration: str):
    """
    Start a giveaway with the specified prize, number of winners, and duration in minutes.
    Example usage: !giveaway "Discord Nitro" 1 60
    """
    channel = bot.get_channel(giveaway_channel_id)
    message = await channel.send(f'🎉 **GIVEAWAY** 🎉\n\nPrize: {prize}\nWinners: {winners}\nDuration: {duration} minutes\nReact with 🎉 to enter!')
    await message.add_reaction('🎉')

    await asyncio.sleep(int(duration) * 60)

    # get the list of participants (users who reacted with 🎉)
    message = await channel.fetch_message(message.id)
    reactions = [r for r in message.reactions if str(r.emoji) == '🎉']
    if len(reactions) == 0:
        await channel.send('No one entered the giveaway. 😔')
        return
    participants = []
    async for user in reactions[0].users():
        if user != bot.user:
            participants.append(user)

    # select the winners
    if len(participants) < winners:
        winners = len(participants)
    winner_list = random.sample(participants, winners)

    # announce the winners
    winner_str = ''
    for i, winner in enumerate(winner_list):
        winner_str += f'{i+1}. {winner.mention}\n'
    await channel.send(f'🎉 **GIVEAWAY ENDED** 🎉\n\nPrize: {prize}\nWinners: {winner_str}')

@bot.command(name='reroll')
@commands.has_role('Giveaway Hosters')  # restrict the command to users with the "Admin" role
async def reroll(ctx, message_id: int):
    """
    Reroll a giveaway by message ID.
    Example usage: !reroll 123456789012345678
    """
    try:
        message = await ctx.fetch_message(message_id)
    except discord.NotFound:
        await ctx.send('Invalid message ID.')
        return

    # get the list of participants (users who reacted with 🎉)
    reactions = [r for r in message.reactions if str(r.emoji) == '🎉']
    if len(reactions) == 0:
        await ctx.send('No one entered the giveaway. 😔')
        return
    participants = []
    async for user in reactions[0].users():
        if user != bot.user:
            participants.append(user)

    # select the winners
    winners = 1
    if len(participants) < winners:
        winners = len(participants)
    winner_list = random.sample(participants, winners)

    # announce the winners
    winner_str = ''
    for i, winner in enumerate(winner_list):
        winner_str += f'{i+1}. {winner.mention}\n'
    await ctx.send(f'🎉 **GIVEAWAY REROLLED** 🎉\n\nNew Winner: {winner_str}')

# Economy commands

@bot.command(name='balance')
async def balance_command(ctx):
    user_id = ctx.author.id
    c.execute('SELECT balance FROM balances WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    if result is None:
        await ctx.send('You do not have a balance yet.')
    else:
        balance = result[0]
        await ctx.send(f'Your balance is {balance} coins.')

@bot.command(name='work')
async def work_command(ctx):
    user_id = str(ctx.author.id)
    c.execute('SELECT balance FROM balances WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    if result is None:
        await ctx.send('You do not have a balance yet. Use !balance to create one.')
        return
    old_balance = result[0]
    coins = random.randint(10, 100)
    new_balance = old_balance + coins
    c.execute('UPDATE balances SET balance = ? WHERE user_id = ?', (new_balance, user_id))
    conn.commit()
    await ctx.send(f'You worked and earned {coins} coins! Your new balance is {new_balance}.')

@bot.command(name='check-balance')
async def check_balance_command(ctx, member: discord.Member):
    user_id = member.id
    c.execute('SELECT balance FROM balances WHERE user_id = ?', (user_id,))
    balance = c.fetchone()
    if balance is None:
        await ctx.send(f"{member.mention} does not have a balance yet.")
    else:
        await ctx.send(f"{member.mention}'s balance is {balance[0]} coins.")

@bot.command(name='leaderboard')
async def leaderboard_command(ctx):
    conn = sqlite3.connect('balances.db')
    c = conn.cursor()
    c.execute('SELECT user_id, balance FROM balances ORDER BY balance DESC')
    leaderboard = c.fetchall()
    conn.close()

    leaderboard_str = 'Leaderboard:\n'
    for i, (user_id, balance) in enumerate(leaderboard, start=1):
        user = await bot.fetch_user(user_id)
        leaderboard_str += f'{i}. {user.name}: {balance} coins\n'
    await ctx.send(leaderboard_str)

@bot.command(name='transfer')
async def transfer_command(ctx, recipient: discord.Member, amount: int):
    if recipient.bot:
        await ctx.send("Sorry, you can't transfer coins to bots.")
        return
    if amount < 1:
        await ctx.send("You must transfer at least 1 coin.")
        return
    user_id = ctx.author.id
    recipient_id = recipient.id
    conn = sqlite3.connect('balances.db')
    c = conn.cursor()
    c.execute('SELECT balance FROM balances WHERE user_id = ?', (user_id,))
    sender_balance = c.fetchone()
    if not sender_balance or sender_balance[0] < amount:
        await ctx.send("Sorry, you don't have enough coins to make this transfer.")
        return
    c.execute('UPDATE balances SET balance = balance - ? WHERE user_id = ?', (amount, user_id))
    c.execute('UPDATE balances SET balance = balance + ? WHERE user_id = ?', (amount, recipient_id))
    conn.commit()
    await ctx.send(f"You have transferred {amount} coins to {recipient.mention}.")

bot.run('BOT_TOKEN_HERE')
