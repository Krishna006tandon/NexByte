import os
from pymongo import MongoClient
from werkzeug.security import generate_password_hash
import getpass

# --- Database Configuration ---
# IMPORTANT: Make sure this URI is correct and points to your database.
MONGO_URI = "mongodb+srv://krishnatandon006:krishnatandon006@zenspace.63o32aq.mongodb.net/NexByte"
client = MongoClient(MONGO_URI)
db = client.get_database("NexByte") # Or whatever your DB name is
users = db.users

def create_admin_user():
    """Creates a new admin user in the database."""
    print("--- Create a New Admin User ---")
    
    # 1. Get user details
    name = input("Enter admin's full name: ")
    email = input("Enter admin's email address: ")
    
    # 2. Check if user already exists
    if users.find_one({'email': email}):
        print(f"Error: A user with the email '{email}' already exists.")
        return

    # 3. Get password securely
    password = getpass.getpass("Enter admin's password: ")
    confirm_password = getpass.getpass("Confirm password: ")

    if password != confirm_password:
        print("Error: Passwords do not match.")
        return

    # 4. Hash the password
    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

    # 5. Create the user document
    admin_user = {
        'name': name,
        'email': email,
        'password': hashed_password,
        'is_admin': True,
        'messages': []
    }

    # 6. Insert the new admin user into the database
    try:
        users.insert_one(admin_user)
        print(f"\nSuccessfully created admin user '{name}' with email '{email}'.")
    except Exception as e:
        print(f"\nAn error occurred while creating the user: {e}")

if __name__ == '__main__':
    create_admin_user()
    client.close()