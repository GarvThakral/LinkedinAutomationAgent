from fastapi import FastAPI , File, UploadFile, HTTPException , Form
from src.user_details import get_user_details
from src.run_agent import run_agent
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import requests
import os
from typing import Any, List
import psycopg2
import numpy as np
import pandas as pd
from psycopg2.extras import RealDictCursor
from src.run_agent import create_and_post_linkedin_content
load_dotenv()


app = FastAPI()

import psycopg2
from psycopg2 import sql

def create_database_if_not_exists():
    # Connect to the default postgres database
    conn = psycopg2.connect(
        database="postgres",
        user=DATABASE_CONFIG["user"],
        password=DATABASE_CONFIG["password"],
        host=DATABASE_CONFIG["host"],
        port=DATABASE_CONFIG["port"]
    )
    conn.autocommit = True
    cur = conn.cursor()

    # Check if our target DB exists
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DATABASE_CONFIG["database"],))
    exists = cur.fetchone()

    if not exists:
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DATABASE_CONFIG["database"])))
        print(f"✅ Created database '{DATABASE_CONFIG['database']}'")
    else:
        print(f"ℹ️ Database '{DATABASE_CONFIG['database']}' already exists")

    cur.close()
    conn.close()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or your frontend URL
    allow_credentials=True,
    allow_methods=["*"],  # Important: allows OPTIONS too
    allow_headers=["*"],
)

DATABASE_CONFIG = {
    "database": "influence",
    "user": "postgres",
    "password": "mypassword",
    "host": "localhost",
    "port": "5432",
}

@app.get("/user")
def user_details():
    return get_user_details()


class MakePostRequest(BaseModel):
    contentRequirements: str
    targetAudience: str
    postTone: str

@app.post('/makepost')
def run_agent_orch(
    payload: MakePostRequest
):
    create_database_if_not_exists()
    conn = psycopg2.connect(**DATABASE_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)  

    cursor.execute("SELECT name, about, industry, website FROM user_details ORDER BY id DESC LIMIT 1")
    user_row = cursor.fetchone()

    cursor.close()
    conn.close()

    # Construct client_info using fetched values or fallback
    if user_row:
        client_info = {
            "name": user_row.get("name", "John Doe"),
            "industry": user_row.get("industry", "Tech"),
            # about and website fetched but not used yet
            "about": user_row.get("about", ""),
            "website": user_row.get("website", "")
        }
    else:
        client_info = {
            "name": "John Doe",
            "industry": "Tech",
            "about": "",
            "website": ""
        }

    # Debug prints if needed
    print("Requirements:", payload.contentRequirements)
    print("Audience:", payload.targetAudience)
    print("Tone:",payload.postTone)

    # Call run_agent passing the client_info with name and industry
    print(client_info)
    print(payload.contentRequirements)
    return run_agent(
        client_info=client_info,
        post_type="carousel",
        target_industry=client_info.get('industry'),
        content_goals=payload.contentRequirements + " Tone of the post = " + payload.postTone
    )

class LinkedInData(BaseModel):
    code: str

class PostContentRequest(BaseModel):
    content_data: Any  # replace Any with specific type if you have one
    image_urls: List[str]
    post_type: str
    access_token: str

@app.post("/postcontent")
def post_content(request: PostContentRequest):
    headers = {"Authorization": f"Bearer {request.access_token}"}
    # Call LinkedIn API to get user URN
    profile_response = requests.get("https://api.linkedin.com/v2/userinfo", headers=headers)
    
    if profile_response.status_code != 200:
        raise HTTPException(status_code=profile_response.status_code, detail="Failed to fetch user info from LinkedIn")
    
    profile_json = profile_response.json()
    linkedin_urn = profile_json.get("sub")
    
    if not linkedin_urn:
        raise HTTPException(status_code=400, detail="LinkedIn URN not found in response")
    
    # Call your post function
    print(linkedin_urn)
    result = create_and_post_linkedin_content(
        content_data=request.content_data,
        image_urls=request.image_urls,
        post_type=request.post_type,
        linkedin_urn=linkedin_urn,
        access_token=request.access_token
    )
    
    return {"status": "success", "detail": "Content posted to LinkedIn", "result": result}

@app.post('/connectLinkedin')
def connect(code:LinkedInData):
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    token_data = {
        'grant_type': 'authorization_code',
        'code': code.code,
        'redirect_uri': os.getenv('REDIRECT_URI'),
        'client_id': os.getenv('CLIENT_ID'),
        'client_secret': os.getenv('CLIENT_SECRET'),
    }
    
    try:
        token_response = requests.post(token_url, data=token_data)
        token_json = token_response.json()
        
        if 'access_token' in token_json:
            access_token = token_json['access_token']
            
            return {
                'access_token':access_token
            }
        else:
            return token_json
            
    except Exception as e:
        return {'error':e}




@app.post("/upload-csv")
async def upload_csv(
    file: UploadFile = File(...),
    user_id: int = Form(...)   # ✅ get user id along with CSV
):
    if not file.filename.endswith(".csv"):
        return {"error": "Invalid file type"}
    
    df = pd.read_csv(file.file)
    df = df.replace({np.nan: None, np.inf: None, -np.inf: None})

    first_row = df.iloc[0]

    first_name = first_row.get('First Name') or ''
    last_name = first_row.get('Last Name') or ''
    full_name = f"{first_name} {last_name}".strip()

    summary = first_row.get('Summary') or ''
    industry = first_row.get('Industry') or ''
    website = first_row.get('Websites') or ''

    create_database_if_not_exists()
    conn = psycopg2.connect(**DATABASE_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_details (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            name TEXT,
            about TEXT,
            industry TEXT,
            website TEXT
        )
    """)
    conn.commit()

    cursor.execute("""
        UPDATE user_details
        SET name = %s, about = %s, industry = %s, website = %s
        WHERE id = %s
    """, (full_name, summary, industry, website, user_id))

    conn.commit()
    cursor.close()
    conn.close()

    return {
        "filename": file.filename,
        "rows": len(df),
        "columns": list(df.columns),
        "data": df.to_dict(orient="records"),
        "message": f"User details saved for user_id {user_id}."
    }


class SignupRequest(BaseModel):
    full_name: Any 
    email: str
    password: str

@app.post("/signup")
def signup(payload:SignupRequest):
    create_database_if_not_exists()
    conn = psycopg2.connect(**DATABASE_CONFIG)
    cur = conn.cursor()

    # create users table if not exists
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
    cur.execute("SELECT id FROM users WHERE email=%s", (payload.email,))
    if cur.fetchone():
        print("❌ Email already registered")
        cur.close()
        conn.close()
        return False

    # insert user
    cur.execute("INSERT INTO users (full_name, email, password) VALUES (%s, %s, %s)",
                (payload.full_name, payload.email, payload.password))
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Signup successful")
    return True


class SigninRequest(BaseModel):
    email: str
    password: str

@app.post("/login")
def login(payload:SigninRequest):
    create_database_if_not_exists()
    conn = psycopg2.connect(**DATABASE_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT id, full_name FROM users WHERE email=%s AND password=%s", (payload.email, payload.password))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user:
        print(f"✅ Login successful. Welcome {user[1]}!")
        return user[0]
    else:
        print("❌ Invalid email or password")
        return False
