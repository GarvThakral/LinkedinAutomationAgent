from dotenv import load_dotenv
import os
import requests
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from bs4 import BeautifulSoup
# Load environment variables
load_dotenv()

# ---------------- NEON DB CONFIG ----------------
# Get the connection string from environment variable
NEON_CONNECTION_STRING = os.getenv("NEON_CONNECTION_STRING")

# If not in .env, you can set it directly (not recommended for production)
if not NEON_CONNECTION_STRING:
    NEON_CONNECTION_STRING = "postgresql://neondb_owner:****************@ep-damp-base-ae4z5d59-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"


# ---------------- CONNECT TO NEON DB ----------------
def get_db_conn():
    """Connect directly to Neon DB - no need to create database as it already exists"""
    try:
        conn = psycopg2.connect(NEON_CONNECTION_STRING)
        return conn
    except Exception as e:
        print(f"❌ Failed to connect to Neon DB: {e}")
        raise


# ---------------- TEST CONNECTION ----------------
def test_connection():
    """Test the Neon DB connection"""
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()
        print(f"✅ Connected to Neon DB: {version[0]}")
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False


# ---------------- SIGNUP ----------------
def signup(full_name, email, password):
    conn = get_db_conn()
    cur = conn.cursor()

    # create table if not exists
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

    try:
        # insert new user
        cur.execute("""
        INSERT INTO users (full_name, email, password) 
        VALUES (%s, %s, %s)
        """, (full_name, email, password))
        conn.commit()
        print("✅ Signup successful")
        return True
    except Exception as e:
        print(f"❌ Signup failed: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


# ---------------- LOGIN ----------------
def login(email, password):
    conn = get_db_conn()
    cur = conn.cursor()

    try:
        cur.execute("""
        SELECT id, full_name, created_at 
        FROM users 
        WHERE email=%s AND password=%s
        """, (email, password))
        user = cur.fetchone()

        if user:
            print(f"✅ Login successful. Welcome {user[1]}!")
            print(f"   Account created: {user[2]}")
            return True
        else:
            print("❌ Invalid email or password")
            return False
    except Exception as e:
        print(f"❌ Login failed: {e}")
        return False
    finally:
        cur.close()
        conn.close()


# ---------------- GET USER DETAILS + SAVE ----------------
def get_user_details():
    """
    Return the most recent user details saved in the database.
    Falls back to LinkedIn userinfo (if ACCESS_TOKEN is set) and,
    if nothing is available, a minimal default payload. No CSV needed.
    """
    access_token = os.getenv("ACCESS_TOKEN")
    headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
    profile_data = {}

    try:
        profile_response = requests.get(
            "https://api.linkedin.com/v2/userinfo", headers=headers, timeout=10
        )
        if profile_response.status_code == 200:
            profile_data = profile_response.json()
    except Exception as e:
        print("⚠️ LinkedIn API Error:", e)

    conn = get_db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute(
            """
        CREATE TABLE IF NOT EXISTS user_details (
            id SERIAL PRIMARY KEY,
            name TEXT,
            about TEXT,
            industry TEXT,
            website TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        )
        conn.commit()

        cur.execute(
            """
        SELECT name, about, industry, website
        FROM user_details
        ORDER BY created_at DESC
        LIMIT 1
        """
        )
        row = cur.fetchone()

        if row:
            client_info = dict(row)
        else:
            client_info = {
                "name": profile_data.get("name") or "LinkedIn Member",
                "about": "",
                "industry": profile_data.get("locale", ""),
                "website": "",
            }

        if client_info.get("website"):
            try:
                website_url = client_info["website"]
                if not website_url.startswith(("http://", "https://")):
                    website_url = "https://" + website_url

                page = requests.get(
                    website_url,
                    timeout=10,
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                soup = BeautifulSoup(page.content, "html.parser")
                text = soup.get_text(separator=" ", strip=True)
                print("Website snippet:", text[:200] + "...")
            except Exception as e:
                print(f"Website fetch error: {e}")

        return client_info

    except Exception as e:
        print(f"❌ Failed to fetch user details: {e}")
        return {
            "name": "LinkedIn Member",
            "about": "",
            "industry": "",
            "website": "",
        }
    finally:
        cur.close()
        conn.close()

# ---------------- GET ALL USERS (UTILITY FUNCTION) ----------------
def get_all_users():
    """Utility function to view all users in the database"""
    conn = get_db_conn()
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT id, full_name, email, created_at FROM users ORDER BY created_at DESC")
        users = cur.fetchall()
        
        if users:
            print("\n📋 All Users:")
            print("-" * 60)
            for user in users:
                print(f"ID: {user[0]} | Name: {user[1]} | Email: {user[2]} | Created: {user[3]}")
        else:
            print("No users found in database")
            
        return users
    except Exception as e:
        print(f"❌ Error fetching users: {e}")
        return []
    finally:
        cur.close()
        conn.close()


# ---------------- GET ALL USER DETAILS (UTILITY FUNCTION) ----------------
def get_all_user_details():
    """Utility function to view all user details in the database"""
    conn = get_db_conn()
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT * FROM user_details ORDER BY created_at DESC")
        details = cur.fetchall()
        
        if details:
            print("\n📋 All User Details:")
            print("-" * 80)
            for detail in details:
                print(f"ID: {detail[0]} | Name: {detail[1]} | Industry: {detail[3]} | Created: {detail[5]}")
                if detail[2]:  # about
                    print(f"   About: {detail[2][:100]}...")
                if detail[4]:  # website
                    print(f"   Website: {detail[4]}")
                print()
        else:
            print("No user details found in database")
            
        return details
    except Exception as e:
        print(f"❌ Error fetching user details: {e}")
        return []
    finally:
        cur.close()
        conn.close()


# ---------------- Example Usage ----------------
if __name__ == "__main__":
    print("🚀 Testing Neon DB connection...")
    
    if test_connection():
        print("\n" + "="*50)
        print("Testing signup and login...")
        
        # Test signup
        if signup("John Doe", "john@example.com", "pass123"):
            # Test login
            login("john@example.com", "pass123")
            
            # Test get user details (requires Profile.csv)
            try:
                user_info = get_user_details()
                if user_info:
                    print("User info retrieved successfully!")
            except FileNotFoundError:
                print("⚠️ Profile.csv not found. Skipping user details test.")
            except Exception as e:
                print(f"⚠️ Error in get_user_details: {e}")
        
        # Show all data
        print("\n" + "="*50)
        get_all_users()
        get_all_user_details()
    else:
        print("❌ Cannot proceed without database connection")
