# Profile Analysis Data Upload – Influence OS

## 📋 Why we ask for a data upload
LinkedIn's public API for individual developers **does not** allow full access to a user's work history, skills, endorsements, or past posts.  
These fields are restricted to **LinkedIn Marketing Developer Platform** or **Talent Solutions** partners, which require a lengthy approval process that is not feasible within our project timeline.

**With standard developer access**, we can only fetch:
- Name
- Profile picture
- Email (if authorized)

This is **not enough** for meaningful content personalization.  
To give you a truly personalized experience, we request your **profile export** directly from LinkedIn.

---

## 📤 How to get your LinkedIn data export

1. **Open LinkedIn in your browser** and log in.
2. Go to:
3. Select **"Download larger data archive"** (recommended) or **"Profile information"** only.
4. Click **Request archive** and complete any verification steps.
5. LinkedIn will email you a download link (usually within 10 minutes).
6. Unzip the archive on your computer.

---

## 📥 Upload your profile data to Influence OS

1. From the extracted files, find:
- `Profile.json` (contains work history, skills, and about section)
2. Go to the **Profile Upload** section of our app.
3. Drag and drop `Profile.json` into the upload box.
4. We will parse and analyze:
- Work history
- Skills
- Interests
- Summary/About text
5. Your data is processed **locally** on our server, stored securely, and only used for AI-driven post generation.

---

## 🔒 Data privacy
- We do **not** store your archive in raw form — only parsed, relevant fields.
- Your data is **never shared** with third parties.
- You can request deletion of your stored profile data at any time.

---

## 📚 Technical note
We chose this approach because:
- **LinkedIn API restriction**: Full profile data endpoints are partner-only.
- **Compliance**: Downloading your own data and uploading it voluntarily complies with LinkedIn's Terms of Service and privacy policy.
- **Control**: Users decide exactly what data to share with our AI engine.

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

---

## 📌 Notes
- All endpoints accept and return **JSON** unless indicated otherwise.
- CORS is enabled for all origins (`*`), making it compatible with local and hosted frontends.
- The database and required tables are created automatically if they don't exist.

---

## 📜 License
This project is proprietary. All rights reserved.
