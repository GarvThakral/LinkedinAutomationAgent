# Profile Analysis Data Upload – Influence OS

## 🔄 Profile inputs
We no longer require a `Profile.csv` upload to get started. The API will:
- use the latest profile row in the `user_details` table if you upload one via `/upload-csv` (optional), or
- fall back to LinkedIn `userinfo` (if `ACCESS_TOKEN` is set), or
- return a sensible default placeholder.

---
# 🚀 Backend API Documentation

This is the backend service for the project, built with **FastAPI** and **PostgreSQL**, designed to handle user authentication, LinkedIn integration, content generation, CSV uploads, and posting content to LinkedIn.

You must have a PostgreSQL server running (locally or hosted) and configured with the credentials specified in your .env or the default settings:

text
database = influence
user     = postgres
password = mypassword
host     = localhost
port     = 5432

---

## 📦 Installation & Setup

### 1️⃣ Clone the Repository
git clone https://github.com/GarvThakral/LinkedinAutomationAgent.git
cd LinkedinAutomationAgent


### 2️⃣ Python Version
This project requires **Python 3.11**.  
You can check your version using:
python --version


### 3️⃣ Install Dependencies
Install all required Python packages with:
pip install -r requirements.txt


### 4️⃣ Environment Variables
Create a `.env` file in the project root with the following:

CO_API_KEY = <API_KEY_FOR_LANGCHAIN>
CLIENT_ID = <Your client id>
CLIENT_SECRET = <Your app client secret> 

### 5️⃣ Database Setup
This project uses **PostgreSQL**. Default connection values:
database = influence
user = postgres
password = mypassword
host = localhost
port = 5432

## You must have a PostgreSQL server running (locally or hosted) and configured with the credentials specified in your .env or the default settings:

text
database = influence
user     = postgres
password = mypassword
host     = localhost
port     = 5432

The database will be auto-created if it doesn't exist.

### 6️⃣ Run the Server
Start the development server with:
uvicorn api.index:app --reload

Server will run at:
http://127.0.0.1:8000



---

## 📍 API Endpoints

Below is a detailed documentation of all available API routes.

---

### **1. Get User Details**
**Endpoint:** `GET /user`  
**Description:** Fetches the most recently stored user details from the database.  
**Response:**
{
"name": "John Doe",
"industry": "Tech",
"about": "",
"website": ""
}


---

### **2. Generate LinkedIn Post**
**Endpoint:** `POST /makepost`  
**Description:** Generates content for a LinkedIn carousel post based on user profile & requirements.

**Body:**
{
"contentRequirements": "Share a list of AI productivity tools",
"targetAudience": "Entrepreneurs and tech enthusiasts",
"postTone": "Professional and engaging"
}


---

### **3. Post Content to LinkedIn**
**Endpoint:** `POST /postcontent`  
**Description:** Publishes prepared content to LinkedIn on behalf of the authenticated user.

**Body:**
{
"content_data": "Generated post text",
"image_urls": ["https://example.com/image1.jpg"],
"post_type": "carousel",
"access_token": "<linkedin-oauth-token>"
}


---

### **4. Connect to LinkedIn OAuth**
**Endpoint:** `POST /connectLinkedin`  
**Description:** Exchanges LinkedIn OAuth authorization code for an access token.

**Body:**
{
"code": "<linkedin-oauth-code>"
}


---

### **5. Upload CSV with User Details**
**Endpoint:** `POST /upload-csv`  
**Description:** Uploads a CSV file containing LinkedIn profile data and updates the database.

**Form Data:**
- `file` (CSV file)
- `user_id` (integer - must exist in `users` table)

**Example CSV Columns:**
First Name, Last Name, Summary, Industry, Websites


---

### **6. User Signup**
**Endpoint:** `POST /signup`  
**Description:** Creates a new user account.

**Body:**
{
"full_name": "Alice Johnson",
"email": "alice@example.com",
"password": "mypassword"
}
---

### **7. User Login**
**Endpoint:** `POST /login`  
**Description:** Authenticates a user and returns their ID.

**Body:**
{
"email": "alice@example.com",
"password": "mypassword"
}


---

## 🛠 Tech Stack
- **Python 3.11**
- **FastAPI** - Web framework
- **PostgreSQL** - Database
- **Psycopg2** - PostgreSQL driver
- **Pandas & NumPy** - CSV handling
- **LinkedIn API** - OAuth & posting
- **Instagram Graph API** - OAuth, media publish
- **Reddit API** - OAuth & submissions

---

## 🌐 New social integrations

### Instagram (Graph API)
- `GET /oauth/instagram/url` → returns the login URL.
- `POST /oauth/instagram/token` → exchanges `code` for an access token.
- `GET /instagram/pages?user_token=...` → lists Facebook pages for the authenticated user.
- `POST /instagram/publish` → create & publish an image post (needs `page_token`, `ig_user_id`, `image_url`, `caption`).

Environment:
```
IG_APP_ID=<facebook_app_id>
IG_APP_SECRET=<facebook_app_secret>
IG_REDIRECT_URI=https://yourapp.com/instagram/callback
```

### Reddit
- `GET /oauth/reddit/url` → returns the login URL.
- `POST /oauth/reddit/token` → exchange `code` for access/refresh tokens.
- `POST /reddit/post` → submit a `self` or `link` post (`subreddit`, `title`, `kind`, `text/url`).

Environment:
```
REDDIT_CLIENT_ID=<reddit_app_id>
REDDIT_CLIENT_SECRET=<reddit_app_secret>
REDDIT_REDIRECT_URI=https://yourapp.com/reddit/callback
```

---

## 📌 Notes
- All endpoints accept and return **JSON** unless indicated otherwise.
- CORS is enabled for all origins (`*`), making it compatible with local and hosted frontends.
- The database and required tables are created automatically if they don't exist.

---

## 📜 License
This project is proprietary. All rights reserved.
