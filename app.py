from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
import re

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config["MONGO_URI"] = "mongodb+srv://krishnatandon006:krishnatandon006@zenspace.63o32aq.mongodb.net/NexByte"
# Remove hardcoded SendGrid API key and use environment variable
sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')
if not sendgrid_api_key:
    raise RuntimeError('SENDGRID_API_KEY environment variable not set!')
app.config['SENDGRID_API_KEY'] = sendgrid_api_key
mongo = PyMongo(app)
sg = sendgrid.SendGridAPIClient(app.config['SENDGRID_API_KEY'])

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message_body = request.form['message']

        # Send email using SendGrid
        from_email = Email("nexbyte.dev@gmail.com")
        to_email = To("nexbyte.dev@gmail.com")
        subject = f"New Contact Form Submission from {name}"
        plain_text_content = f"From: {name} <{email}>\n\n{message_body}"
        html_content = f"""
        <h3>New Contact Form Submission</h3>
        <p><strong>Name:</strong> {name}</p>
        <p><strong>Email:</strong> {email}</p>
        <p><strong>Message:</strong></p>
        <p>{message_body}</p>
        """
        mail = Mail(
            from_email=from_email,
            to_emails=to_email,
            subject=subject,
            plain_text_content=plain_text_content,
            html_content=html_content
        )
        
        try:
            response = sg.client.mail.send.post(request_body=mail.get())
            if response.status_code == 202:
                flash('Your message has been sent successfully!', 'success')
                 # Store message in user's profile if logged in
                if 'user_id' in session:
                    users = mongo.db.users
                    message_id = str(ObjectId())
                    users.update_one(
                        {'_id': ObjectId(session['user_id'])},
                        {'$push': {'messages': {
                            'message_id': message_id,
                            'name': name,
                            'email': email,
                            'message': message_body,
                            'replies': []
                        }}}
                    )
                    
                    # Send confirmation email to user
                    reply_to_email = Email("nexbyte.dev@gmail.com")
                    user_email = To(email)
                    reply_subject = f"Re: Your message to NexByte [ref:{message_id}]"
                    reply_content = Content("text/plain", "Thank you for your message. We will get back to you shortly. You can reply to this email to add more comments.")
                    reply_mail = Mail(from_email, user_email, reply_subject, reply_content)
                    reply_response = sg.client.mail.send.post(request_body=reply_mail.get())
                    print(f"Reply email sent to {email}, status code: {reply_response.status_code}")


            else:
                flash(f'An error occurred while sending your message. Status Code: {response.status_code}', 'error')
        except Exception as e:
            error_body = e.body if hasattr(e, 'body') else 'No additional error body found.'
            print(f"A critical error occurred with SendGrid. Status Code: {getattr(e, 'status_code', 'N/A')}")
            print(f"Error Body: {error_body}")
            flash('An error occurred while sending your message.', 'error')


       
        return redirect(url_for('contact'))
    return render_template('contact.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        users = mongo.db.users
        existing_user = users.find_one({'email': email})

        if existing_user:
            flash('Email already registered.', 'error')
            return redirect(url_for('signup'))

        # Make the first user an admin
        is_admin = users.count_documents({}) == 0
        users.insert_one({'name': name, 'email': email, 'password': hashed_password, 'is_admin': is_admin})
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        users = mongo.db.users
        user = users.find_one({'email': email})

        if user and check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id'])
            session['is_admin'] = user.get('is_admin', False)
            if session['is_admin']:
                return redirect(url_for('admin'))
            return redirect(url_for('profile'))
        else:
            flash('Invalid email or password.', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    users = mongo.db.users
    user = users.find_one({'_id': ObjectId(session['user_id'])})

    if user:
        return render_template('profile.html', user=user)
    return redirect(url_for('login'))

@app.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    users = mongo.db.users
    user = users.find_one({'_id': ObjectId(session['user_id'])})

    if not user or not user.get('is_admin'):
        return redirect(url_for('profile'))

    all_users = list(users.find())
    return render_template('admin.html', users=all_users)

@app.route('/admin/reply/<user_id>/<message_id>', methods=['POST'])
def admin_reply(user_id, message_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    users = mongo.db.users
    admin_user = users.find_one({'_id': ObjectId(session['user_id'])})

    if not admin_user or not admin_user.get('is_admin'):
        return redirect(url_for('profile'))

    reply_text = request.form['reply']

    # Find the user and the message to get user's email and name
    user = users.find_one({'_id': ObjectId(user_id)})
    user_email = None
    user_name = None
    if user and 'messages' in user:
        for msg in user['messages']:
            if msg.get('message_id') == message_id:
                user_email = msg.get('email')
                user_name = msg.get('name')
                break

    # Save reply in DB with 'from': 'NexByte'
    users.update_one(
        {'_id': ObjectId(user_id), 'messages.message_id': message_id},
        {'$push': {'messages.$.replies': {'from': 'NexByte', 'reply_text': reply_text}}}
    )

    # Send email to user if email found
    if user_email:
        from sendgrid.helpers.mail import Mail, Email, To, Content
        from_email = Email("nexbyte.dev@gmail.com", "NexByte")
        to_email = To(user_email)
        subject = f"Reply from NexByte to your message"
        content = Content("text/plain", f"Hello {user_name or ''},\n\nYou received a reply from NexByte:\n\n{reply_text}\n\nThank you!")
        mail = Mail(from_email, to_email, subject, content)
        try:
            response = sg.client.mail.send.post(request_body=mail.get())
            print(f"Reply email sent to {user_email}, status code: {response.status_code}")
        except Exception as e:
            print(f"Error sending reply email: {e}")

    flash('Reply sent!', 'success')
    return redirect(url_for('admin'))

@app.route('/email_webhook', methods=['POST'])
def email_webhook():
    sender = request.form.get('from')
    subject = request.form.get('subject', '')
    text = request.form.get('text', '')
    
    match = re.search(r'\[ref:(\w+)\]', subject)
    if not match:
        return 'OK', 200

    message_id = match.group(1)

    users = mongo.db.users
    users.update_one(
        {'messages.message_id': message_id},
        {'$push': {'messages.$.replies': {'from': sender, 'reply_text': text}}}
    )

    return 'OK', 200

if __name__ == '__main__':
    app.run(debug=True)