from fastapi import FastAPI , File, UploadFile
from src.user_details import get_user_details
from src.run_agent import run_agent
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import requests
import os
import io
import numpy as np
import pandas as pd
load_dotenv()


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or your frontend URL
    allow_credentials=True,
    allow_methods=["*"],  # Important: allows OPTIONS too
    allow_headers=["*"],
)

@app.get("/user")
def user_details():
    return get_user_details()

@app.get('/makepost')
def run_agent_orch():
    return run_agent(    client_info={'name': 'John Doe', 'industry': 'Tech'},
    post_type="article",
    target_industry="Tech",
    content_goals="AI boom post")

class LinkedInData(BaseModel):
    code: str


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
                access_token:access_token
            }
        else:
            return token_json
            
    except Exception as e:
        return {'error':e}



@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        return {"error": "Invalid file type"}
    
    df = pd.read_csv(file.file)

    # Replace NaN/inf with None
    df = df.replace({np.nan: None, np.inf: None, -np.inf: None})

    return {
        "filename": file.filename,
        "rows": len(df),
        "columns": list(df.columns),
        "data": df.to_dict(orient="records")
    }