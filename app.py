from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pymongo
import telebot
import os
from dotenv import load_dotenv
import threading

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app and Telegram bot using telebot
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Set a secret key for flash messages

# Initialize the Telegram Bot using environment variables
bot = telebot.TeleBot(os.getenv('TELEGRAM_BOT_TOKEN'))

# Admin chat ID using environment variables
admin_chat_id = os.getenv('ADMIN_CHAT_ID')

# MongoDB setup
client = pymongo.MongoClient(os.getenv("MONGO_URI"))
db = client['reminder_app']  # Replace 'reminder_app' with your database name
reminders_collection = db['reminders']

# Function to save user input to the database
def save_reminder(chat_id, name, specialty, date):
    try:
        reminder = {
            "chat_id": chat_id,
            "name": name,
            "specialty": specialty,
            "date": date
        }
        reminders_collection.insert_one(reminder)
        return True
    except Exception as e:
        print(f"Failed to save reminder: {e}")
        return False

# Function to fetch user reminders from the database
def get_user_reminders(chat_id=None):
    if chat_id:
        return list(reminders_collection.find({"chat_id": chat_id}))
    return list(reminders_collection.find({}))

# Scheduler to send reminders
def send_reminder(chat_id, name, specialty, date):
    message = f"✨ Reminder for {name}: Today's specialty is {specialty} 🌟!"
    bot.send_message(chat_id=chat_id, text=message)

# Function to check and send reminders
def check_reminders():
    today = datetime.now().strftime("%m/%d")
    reminders = get_user_reminders()
    for reminder in reminders:
        chat_id = reminder['chat_id']
        name = reminder['name']
        specialty = reminder['specialty']
        date = reminder['date']
        if date == today:
            send_reminder(chat_id, name, specialty, date)

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(check_reminders, 'interval', hours=24, next_run_time=datetime.now())
scheduler.start()

# Flask Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit_reminder():
    chat_id = request.form['chat_id']
    name = request.form['name']
    specialty = request.form['specialty']
    date = request.form['date']
    if save_reminder(chat_id, name, specialty, date):
        flash("Reminder saved successfully!", "success")
    else:
        flash("Failed to save reminder. Please try again.", "danger")
    return redirect(url_for('home'))

# Route to view all reminders for a specific chat ID and delete individually
@app.route('/view_reminders/<chat_id>', methods=['GET', 'POST'])
def view_reminders(chat_id):
    if request.method == 'POST':
        reminder_id = request.form['reminder_id']
        reminders_collection.delete_one({"_id": pymongo.ObjectId(reminder_id)})
        flash("Reminder deleted successfully.", "success")
        return redirect(url_for('view_reminders', chat_id=chat_id))
    
    reminders = get_user_reminders(chat_id)
    return render_template('view_reminders.html', reminders=reminders, chat_id=chat_id)
# Admin route to download the .txt file (only admin can access this)
@app.route('/admin/download')
def admin_download():
    if request.args.get('chat_id') == admin_chat_id:
        with open('reminders.txt', 'w') as f:
            reminders = get_user_reminders()
            for reminder in reminders:
                f.write(f"{reminder['chat_id']} - {reminder['name']} - {reminder['specialty']} - {reminder['date']}\n")
        return send_file('reminders.txt', as_attachment=True)
    return "Unauthorized"
"""
@app.route('/delete', methods=['POST'])
def delete_reminder():
    chat_id = request.form['chat_id']
    if reminders_collection.delete_many({"chat_id": chat_id}).deleted_count > 0:
        flash(f"Reminders for chat ID {chat_id} have been deleted successfully.", "success")
    else:
        flash(f"No reminders found for chat ID {chat_id}.", "danger")
    return redirect(url_for('home'))
"""
@app.route('/delete', methods=['POST'])
def delete_reminder():
    chat_id = request.form['chat_id']
    return redirect(url_for('view_reminders', chat_id=chat_id))

# Telegram bot command handler for /admin
@bot.message_handler(commands=['admin'])
def admin_info(message):
    if str(message.chat.id) == admin_chat_id:
        reminders = get_user_reminders()
        if reminders:
            reminder_texts = [f"Chat ID: {reminder['chat_id']}, Name: {reminder['name']}, Specialty: {reminder['specialty']}, Date: {reminder['date']}"
                              for reminder in reminders]
            reminders_message = "\n\n".join(reminder_texts)
            bot.send_message(chat_id=admin_chat_id, text=f"📋 Current Reminders:\n\n{reminders_message}")
        else:
            bot.send_message(chat_id=admin_chat_id, text="No reminders found in the database.")
    else:
        bot.send_message(chat_id=message.chat.id, text="Unauthorized access.")

# Telegram bot command handler for /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, 
                     "Welcome to the Telegram Reminder Bot! 🎉\n\n"
                     "To get started, you need to set up your reminder. Please visit the following link to update your reminder details: 🌐\n"
                     f"{os.getenv('WEB_URL')}\n\n"
                     "Once you've updated your reminder, the bot will notify you on the specified date. 💡\n\n"
                     "Please make sure to click the 'Start' button in Telegram to activate the bot! ⚠️")

# Function to run the bot
def start_bot():
    bot.polling()

if __name__ == "__main__":
    # Start the bot in a separate thread
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.start()
    
    # Start Flask app
    app.run(host='0.0.0.0', port=5000)
