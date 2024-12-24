import platform
import json
import shelve

import nextcord
from nextcord import SlashOption
from nextcord.ext import commands

from logger import get_custom_logger
from templates import MessageTemplates

log = get_custom_logger(__name__)
embed = MessageTemplates()

# Load configuration
with open('config.json', 'r') as file:
    config = json.load(file)

intents = nextcord.Intents.all()
client = commands.Bot(intents=intents)

WHITELIST_ROLE_ID = config['whitelist']  # The integer role ID for the whitelist role
WHITELIST_DB = "whitelist_data.db"  # Shelve database file name (e.g., "whitelist_data.db")


# Helper function to ensure our DB has the structures we need
def init_db():
    with shelve.open(WHITELIST_DB) as db:
        if "invites" not in db:
            db["invites"] = {}
        if "invited_by" not in db:
            db["invited_by"] = {}


# Helper function to evaluate a user's profile
def evaluate_user_profile(guild: nextcord.Guild, member: nextcord.Member):
    """
    Evaluates the user's profile and returns a dictionary with raw data.

    Returns:
        dict: {
            'is_whitelisted': bool,
            'is_founder': bool,
            'invites_left': int,
            'inviter_id': str or None
        }
    """
    with shelve.open(WHITELIST_DB, writeback=True) as db:
        invites_dict = db["invites"]
        invited_by_dict = db["invited_by"]

        user_id_str = str(member.id)
        is_whitelisted = False
        is_founder = False
        invites_left = 0
        inviter_id = None

        whitelist_role = guild.get_role(WHITELIST_ROLE_ID)
        if not whitelist_role:
            log.error("Whitelist role not found in the guild.")
            return {
                'is_whitelisted': False,
                'is_founder': False,
                'invites_left': 0,
                'inviter_id': None
            }

        if whitelist_role in member.roles:
            is_whitelisted = True
            invites_left = invites_dict.get(user_id_str, 0)

            if user_id_str not in invited_by_dict:
                # Initialize as founder
                invited_by_dict[user_id_str] = "founder"
                invites_dict[user_id_str] = invites_dict.get(user_id_str, 1)
                is_founder = True
                inviter_id = "founder"
                log.info(f'Initialized founder: {member} with 1 invite.')
            else:
                inviter_id = invited_by_dict[user_id_str]
                if inviter_id == "founder":
                    is_founder = True
        else:
            is_whitelisted = False

        # Save changes if any initialization occurred
        db["invites"] = invites_dict
        db["invited_by"] = invited_by_dict

        return {
            'is_whitelisted': is_whitelisted,
            'is_founder': is_founder,
            'invites_left': invites_left,
            'inviter_id': inviter_id
        }


# Bot startup
@client.event
async def on_ready():
    await client.change_presence(activity=nextcord.Game(name='Hello World!'))
    log.info('Bot is ready')
    log.info('======================================')
    log.info(f'Logged in as {client.user} ({client.user.id})')
    log.info(f'Currently running nextcord {nextcord.__version__} on Python {platform.python_version()}')
    log.info('======================================')

    # Initialize the shelve DB on startup
    init_db()

    # Optional: Initialize all existing whitelist members as founders
    # Uncomment the following block if you want to bulk initialize at startup
    '''
    guilds = client.guilds
    for guild in guilds:
        whitelist_role = guild.get_role(WHITELIST_ROLE_ID)
        if not whitelist_role:
            log.warning(f"Whitelist role not found in guild: {guild.name}")
            continue

        with shelve.open(WHITELIST_DB, writeback=True) as db:
            invites_dict = db["invites"]
            invited_by_dict = db["invited_by"]
            for member in guild.members:
                user_id_str = str(member.id)
                if whitelist_role in member.roles and user_id_str not in invited_by_dict:
                    invited_by_dict[user_id_str] = "founder"
                    invites_dict[user_id_str] = invites_dict.get(user_id_str, 1)
                    log.info(f'Initialized founder: {member} with 1 invite.')
            db["invites"] = invites_dict
            db["invited_by"] = invited_by_dict
    '''


@client.slash_command(name='핑', description='봇의 핑을 확인합니다.')
async def ping(ctx):
    await ctx.send(embed=embed.success(f'퐁! {round(client.latency * 1000)}ms'), ephemeral=True)


########################################################################
# WHITELIST COMMAND
########################################################################
@client.slash_command(name='화이트리스트', description='1회 초대를 사용해 다른 멤버를 화이트리스트합니다.')
async def whitelist(
        ctx,
        user: nextcord.Member = SlashOption(
            name="사용자",
            description="화이트리스트에 추가할 사용자를 선택하세요.",
            required=True
        )
):
    """Give the specified user a whitelist role if the invoker has an invite available."""
    guild = ctx.guild
    if not guild:
        await ctx.send(embed=embed.error("명령어는 서버 내에서만 사용할 수 있습니다."), ephemeral=True)
        return

    # Fetch role and member objects
    whitelist_role = guild.get_role(WHITELIST_ROLE_ID)
    if not whitelist_role:
        await ctx.send(embed=embed.error('화이트리스트 역할을 찾을 수 없습니다.'), ephemeral=True)
        return

    # Check if target is not a bot
    if user.bot:
        await ctx.send(embed=embed.error('봇을 화이트리스트에 추가할 수 없습니다.'), ephemeral=True)
        return

    invoker_member = guild.get_member(ctx.user.id)
    target_member = guild.get_member(user.id)

    if not invoker_member:
        await ctx.send(embed=embed.error('초대한 사용자를 찾을 수 없습니다.'), ephemeral=True)
        return

    if not target_member:
        await ctx.send(embed=embed.error('대상 사용자를 찾을 수 없습니다.'), ephemeral=True)
        return

    # Check if the invoker has the whitelist role
    if whitelist_role not in invoker_member.roles:
        await ctx.send(embed=embed.error('화이트리스트 권한이 없습니다!'), ephemeral=True)
        return

    # Attempt to retrieve the DB data
    with shelve.open(WHITELIST_DB, writeback=True) as db:
        invites_dict = db["invites"]
        invited_by_dict = db["invited_by"]

        invoker_id_str = str(invoker_member.id)
        target_id_str = str(target_member.id)

        # Initialize invoker in DB if not present (as founder)
        if invoker_id_str not in invited_by_dict:
            invited_by_dict[invoker_id_str] = "founder"
            invites_dict[invoker_id_str] = invites_dict.get(invoker_id_str, 1)
            log.info(f'Initialized founder: {invoker_member} with 1 invite.')

        # Check if the invoker has any invites left
        invoker_invites = invites_dict.get(invoker_id_str, 0)

        if invoker_invites < 1:
            await ctx.send(embed=embed.error('초대 가능한 횟수가 없습니다.'), ephemeral=True)
            return

        # Check if the target is already whitelisted
        if whitelist_role in target_member.roles:
            await ctx.send(embed=embed.error(f'{target_member.mention}님은 이미 화이트리스트입니다.'), ephemeral=True)
            return

        # Prevent users from whitelisting themselves
        if target_member.id == invoker_member.id:
            await ctx.send(embed=embed.error('자신을 화이트리스트에 추가할 수 없습니다.'), ephemeral=True)
            return

        # Everything OK: reduce the invoker's invites by 1
        invites_dict[invoker_id_str] = invoker_invites - 1

        # Mark who invited the target
        invited_by_dict[target_id_str] = invoker_id_str

        # Give whitelist role
        try:
            await target_member.add_roles(whitelist_role, reason="Whitelist invitation")
            sucess_embed = embed.success(f'{invoker_member.mention}님이 {target_member.mention}님에게 화이트리스트 역할을 부여했습니다.')
            sucess_embed.set_footer(text=f'남은 초대 횟수: {invites_dict[invoker_id_str]}')
            await ctx.send(embed=sucess_embed, ephemeral=True)
            log.info(f'{invoker_member} invited {target_member} to whitelist.')
        except Exception as e:
            log.error(f'Failed to add whitelist role to {target_member}: {e}')
            await ctx.send(embed=embed.error('화이트리스트 역할을 부여하는 데 실패했습니다.'), ephemeral=True)
            return

        # Save changes
        db["invites"] = invites_dict
        db["invited_by"] = invited_by_dict


########################################################################
# ADMIN COMMAND: ADD INVITES
########################################################################
@client.slash_command(name='초대부여', description='특정 유저 또는 전체 유저에게 화이트리스트 초대를 추가합니다. (관리자 전용)')
@commands.has_permissions(administrator=True)
async def give_invites(
        ctx,
        count: int = SlashOption(
            name="횟수",
            description="부여할 초대 횟수",
            required=True
        ),
        user: nextcord.Member = SlashOption(
            name="대상",
            description="초대를 줄 대상 (비워두면 전체)",
            required=False
        )
):
    guild = ctx.guild
    if not guild:
        await ctx.send(embed=embed.error("명령어는 서버 내에서만 사용할 수 있습니다."), ephemeral=True)
        return

    if count <= 0:
        await ctx.send(embed=embed.error("0보다 큰 숫자를 입력해주세요."), ephemeral=True)
        return

    with shelve.open(WHITELIST_DB, writeback=True) as db:
        invites_dict = db["invites"]

        if user:
            # Add invites to a specific user
            user_id_str = str(user.id)
            invites_dict[user_id_str] = invites_dict.get(user_id_str, 0) + count
            await ctx.send(embed=embed.success(f"{user.mention} 님에게 {count}개의 초대를 추가했습니다."), ephemeral=True)
            log.info(f'Granted {count} invites to {user}.')
        else:
            # Add invites to everyone in the server
            for member in guild.members:
                invites_dict[str(member.id)] = invites_dict.get(str(member.id), 0) + count
            await ctx.send(embed=embed.success(f"서버 내 모든 사용자에게 {count}개의 초대를 추가했습니다."), ephemeral=True)
            log.info(f'Granted {count} invites to all members in guild: {guild.name}.')

        # Save changes
        db["invites"] = invites_dict


########################################################################
# PROFILE COMMAND
########################################################################

@client.slash_command(name='프로필', description='자신 또는 다른 사용자의 프로필을 확인합니다.')
async def profile_command(
        ctx,
        user: nextcord.Member = SlashOption(
            name="사용자",
            description="프로필을 확인할 사용자를 입력해 주세요.",
            required=False
        )
):
    """
    Displays how many invites a user has left, and who invited them.
    - If user is not in the DB but DOES have the whitelist role, treat them as founder.
    - If user does NOT have the whitelist role, they are not part of the community.
    """
    # If no user provided, default to the person invoking the command
    target_member = user if user else ctx.user

    guild = ctx.guild
    if not guild:
        await ctx.send(embed=embed.error("명령어는 서버 내에서만 사용할 수 있습니다."), ephemeral=True)
        return

    # Evaluate the user's profile
    profile_data = evaluate_user_profile(guild, target_member)

    # Unpack the raw data
    is_whitelisted = profile_data['is_whitelisted']
    is_founder = profile_data['is_founder']
    invites_left = profile_data['invites_left']
    inviter_id = profile_data['inviter_id']

    # Custom logic based on raw data
    if not is_whitelisted:
        await ctx.send(embed=embed.error(f"{target_member.mention}님은 화이트리스트에 없습니다."), ephemeral=True)
        return

    profile_embed = nextcord.Embed(title="", color=0x2B2D31)
    profile_embed.set_author(name=f"{target_member.display_name}님의 프로필", icon_url=target_member.avatar.url)

    if is_founder:
        profile_embed.description = "`초기 멤버`"
    else:
        profile_embed.description = f"초대자: <@{inviter_id}>"

    # get all memebers who have been invited by the target_member
    with shelve.open(WHITELIST_DB) as db:
        invited_by_dict = db["invited_by"]
        # Find all user IDs where inviter_id == target_member.id
        invited_member_ids = [user_id for user_id, inviter in invited_by_dict.items() if
                              inviter == str(target_member.id)]
        invited_members = [guild.get_member(int(user_id)) for user_id in invited_member_ids]
        invited_mentions = [member.mention for member in invited_members if member]

    if invited_mentions:
        profile_embed.add_field(name="초대한 멤버", value="\n".join(invited_mentions), inline=False)
    profile_embed.set_footer(text=f"남은 초대 횟수: {invites_left}")

    await ctx.send(embed=profile_embed, ephemeral=True)


########################################################################
# RUN THE BOT
########################################################################
try:
    client.run(config['token'])
except nextcord.errors.LoginFailure:
    log.fatal('Authentication to Discord failed.')
    exit()
