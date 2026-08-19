import discord
from discord.ext import commands
from discord import app_commands
import json
import os

# ============================================================
# CONFIGURATION
# ============================================================

# Your Discord bot token should be stored as an environment
# variable/Secret named DISCORD_TOKEN.
TOKEN = os.getenv("DISCORD_TOKEN")

CONFIG_FILE = "config.json"


# ============================================================
# CONFIG FILE FUNCTIONS
# ============================================================

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(config, file, indent=4)


config = load_config()


# ============================================================
# BOT SETUP
# ============================================================

intents = discord.Intents.default()

# Required for detecting when someone joins
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# ============================================================
# VERIFICATION BUTTON
# ============================================================

class VerifyView(discord.ui.View):

    def __init__(self):
        # None means the button never expires
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Verify",
        style=discord.ButtonStyle.green,
        custom_id="verification_button"
    )
    async def verify_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        guild = interaction.guild
        member = interaction.user

        # Make sure this is being used in a server
        if guild is None:
            await interaction.response.send_message(
                "This button can only be used inside a server.",
                ephemeral=True
            )
            return

        guild_id = str(guild.id)

        # Get this server's configuration
        guild_config = config.get(guild_id)

        if not guild_config:
            await interaction.response.send_message(
                "Verification has not been configured yet.",
                ephemeral=True
            )
            return

        join_role_id = guild_config.get("join_role")
        verify_role_id = guild_config.get("verify_role")

        # Make sure both roles have been configured
        if not join_role_id or not verify_role_id:
            await interaction.response.send_message(
                "Verification has not been fully configured yet.",
                ephemeral=True
            )
            return

        # Find the roles
        join_role = guild.get_role(int(join_role_id))
        verify_role = guild.get_role(int(verify_role_id))

        # Make sure the verification role still exists
        if verify_role is None:
            await interaction.response.send_message(
                "The verification role no longer exists.",
                ephemeral=True
            )
            return

        # Don't verify someone twice
        if verify_role in member.roles:
            await interaction.response.send_message(
                "You are already verified.",
                ephemeral=True
            )
            return

        try:
            # Give the verified role
            await member.add_roles(
                verify_role,
                reason="Member completed verification"
            )

            # Remove the unverified/join role
            if join_role and join_role in member.roles:
                await member.remove_roles(
                    join_role,
                    reason="Member completed verification"
                )

            # Only the person who clicked can see this
            await interaction.response.send_message(
                "✅ Verification successfully complete!",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "I couldn't change your roles. "
                "Please contact a server administrator.",
                ephemeral=True
            )

        except Exception as error:
            print(f"Verification error: {error}")

            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Something went wrong while verifying you.",
                    ephemeral=True
                )


# ============================================================
# BOT READY
# ============================================================

@bot.event
async def on_ready():

    print("========================================")
    print(f"Bot logged in as: {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print("========================================")

    # Sync slash commands
    try:
        synced = await bot.tree.sync()

        print(f"Synced {len(synced)} slash commands:")

        for command in synced:
            print(f"  /{command.name}")

    except Exception as error:
        print(f"Failed to sync slash commands: {error}")


# ============================================================
# SETUP PERSISTENT VIEW
# ============================================================

async def setup_hook():
    # Makes the verification button continue working
    # after the bot restarts.
    bot.add_view(VerifyView())


# Attach setup hook to the bot
bot.setup_hook = setup_hook


# ============================================================
# MEMBER JOIN
# ============================================================

@bot.event
async def on_member_join(member: discord.Member):

    guild_id = str(member.guild.id)

    # Get this server's settings
    guild_config = config.get(guild_id)

    if not guild_config:
        print(
            f"{member} joined {member.guild.name}, "
            "but the server has not been configured."
        )
        return

    # Get the configured join role
    join_role_id = guild_config.get("join_role")

    if not join_role_id:
        print(
            f"{member} joined {member.guild.name}, "
            "but no join role has been configured."
        )
        return

    # Find the role
    role = member.guild.get_role(int(join_role_id))

    if role is None:
        print(
            f"The configured join role does not exist "
            f"in {member.guild.name}."
        )
        return

    try:
        # Give the new member the join role
        await member.add_roles(
            role,
            reason="Automatic verification role"
        )

        print(
            f"Gave '{role.name}' to {member} "
            f"in {member.guild.name}"
        )

    except discord.Forbidden:
        print(
            f"Could not give '{role.name}' to {member}. "
            "Make sure the bot's role is above the join role."
        )

    except Exception as error:
        print(f"Error giving join role: {error}")


# ============================================================
# /joinrole
# ============================================================

@bot.tree.command(
    name="joinrole",
    description="Choose the role new members receive when they join."
)
@app_commands.describe(
    role="Choose the role new members receive when they join."
)
@app_commands.checks.has_permissions(administrator=True)
async def joinrole(
    interaction: discord.Interaction,
    role: discord.Role
):

    if interaction.guild is None:
        await interaction.response.send_message(
            "This command can only be used inside a server.",
            ephemeral=True
        )
        return

    guild_id = str(interaction.guild.id)

    # Create settings for this server if necessary
    if guild_id not in config:
        config[guild_id] = {}

    # Save the selected role
    config[guild_id]["join_role"] = role.id
    save_config(config)

    await interaction.response.send_message(
        f"✅ The join role is now {role.mention}.\n\n"
        "New members will automatically receive this role "
        "when they join.",
        ephemeral=True
    )


# ============================================================
# /verifyrole
# ============================================================

@bot.tree.command(
    name="verifyrole",
    description="Choose the role members receive after verification."
)
@app_commands.describe(
    role="Choose the role members receive after verification."
)
@app_commands.checks.has_permissions(administrator=True)
async def verifyrole(
    interaction: discord.Interaction,
    role: discord.Role
):

    if interaction.guild is None:
        await interaction.response.send_message(
            "This command can only be used inside a server.",
            ephemeral=True
        )
        return

    guild_id = str(interaction.guild.id)

    # Create settings for this server if necessary
    if guild_id not in config:
        config[guild_id] = {}

    # Save the selected role
    config[guild_id]["verify_role"] = role.id
    save_config(config)

    await interaction.response.send_message(
        f"✅ The verification role is now {role.mention}.\n\n"
        "Members will receive this role after pressing Verify.",
        ephemeral=True
    )


# ============================================================
# /verifymessage
# ============================================================

@bot.tree.command(
    name="verifymessage",
    description="Send the server verification message."
)
@app_commands.checks.has_permissions(administrator=True)
async def verifymessage(interaction: discord.Interaction):

    if interaction.guild is None:
        await interaction.response.send_message(
            "This command can only be used inside a server.",
            ephemeral=True
        )
        return

    guild_id = str(interaction.guild.id)

    guild_config = config.get(guild_id)

    # Make sure the server has settings
    if not guild_config:
        await interaction.response.send_message(
            "❌ Verification has not been configured.\n\n"
            "Use /joinrole and /verifyrole first.",
            ephemeral=True
        )
        return

    # Make sure /joinrole has been used
    if not guild_config.get("join_role"):
        await interaction.response.send_message(
            "❌ You need to use /joinrole first.",
            ephemeral=True
        )
        return

    # Make sure /verifyrole has been used
    if not guild_config.get("verify_role"):
        await interaction.response.send_message(
            "❌ You need to use /verifyrole first.",
            ephemeral=True
        )
        return

    # Send the verification message
    await interaction.response.send_message(
        "Click below to verify and see the rest of the server.",
        view=VerifyView()
    )


# ============================================================
# SLASH COMMAND ERROR HANDLER
# ============================================================

@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError
):

    # Someone without Administrator permission used
    # /joinrole, /verifyrole, or /verifymessage
    if isinstance(error, app_commands.MissingPermissions):

        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ You need Administrator permission to use this command.",
                ephemeral=True
            )

        return

    print(f"Slash command error: {error}")

    if not interaction.response.is_done():
        await interaction.response.send_message(
            "❌ An error occurred while running that command.",
            ephemeral=True
        )


# ============================================================
# START BOT
# ============================================================

if not TOKEN:
    print(
        "ERROR: DISCORD_TOKEN was not found.\n"
        "Create an environment variable/Secret named "
        "DISCORD_TOKEN and put your bot token there."
    )
else:
    bot.run(TOKEN)
