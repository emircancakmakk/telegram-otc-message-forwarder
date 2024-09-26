from telegram import Update, User
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes
from telegram.ext import filters
from supabase import create_client, Client
from dotenv import load_dotenv
import logging
import requests
import os

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Load environment variables from .env file
load_dotenv()

# Supabase setup
SUPABASE_URL = os.getenv("SUPABASE_URL")  # Replace with your Supabase URL
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # Replace with your Supabase API key
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize admin ID and bot token
admin_ids = [6119547076, 7127199179]  # Replace with your Telegram user ID to restrict certain commands
bot_token = os.getenv("TELEGRAM_BOT_TOKEN")  # Replace with your bot token

# Remove webhook before starting
def remove_webhook():
    url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            logging.info("Webhook removed successfully.")
        else:
            logging.error("Failed to remove webhook.")
    except Exception as e:
        logging.error(f"Error removing webhook: {e}")

remove_webhook()

# Load recipients from Supabase
def load_recipients():
    recipients = {}
    try:
        response = supabase.table("recipients").select("*").execute()
        for recipient in response.data:
            recipients[recipient["user_id"]] = {
                "chat_id": recipient["chat_id"],
                "username": recipient["username"],
                "status": recipient["status"]  # Adding status to recipients dictionary
            }
        logging.info("Recipients loaded successfully.")
    except Exception as e:
        logging.error(f"Error loading recipients: {e}")
    return recipients

# Save a recipient to Supabase
def save_recipient(user_id, chat_id, username, status=True):
    try:
        supabase.table("recipients").insert({
            "user_id": user_id,
            "chat_id": chat_id,
            "username": username,
            "status": status  # Save recipient with status
        }).execute()
        logging.info(f"Recipient @{username} saved successfully.")
    except Exception as e:
        logging.error(f"Error saving recipient: {e}")

# Update recipient status in Supabase
def update_recipient_status(user_id, status):
    try:
        supabase.table("recipients").update({"status": status}).eq("user_id", user_id).execute()
        status_text = "enabled" if status else "disabled"
        logging.info(f"Recipient with ID {user_id} {status_text} successfully.")
    except Exception as e:
        logging.error(f"Error updating recipient status: {e}")

# Remove a recipient from Supabase
def remove_recipient(user_id):
    try:
        supabase.table("recipients").delete().eq("user_id", user_id).execute()
        logging.info(f"Recipient with ID {user_id} removed successfully.")
    except Exception as e:
        logging.error(f"Error removing recipient: {e}")

# Check if user is admin
def is_admin(user_id):
    return user_id in admin_ids

# Custom welcome message when bot is started
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if is_admin(update.effective_user.id):
        # Message for admins
        welcome_message = (
            "Welcome, Admin!\n"
            "This bot is configured to forward OTC messages to designated recipients.\n"
            "Use /help to view all available commands.\n"
            "Use /enable_recipient <user_id> or /disable_recipient <user_id> to manage recipient status."
        )
    else:
        # Message for regular users
        welcome_message = (
            "Welcome to the OTC Forwarding Bot!\n"
            "This bot will send OTC messages securely to the intended recipients.\n"
            "You have been added as a recipient automatically."
        )
        # Automatically add user as recipient if not already added
        await add_recipient_auto(update, context)
    await update.message.reply_text(welcome_message)

# Automatically add recipient on first interaction
async def add_recipient_auto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id
    username = user.username or f"ID:{user_id}"  # Use username if available, else user ID as string

    recipients = load_recipients()
    if user_id not in recipients:
        save_recipient(user_id, user_id, username)
        # Notify admins about the new recipient added
        for admin_id in admin_ids:
            await context.bot.send_message(chat_id=admin_id, text=f"New recipient added: @{username} with chat ID {user_id}.")
        logging.info(f"New recipient added: @{username} with chat ID {user_id}.")
    else:
        logging.info(f"Recipient @{username} is already in the list.")

# Enable recipient (Admin only)
async def enable_recipient(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You don't have permission to use this command.")
        return
    
    try:
        user_id = int(context.args[0])
        update_recipient_status(user_id, True)
        await update.message.reply_text(f"Recipient with ID {user_id} has been enabled successfully.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /enable_recipient <user_id>")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
        logging.error(f"Error enabling recipient: {e}")

# Disable recipient (Admin only)
async def disable_recipient(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You don't have permission to use this command.")
        return
    
    try:
        user_id = int(context.args[0])
        update_recipient_status(user_id, False)
        await update.message.reply_text(f"Recipient with ID {user_id} has been disabled successfully.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /disable_recipient <user_id>")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
        logging.error(f"Error disabling recipient: {e}")

# Remove a recipient (Admin only)
async def remove_recipient_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You don't have permission to use this command.")
        return
    
    try:
        user_id = int(context.args[0])
        remove_recipient(user_id)
        await update.message.reply_text(f"Recipient with ID {user_id} removed successfully.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /remove_recipient <user_id>")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
        logging.error(f"Error removing recipient: {e}")

# List all recipients (Admin only)
async def list_recipients(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You don't have permission to use this command.")
        return
    
    try:
        recipients = load_recipients()
        recipients_list = "\n".join([f"@{data['username']}: {user_id} (Active: {data['status']})" for user_id, data in recipients.items()])
        await update.message.reply_text(f"Current recipients:\n{recipients_list}")
    except Exception as e:
        await update.message.reply_text(f"Error retrieving recipients list: {e}")
        logging.error(f"Error retrieving recipients list: {e}")

# Help command to show available commands for the admin
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if is_admin(update.effective_user.id):
        help_text = (
            "Admin Commands:\n"
            "/start - Start the bot and show this message\n"
            "/help - Show this help message\n"
            "/enable_recipient <user_id> - Enable a recipient (Admin only)\n"
            "/disable_recipient <user_id> - Disable a recipient (Admin only)\n"
            "/remove_recipient <user_id> - Remove a recipient (Admin only)\n"
            "/list_recipients - List all current recipients (Admin only)"
        )
        await update.message.reply_text(help_text)
    else:
        await update.message.reply_text("You don't have permission to use this command.")

# Forward incoming messages to all recipients if sent by admin
async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if is_admin(update.effective_user.id):
        successful_recipients = []
        failed_recipients = []
        
        recipients = load_recipients()
        for user_id, data in recipients.items():
            if user_id not in admin_ids and data['status']:  # Check if recipient is active before sending
                try:
                    sent_message = await context.bot.send_message(chat_id=data['chat_id'], text=update.message.text)
                    successful_recipients.append(f"@{data['username']}")
                    
                    # Schedule deletion after 15 minutes (900 seconds)
                    context.job_queue.run_once(
                        delete_message_after_delay,
                        900,
                        data={'chat_id': data['chat_id'], 'message_id': sent_message.message_id}
                    )
                except Exception as e:
                    failed_recipients.append(f"@{data['username']} (Error: {e})")
                    logging.error(f"Failed to send message to @{data['username']} with error: {e}")
        
        # Send feedback to the admin about the message delivery status
        response_message = "Message forwarded successfully to the following recipients:\n"
        response_message += "\n".join(successful_recipients) if successful_recipients else "None"
        
        if failed_recipients:
            response_message += "\n\nFailed to send message to the following recipients:\n"
            response_message += "\n".join(failed_recipients)
        
        await update.message.reply_text(response_message)
    else:
        await update.message.reply_text("You don't have permission to send messages through this bot.")

# Function to delete messages after a delay
async def delete_message_after_delay(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    try:
        await context.bot.delete_message(chat_id=job.data['chat_id'], message_id=job.data['message_id'])
        logging.info(f"Message {job.data['message_id']} deleted successfully.")
    except Exception as e:
        logging.error(f"Failed to delete message {job.data['message_id']}: {e}")

# Handle all other commands for non-admin users
async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You only have access to the /start command.")

def main() -> None:
    # Create the Application with the JobQueue enabled
    app = ApplicationBuilder().token(bot_token).post_init(lambda application: application.job_queue.start()).build()
    job_queue = app.job_queue  # Access the JobQueue

    # Adding handlers for commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("enable_recipient", enable_recipient))
    app.add_handler(CommandHandler("disable_recipient", disable_recipient))
    app.add_handler(CommandHandler("remove_recipient", remove_recipient_command))
    app.add_handler(CommandHandler("list_recipients", list_recipients))
    
    # Adding handler for all text messages to be forwarded
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_message))
    # Adding handler for unknown commands for non-admin users
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    # Start the bot
    app.run_polling()

if __name__ == '__main__':
    main()
