from flask import Flask, render_template, request, redirect, url_for, flash
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import sqlite3
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

# Database setup
db_file = 'reminders.db'

# Create tables if they don't exist
def create_db():
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reminders 
                 (chat_id TEXT, name TEXT, specialty TEXT, date TEXT)''')
    conn.commit()
    conn.close()

create_db()

# Function to save user input to the database
def save_reminder(chat_id, name, specialty, date):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO reminders (chat_id, name, specialty, date) VALUES (?, ?, ?, ?)",
                  (chat_id, name, specialty, date))
        conn.commit()
        return True
    except Exception as e:
        print(f"Failed to save reminder: {e}")
        return False
    finally:
        conn.close()

# Function to fetch user reminders from the database
def get_user_reminders():
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute("SELECT * FROM reminders")
    reminders = c.fetchall()
    conn.close()
    return reminders

# Scheduler to send reminders
def send_reminder(chat_id, name, specialty, date):
    message = f"✨ Reminder for {name}: Today's specialty is {specialty} 🌟!"
    bot.send_message(chat_id=chat_id, text=message)

# Function to check and send reminders
def check_reminders():
    today = datetime.now().strftime("%m/%d")
    reminders = get_user_reminders()
    for reminder in reminders:
        chat_id, name, specialty, date = reminder
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

# Admin route to download the .txt file (only admin can access this)
@app.route('/admin/download')
def admin_download():
    if request.args.get('chat_id') == admin_chat_id:
        with open('reminders.txt', 'w') as f:
            conn = sqlite3.connect(db_file)
            c = conn.cursor()
            c.execute("SELECT * FROM reminders")
            reminders = c.fetchall()
            for reminder in reminders:
                f.write(f"{reminder[0]} - {reminder[1]} - {reminder[2]} - {reminder[3]}\n")
            conn.close()
        return "File saved as reminders.txt"
    return "Unauthorized"

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
    app.run(debug=True)
