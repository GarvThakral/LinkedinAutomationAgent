from dotenv import load_dotenv
import requests
import pandas as pd
# import psycopg2
from bs4 import BeautifulSoup

def get_user_details():
    access_token = load_dotenv('access_token')
    headers = {"Authorization": f"Bearer {access_token}"}
    profile_response = requests.get("https://api.linkedin.com/v2/userinfo", headers=headers)
    profile_response = profile_response.json()

    data = pd.read_csv("Profile.csv")

    client_name = data['First Name'][0] + " " + data['Last Name'][0]
    about_client = data['Summary'][0]
    client_industry = data['Industry'][0]
    client_website = data["Websites"][0]

    client_info = {
        'name':client_name,
        'about':about_client,
        'industry':client_industry,
        'website':client_website
    }

    if pd.isna(client_website):
        print(f"client_website contains: nan")
        client_info['website'] = ''
    else:
        page = requests.get("https://portfoliofinal-blond.vercel.app/")
        soup = BeautifulSoup(page.content, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)
        print(text)
    print(client_info)
    return client_info


# Step 1: connect to the default 'postgres' DB first
# conn = psycopg2.connect(
#     database="influence",   
#     user="postgres",
#     host="localhost",
#     password="mypassword",
#     port="5432"
# )

# cursor = conn.cursor()

# cursor.execute("")

# cursor.close()
# conn.close()
