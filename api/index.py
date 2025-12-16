from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Query
from src.user_details import get_user_details
from src.run_agent import run_agent
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth
import os
from typing import Any, List
import psycopg2
import csv
from psycopg2.extras import RealDictCursor
from src.run_agent import create_and_post_linkedin_content
import io
from src.regenerate_images import regenerate
from urllib.parse import urlencode

# Load environment variables
load_dotenv()

app = FastAPI()

# ---------------- NEON DB CONFIG ----------------
NEON_CONNECTION_STRING = os.getenv("NEON_CONNECTION_STRING")

# If not in .env, you can set it directly (not recommended for production)
if not NEON_CONNECTION_STRING:
    NEON_CONNECTION_STRING = "postgresql://neondb_owner:****************@ep-damp-base-ae4z5d59-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# --------------- OAUTH CONFIG ----------------
IG_APP_ID = os.getenv("IG_APP_ID", "")
IG_APP_SECRET = os.getenv("IG_APP_SECRET", "")
IG_REDIRECT_URI = os.getenv("IG_REDIRECT_URI", "https://yourapp.com/instagram/callback")

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_REDIRECT_URI = os.getenv("REDDIT_REDIRECT_URI", "https://yourapp.com/reddit/callback")
REDDIT_SCOPES = ["identity", "submit"]

# ---------------- DATABASE CONNECTION ----------------
def get_neon_connection():
    """Get connection to Neon DB"""
    try:
        conn = psycopg2.connect(NEON_CONNECTION_STRING)
        return conn
    except Exception as e:
        print(f"❌ Failed to connect to Neon DB: {e}")
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

def test_neon_connection():
    """Test Neon DB connection"""
    try:
        conn = get_neon_connection()
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()
        print(f"✅ Connected to Neon DB: {version[0]}")
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Neon DB connection test failed: {e}")
        return False

# Test connection on startup
@app.on_event("startup")
async def startup_event():
    """Test database connection on startup"""
    if test_neon_connection():
        print("🚀 FastAPI app started with Neon DB connection")
    else:
        print("⚠️ FastAPI app started but Neon DB connection failed")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- ROUTES ----------------
@app.get("/")
def health_checks():
    return {"status": "healthy", "message": "API is running"}

@app.get("/health")  
def detailed_health():
    return {"status": "ok", "timestamp": "2024-08-14"}

@app.get("/")
def root():
    """Health check endpoint"""
    return {"message": "FastAPI app with Neon DB is running"}

@app.get("/health")
def health_check():
    """Database health check"""
    try:
        conn = get_neon_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        conn.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}

@app.get("/user")
def user_details():
    """Get user details from external source"""
    return get_user_details()

# ---------------- OAUTH HELPERS ----------------
def build_instagram_oauth_url(state: str = "instagram_state"):
    scopes = [
        "instagram_basic",
        "instagram_content_publish",
        "pages_show_list",
        "business_management",
    ]
    params = {
        "client_id": IG_APP_ID,
        "redirect_uri": IG_REDIRECT_URI,
        "scope": ",".join(scopes),
        "auth_type": "rerequest",
        "state": state,
    }
    return f"https://www.facebook.com/v20.0/dialog/oauth?{urlencode(params)}"


def build_reddit_oauth_url(state: str = "reddit_state"):
    params = {
        "client_id": REDDIT_CLIENT_ID,
        "response_type": "code",
        "state": state,
        "redirect_uri": REDDIT_REDIRECT_URI,
        "duration": "permanent",
        "scope": " ".join(REDDIT_SCOPES),
    }
    return f"https://www.reddit.com/api/v1/authorize?{urlencode(params)}"


def create_instagram_media_container(ig_user_id: str, page_token: str, image_url: str, caption: str):
    url = f"https://graph.facebook.com/v20.0/{ig_user_id}/media"
    payload = {"image_url": image_url, "caption": caption, "access_token": page_token}
    res = requests.post(url, data=payload, timeout=20)
    data = res.json()
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])
    return data.get("id")


def publish_instagram_media(ig_user_id: str, page_token: str, creation_id: str):
    url = f"https://graph.facebook.com/v20.0/{ig_user_id}/media_publish"
    payload = {"creation_id": creation_id, "access_token": page_token}
    res = requests.post(url, data=payload, timeout=20)
    data = res.json()
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])
    return data

# ---------------- COMMON MODELS ----------------
class MakePostRequest(BaseModel):
    contentRequirements: str
    targetAudience: str
    postTone: str
    context: str | None = None

class LinkedInData(BaseModel):
    code: str

class PostContentRequest(BaseModel):
    content_data: Any
    image_urls: List[str]
    post_type: str
    access_token: str

class InstagramTokenRequest(BaseModel):
    code: str

class InstagramPublishRequest(BaseModel):
    page_token: str
    ig_user_id: str
    image_url: str
    caption: str = "Posted via API"

class RedditTokenRequest(BaseModel):
    code: str
    redirect_uri: str | None = None

class RedditPostRequest(BaseModel):
    subreddit: str
    title: str
    kind: str = "self"  # "self" or "link"
    text: str | None = None
    url: str | None = None

@app.post('/makepost')
def run_agent_orch(payload: MakePostRequest):
    """Create a post using AI agent"""
    conn = get_neon_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_details (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                name TEXT,
                about TEXT,
                industry TEXT,
                website TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        # Get latest user details
        cursor.execute("SELECT name, about, industry, website FROM user_details ORDER BY id DESC LIMIT 1")
        user_row = cursor.fetchone()

        # Construct client_info using fetched values or fallback
        if user_row:
            client_info = {
                "name": user_row.get("name", "John Doe"),
                "industry": user_row.get("industry", "Tech"),
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

        print("Requirements:", payload.contentRequirements)
        print("Audience:", payload.targetAudience)
        print("Tone:", payload.postTone)
        print("Client Info:", client_info)

        # Call run_agent with the client info
        result = run_agent(
            client_info=client_info,
            post_type="carousel",
            target_industry=client_info.get('industry'),
            content_goals=f"{payload.contentRequirements} Tone of the post = {payload.postTone}.",
            context=payload.context or ""
        )
        result["name"] = client_info['name']
        result["industry"] = client_info['industry']
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating post: {str(e)}")
    finally:
        cursor.close()
        conn.close()

class LinkedInData(BaseModel):
    code: str

class PostContentRequest(BaseModel):
    content_data: Any
    image_urls: List[str]
    post_type: str
    access_token: str

@app.post("/postcontent")
def post_content(request: PostContentRequest):
    """Post content to LinkedIn"""
    headers = {"Authorization": f"Bearer {request.access_token}"}
    
    # Call LinkedIn API to get user URN
    profile_response = requests.get("https://api.linkedin.com/v2/userinfo", headers=headers)
    
    if profile_response.status_code != 200:
        raise HTTPException(
            status_code=profile_response.status_code, 
            detail="Failed to fetch user info from LinkedIn"
        )
    
    profile_json = profile_response.json()
    linkedin_urn = profile_json.get("sub")
    
    if not linkedin_urn:
        raise HTTPException(status_code=400, detail="LinkedIn URN not found in response")
    
    # Call your post function
    print(f"LinkedIn URN: {linkedin_urn}")
    try:
        result = create_and_post_linkedin_content(
            content_data=request.content_data,
            image_urls=request.image_urls,
            post_type=request.post_type,
            linkedin_urn=linkedin_urn,
            access_token=request.access_token
        )
        return {"status": "success", "detail": "Content posted to LinkedIn", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error posting to LinkedIn: {str(e)}")

@app.post('/connectLinkedin')
def connect_linkedin(code: LinkedInData):
    """Connect to LinkedIn OAuth"""
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
            return {'access_token': token_json['access_token']}
        else:
            raise HTTPException(status_code=400, detail=token_json)
            
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"LinkedIn OAuth error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

# ---------------- INSTAGRAM ----------------
@app.get("/oauth/instagram/url")
def instagram_oauth_url(state: str = "instagram_state"):
    if not IG_APP_ID or not IG_REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Instagram app configuration missing")
    return {"url": build_instagram_oauth_url(state)}


@app.post("/oauth/instagram/token")
def instagram_exchange_code(payload: InstagramTokenRequest):
    if not IG_APP_ID or not IG_APP_SECRET or not IG_REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Instagram app configuration missing")
    params = {
        "client_id": IG_APP_ID,
        "client_secret": IG_APP_SECRET,
        "redirect_uri": IG_REDIRECT_URI,
        "code": payload.code,
        "grant_type": "authorization_code",
    }
    res = requests.get("https://graph.facebook.com/v20.0/oauth/access_token", params=params, timeout=20)
    data = res.json()
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])
    return data


@app.get("/instagram/pages")
def instagram_pages(user_token: str = Query(..., description="User access token from Instagram/Facebook login")):
    res = requests.get("https://graph.facebook.com/v20.0/me/accounts", params={"access_token": user_token}, timeout=20)
    data = res.json()
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])
    return data


@app.post("/instagram/publish")
def instagram_publish(payload: InstagramPublishRequest):
    creation_id = create_instagram_media_container(
        ig_user_id=payload.ig_user_id,
        page_token=payload.page_token,
        image_url=payload.image_url,
        caption=payload.caption,
    )
    publish_result = publish_instagram_media(
        ig_user_id=payload.ig_user_id,
        page_token=payload.page_token,
        creation_id=creation_id,
    )
    return {"status": "success", "creation_id": creation_id, "publish_result": publish_result}

@app.post("/upload-csv")
async def upload_csv(
    file: UploadFile = File(...),
    user_id: int = Form(...)
):
    """Upload and process CSV file with user details"""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Invalid file type. Only CSV files allowed.")
    
    try:
        # Read file content
        content = await file.read()
        
        # Decode bytes to string
        content_str = content.decode('utf-8')
        
        # Create a string IO object for csv.DictReader
        csv_file = io.StringIO(content_str)
        
        # Read CSV using DictReader
        reader = csv.DictReader(csv_file)
        
        # Convert to list of dictionaries
        rows = list(reader)
        
        if len(rows) == 0:
            raise HTTPException(status_code=400, detail="CSV file is empty")

        # Get first row
        first_row = rows[0]
        
        # Get column names
        columns = list(reader.fieldnames) if reader.fieldnames else []

        # Extract user details with safe get method
        def safe_get(row, key, default=''):
            return row.get(key, default) if row.get(key) is not None else default

        first_name = safe_get(first_row, 'First Name')
        last_name = safe_get(first_row, 'Last Name')
        full_name = f"{first_name} {last_name}".strip()

        summary = safe_get(first_row, 'Summary')
        industry = safe_get(first_row, 'Industry')
        website = safe_get(first_row, 'Websites')

        # Save to Neon DB
        conn = get_neon_connection()
        cursor = conn.cursor()

        try:
            # Create table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_details (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    name TEXT,
                    about TEXT,
                    industry TEXT,
                    website TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

            # Check if user_details record exists for this user
            cursor.execute("SELECT id FROM user_details WHERE user_id = %s", (user_id,))
            existing_record = cursor.fetchone()

            if existing_record:
                # Update existing record
                cursor.execute("""
                    UPDATE user_details
                    SET name = %s, about = %s, industry = %s, website = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                """, (full_name, summary, industry, website, user_id))
                message = f"User details updated for user_id {user_id}"
            else:
                # Insert new record
                cursor.execute("""
                    INSERT INTO user_details (user_id, name, about, industry, website)
                    VALUES (%s, %s, %s, %s, %s)
                """, (user_id, full_name, summary, industry, website))
                message = f"User details created for user_id {user_id}"

            conn.commit()

            return {
                "filename": file.filename,
                "rows": len(rows),
                "columns": columns,
                "data": rows,
                "message": message
            }

        except psycopg2.Error as db_error:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {str(db_error)}")
        finally:
            cursor.close()
            conn.close()

    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV file encoding error. Please ensure file is UTF-8 encoded.")
    except csv.Error as csv_error:
        raise HTTPException(status_code=400, detail=f"CSV processing error: {str(csv_error)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

class SignupRequest(BaseModel):
    full_name: str
    email: str
    password: str

@app.post("/signup")
def signup(payload: SignupRequest):
    """User signup"""
    conn = get_neon_connection()
    cur = conn.cursor()

    try:
        # Create users table if not exists
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

        # Check if email already exists
        cur.execute("SELECT id FROM users WHERE email=%s", (payload.email,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Email already registered")

        # Insert user
        cur.execute("""
        INSERT INTO users (full_name, email, password) 
        VALUES (%s, %s, %s)
        RETURNING id
        """, (payload.full_name, payload.email, payload.password))
        
        user_id = cur.fetchone()[0]
        conn.commit()
        
        print("✅ Signup successful")
        return {"success": True, "user_id": user_id, "message": "Signup successful"}

    except psycopg2.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Email already registered")
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Signup failed: {str(e)}")
    finally:
        cur.close()
        conn.close()

class SigninRequest(BaseModel):
    email: str
    password: str

@app.post("/login")
def login(payload: SigninRequest):
    """User login"""
    conn = get_neon_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
        SELECT id, full_name, created_at 
        FROM users 
        WHERE email=%s AND password=%s
        """, (payload.email, payload.password))
        
        user = cur.fetchone()

        if user:
            print(f"✅ Login successful. Welcome {user[1]}!")
            return {
                "success": True,
                "user_id": user[0],
                "full_name": user[1],
                "created_at": user[2],
                "message": f"Login successful. Welcome {user[1]}!"
            }
        else:
            raise HTTPException(status_code=401, detail="Invalid email or password")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")
    finally:
        cur.close()
        conn.close()

# ---------------- UTILITY ENDPOINTS ----------------

@app.get("/users")
def get_all_users():
    """Get all users (for admin/debugging)"""
    conn = get_neon_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("SELECT id, full_name, email, created_at FROM users ORDER BY created_at DESC")
        users = cur.fetchall()
        return {"users": users}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching users: {str(e)}")
    finally:
        cur.close()
        conn.close()

@app.get("/user-details")
def get_all_user_details():
    """Get all user details (for admin/debugging)"""
    conn = get_neon_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("""
        SELECT ud.*, u.full_name as user_name, u.email 
        FROM user_details ud 
        LEFT JOIN users u ON ud.user_id = u.id 
        ORDER BY ud.created_at DESC
        """)
        details = cur.fetchall()
        return {"user_details": details}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching user details: {str(e)}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    import os
    
    # Get port from environment (Render sets this automatically)
    port = int(os.getenv("PORT", 8000))
    
    print(f"🚀 Starting FastAPI with Neon DB on port {port}...")
    
class Regen(BaseModel):
    contentRequirements:str
    targetAudience:str
    postTone:str
    access_token: str

@app.post("/regenerateImages")
def regerateImages(payload : Regen):
    client_info = {}
    client_info["contentRequirements"] = payload.contentRequirements
    client_info["targetAudience"] = payload.targetAudience
    client_info["postTone"] = payload.postTone
    
    headers = {"Authorization": f"Bearer {payload.access_token}"}
    
    # Call LinkedIn API to get user URN
    profile_response = requests.get("https://api.linkedin.com/v2/userinfo", headers=headers)
    
    profile_json = profile_response.json()
    linkedin_urn = profile_json.get("sub")
    return regenerate(client_info,payload.access_token,linkedin_urn)

# ---------------- REDDIT ----------------
@app.post("/reddit/post")
def reddit_post(payload: RedditPostRequest):
    try:
        import praw
    except ImportError:
        raise HTTPException(status_code=500, detail="praw is not installed on the server")

    client_id = os.getenv("CLIENT_ID") or os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET") or os.getenv("REDDIT_CLIENT_SECRET")
    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")
    user_agent = os.getenv("USER_AGENT", "InfluenceOS/1.0")

    if not all([client_id, client_secret, username, password, user_agent]):
        raise HTTPException(status_code=500, detail="Missing Reddit credentials in environment")

    if payload.kind not in ("self", "link"):
        raise HTTPException(status_code=400, detail="kind must be 'self' or 'link'")
    if payload.kind == "self" and not payload.text:
        payload.text = ""
    if payload.kind == "link" and not payload.url:
        raise HTTPException(status_code=400, detail="url is required for link posts")

    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            password=password,
            user_agent=user_agent,
        )

        subreddit = reddit.subreddit(payload.subreddit)
        if payload.kind == "self":
            submission = subreddit.submit(title=payload.title, selftext=payload.text)
        else:
            submission = subreddit.submit(title=payload.title, url=payload.url)

        return {"status": "success", "id": submission.id, "permalink": submission.permalink}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reddit post failed: {str(e)}")
