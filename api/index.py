from fastapi import FastAPI
from src.user_details import get_user_details
from src.run_agent import run_agent
app = FastAPI()

@app.get("/user")
def user_details():
    return get_user_details()

@app.get('/makepost')
def run_agent_orch():
    return run_agent()