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
