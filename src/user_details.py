from dotenv import load_dotenv
import os
import requests
import pandas as pd
import psycopg2
from psycopg2 import sql
from bs4 import BeautifulSoup


# ---------------- DB CONFIG ----------------
DB_NAME = "influence"
DB_USER = "postgres"
DB_HOST = "localhost"
DB_PASS = "mypassword"
DB_PORT = "5432"


# ---------------- CREATE DB IF NOT EXISTS ----------------
def create_database_if_not_exists():
    conn = psycopg2.connect(
        database="postgres",
        user=DB_USER,
        host=DB_HOST,
        password=DB_PASS,
        port=DB_PORT
    )
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (DB_NAME,))
    exists = cur.fetchone()

    if not exists:
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB_NAME)))
        print(f"✅ Database '{DB_NAME}' created")
    else:
        print(f"ℹ️ Database '{DB_NAME}' already exists")

    cur.close()
    conn.close()


# ---------------- CONNECT TO SPECIFIC DB ----------------
def get_db_conn():
    return psycopg2.connect(
        database=DB_NAME,
        user=DB_USER,
        host=DB_HOST,
        password=DB_PASS,
        port=DB_PORT
    )


# ---------------- SIGNUP ----------------
def signup(full_name, email, password):
    create_database_if_not_exists()  # make sure DB exists
    conn = get_db_conn()
    cur = conn.cursor()

    # create table if not exists
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)
    conn.commit()

    # check if email already exists
    cur.execute("SELECT id FROM users WHERE email=%s", (email,))
    if cur.fetchone():
        print("❌ Email already registered")
        cur.close()
        conn.close()
        return False

    # insert
    cur.execute("INSERT INTO users (full_name, email, password) VALUES (%s, %s, %s)",
                (full_name, email, password))
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Signup successful")
    return True


# ---------------- LOGIN ----------------
def login(email, password):
    create_database_if_not_exists()  # make sure DB exists
    conn = get_db_conn()
    cur = conn.cursor()

    cur.execute("SELECT id, full_name FROM users WHERE email=%s AND password=%s",
                (email, password))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user:
        print(f"✅ Login successful. Welcome {user[1]}!")
        return True
    else:
        print("❌ Invalid email or password")
        return False


# ---------------- GET USER DETAILS + SAVE ----------------
def get_user_details():
    create_database_if_not_exists()  # make sure DB exists
    load_dotenv()
    access_token = os.getenv("ACCESS_TOKEN")

    headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
    try:
        profile_response = requests.get("https://api.linkedin.com/v2/userinfo", headers=headers)
        print("LinkedIn API status:", profile_response.status_code)
        profile_data = profile_response.json()
    except Exception as e:
        print("⚠️ LinkedIn API Error:", e)
        profile_data = {}

    # CSV read
    data = pd.read_csv("Profile.csv")
    client_name = data['First Name'][0] + " " + data['Last Name'][0]
    about_client = data['Summary'][0]
    client_industry = data['Industry'][0]
    client_website = data["Websites"][0]
    client_urn = data['']

    client_info = {
        'name': client_name,
        'about': about_client,
        'industry': client_industry,
        'website': client_website if not pd.isna(client_website) else ''
    }

    # optional website scrape
    if client_info['website']:
        try:
            page = requests.get(client_info['website'], timeout=10)
            soup = BeautifulSoup(page.content, 'html.parser')
            text = soup.get_text(separator=' ', strip=True)
            print("Website snippet:", text[:200])
        except Exception as e:
            print("Website fetch error:", e)

    print("Final client_info:", client_info)

    # save to DB
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_details (
        id SERIAL PRIMARY KEY,
        name TEXT,
        about TEXT,
        industry TEXT,
        website TEXT
    )
    """)
    conn.commit()

    cur.execute("""
    INSERT INTO user_details (name, about, industry, website)
    VALUES (%s, %s, %s, %s)
    """, (client_info['name'], client_info['about'], client_info['industry'], client_info['website']))
    conn.commit()

    cur.close()
    conn.close()
    print("✅ Client details saved to DB")

    return client_info


# ---------------- Example Usage ----------------
if __name__ == "__main__":
    signup("John Doe", "john@example.com", "pass123")
    login("john@example.com", "pass123")
    get_user_details()
