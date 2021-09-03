import asyncio
import os
import json
import random
import string

import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Register intents
intents = discord.Intents.default()
intents.members = True

# Instantiate bot
bot = commands.Bot(command_prefix='!', intents=intents)


# Data schema
'''
{ author.id :
    {
        name : str
        choices :  tuple(2)  
    }
}
'''

votes = {}
spin_confirmed_by = None
begin_confirmed_by = None
spinning = False


# Helper functions
def get_random_gif():
    gifs = []
    for (dirpath, dirnames, filenames) in os.walk('gifs'):
        gifs.extend(filenames)
        break

    randfile = random.randint(0, len(gifs) - 1)
    return 'gifs' + os.sep + gifs[randfile]


def get_user_votes(user_id, user_name):
    response = f'**{user_name}**\'s choices:\n'
    if user_id in votes.keys() and len(votes[user_id]["choices"]) > 0:
        for choice in votes[user_id]["choices"]:
            response += f'- {choice}\n'
    else:
        response += 'Nothing yet.\n'

    return response


def get_alliances():
    response = f'__**Current alliances**__:\n'

    standings = {}
    total = 0

    if len(votes.keys()) > 0:
        # Tally votes
        for user in votes.keys():
            for choice in votes[user]["choices"]:
                if choice in standings.keys():
                    standings[choice] += 1
                else:
                    standings[choice] = 1
                total += 1

        # Sort and display standings
        for choice, tally in sorted(standings.items(), key=lambda item: item[1], reverse=True):
            chance = (tally / total) * 100
            response += f' - {choice}: {tally} vote{"s" if tally > 1 else ""} (_{chance:.2f}%_)\n'

    else:
        response += 'Nobody has voted yet.\n'

    return response


def get_partial_votes():
    partials = []
    for user in votes.keys():
        if len(votes[user]["choices"]) == 1:
            partials.append(votes[user]['name'])

    return partials


def get_voter_names():
    voters = []
    for user in votes.keys():
        voters.append(votes[user]["name"])

    return voters


def roll_winner():
    # First gather choices
    choices = []
    for user in votes.keys():
        for choice in votes[user]["choices"]:
            choices.append(choice)

    # Roll random choice
    winner = choices[random.randint(0, len(choices) - 1)]

    return winner


def clear_confirmation():
    # This should be called any time a change to the vote dictionary is made.
    global spin_confirmed_by
    spin_confirmed_by = None


# Here be bot commands
@bot.command(name='rules', help='Show the divine commandments that dictate the terms by which each wheel participant '
                                'must adhere to.')
async def show_rules(ctx):
    await ctx.send('1. Thou shalt not vote for the same option twice.\n'
                   '2. Thou shalt not vote for two options in the same franchise.\n'
                   '3. Thou hath permission to form alliances with other voters.\n'
                   '4. Thou shalt not receive a vote if thou refuses to comply with Divine Providence.')


@bot.command(name='begin', help='Clear any pre-existing wheel data and start adding those suggestions!')
async def begin_wheel(ctx):
    # Clear any old data
    global votes
    global spinning
    global begin_confirmed_by
    if begin_confirmed_by is None:
        begin_confirmed_by = ctx.author.id
        await ctx.send("Wait for confirmation.")
    elif begin_confirmed_by == ctx.author.id:
        await ctx.send("Someone else confirm.")
    else:
        spinning = False
        votes = {}
        clear_confirmation()

        await ctx.send('A new wheel night is in session! Cast your votes by using the **!add [choice name]** command, '
                       'and once everyone has made their selections, use **!spin** to spin!\n'
                       'Refresh your knowledge of the Divine Commandments by using **!rules**, and if you\'re stuck '
                       'try using **!help** (or I guess ask Matt if you _must_).\n\n'
                       '**NOTE** that the !begin command clears all saved data, so only use it to clear the previous '
                       'night\'s selections.')

        save_file()


@bot.command(name='spin', help='After everyone has picked, spin the wheel and reveal the divinely-chosen winner.')
async def spin_wheel(ctx):
    # Pre-spin checks
    partials = get_partial_votes()
    if len(votes) == 0:
        await ctx.send('Nobody has voted yet..?')

    elif len(partials) != 0:
        response = f'The following people haven\'t made two choices yet:\n'
        for partial in partials:
            response += f' - {partial}\n'
        await ctx.send(response)

    else:
        global spin_confirmed_by
        global spinning
        if spin_confirmed_by is None and not spinning:
            voters = get_voter_names()

            response = f'**Ready to spin?** Here is a list of everyone who has entered their choices:\n'
            for voter in voters:
                response += f' - {voter}\n'
            response += f'\nIf that\'s everyone, get _another person_ to confirm the spin by calling the **!spin** ' \
                        f'command again. Otherwise, make sure everyone\'s votes are in!\n'

            spin_confirmed_by = ctx.author.id
            await ctx.send(response)

        elif spin_confirmed_by == ctx.author.id and not spinning:
            await ctx.send(f'{ctx.author.name}, you need to get _someone else_ to confirm the spin.')

        else:
            if not spinning:
                spinning = True
                await ctx.send('Time to spin the wheel!')
                await ctx.send(file=discord.File(get_random_gif()))
                await asyncio.sleep(3)
                await ctx.send('And the winner is...')
                await asyncio.sleep(1)
                await ctx.send(f'{roll_winner()}!')
                clear_confirmation()


@bot.command(name='add', aliases=['vote'], help='Add one of your two votes.')
async def add_vote(ctx, *, vote):
    user_id = ctx.author.id
    user_name = ctx.author.name
    fmt_vote = string.capwords(vote)

    update_choices = False
    if user_id in votes.keys():
        if fmt_vote in votes[user_id]["choices"]:
            await ctx.send(f'{user_name} you _KNOW_ you can\'t vote for the same thing twice.')
        elif len(votes[user_id]["choices"]) == 2:
            await ctx.send(f'Sorry {user_name}, you already have two votes. Use **!clear** to reset both your '
                           f'choices, or **!clear [choice name]** to remove a specific one.')
        else:
            update_choices = True
    else:
        votes[user_id] = {"name": user_name, "choices": []}
        update_choices = True

    if update_choices:
        votes[user_id]["choices"].append(fmt_vote)
        clear_confirmation()
        await ctx.send(f'Adding option {fmt_vote} for {user_name}.')

    save_file()


@bot.command(name='me', aliases=['mine'], help='Check what you\'re current votes are.')
async def individual_votes(ctx):
    user_id = ctx.author.id
    user_name = ctx.author.name

    await ctx.send(get_user_votes(user_id, user_name))


@bot.command(name='everyone', aliases=['all'], help='Check what everyone is currently voting for.')
async def all_votes(ctx):
    response = f'__**Current votes**__:\n'
    if len(votes.keys()) > 0:
        for user_id in votes.keys():
            response += get_user_votes(user_id, votes[user_id]["name"]) + '\n'
    else:
        response += 'Nobody has voted yet.\n'

    await ctx.send(response)


@bot.command(name='clear', aliases=['delete, remove'], help='Clear one or both of your current votes.')
async def clear_vote(ctx, *, choice=None):
    user_id = ctx.author.id
    user_name = ctx.author.name

    # Check for any votes to begin with
    if user_id not in votes.keys():
        await ctx.send(f'No votes found for {user_name}.')
        return

    # Otherwise, clear for parameters
    if choice is None:
        votes[user_id]["choices"] = []
        response = f'Cleared all votes for {user_name}.'
        clear_confirmation()

    else:
        fmt_choice = string.capwords(choice)
        if fmt_choice in votes[user_id]["choices"]:
            votes[user_id]["choices"].remove(fmt_choice)
            response = f'Removed {fmt_choice} from {user_name}\'s votes.'
            clear_confirmation()
        else:
            response = f'No vote for {fmt_choice} found, check your spelling and try again. Use **!me** to check ' \
                       f'your current choices.'

    await ctx.send(response)
    save_file()


@bot.command(name='proxyvote', aliases=['proxyadd'], help='Vote on behalf of someone without discord..')
async def proxy_add(ctx, proxy, *, vote):
    user_id = string.capwords(proxy)
    user_name = string.capwords(proxy)
    fmt_vote = string.capwords(vote)

    update_choices = False
    if user_id in votes.keys():
        if fmt_vote in votes[user_id]["choices"]:
            await ctx.send(f'{user_name} you _KNOW_ you can\'t vote for the same thing twice.')
        elif len(votes[user_id]["choices"]) == 2:
            await ctx.send(f'Sorry {user_name}, you already have two votes. Use **!clear** to reset both your '
                           f'choices, or **!clear [choice name]** to remove a specific one.')
        else:
            update_choices = True
    else:
        votes[user_id] = {"name": user_name, "choices": []}
        update_choices = True

    if update_choices:
        votes[user_id]["choices"].append(fmt_vote)
        clear_confirmation()
        await ctx.send(f'Adding option {fmt_vote} for {user_name}.')

    save_file()


@bot.command(name='proxyclear', aliases=['proxydelete, proxyremove'], help='Clear a proxy vote.')
async def clear_vote(ctx, proxy, *, choice=None):
    user_id = string.capwords(proxy)
    user_name = string.capwords(proxy)

    # Check for any votes to begin with
    if user_id not in votes.keys():
        await ctx.send(f'No votes found for {user_name}.')
        return

    # Otherwise, clear for parameters
    if choice is None:
        votes[user_id]["choices"] = []
        response = f'Cleared all votes for {user_name}.'
        clear_confirmation()

    else:
        fmt_choice = string.capwords(choice)
        if fmt_choice in votes[user_id]["choices"]:
            votes[user_id]["choices"].remove(fmt_choice)
            response = f'Removed {fmt_choice} from {user_name}\'s votes.'
            clear_confirmation()
        else:
            response = f'No vote for {fmt_choice} found, check your spelling and try again. Use **!me** to check ' \
                       f'your current choices.'

    await ctx.send(response)
    save_file()


@bot.command(name='alliances', aliases=['standings', 'rankings'], help='Show the current standings of all votes.')
async def alliances(ctx):
    await ctx.send(get_alliances())


def save_file():
    with open('data.json', 'w') as f:
        json.dump(votes, f, indent=4)


def load_file():
    try:
        with open('data.json', 'r') as f:
            global votes
            votes = json.load(f)
    except FileNotFoundError:
        print("data.json not found")


@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')
    load_file()
    print(f'Votes loaded from file:\n{votes}')


# Run Forrest, run!
bot.run(TOKEN)
