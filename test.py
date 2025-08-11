from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Your LinkedIn app credentials

@app.route('/')
def home():
    """Home page with OAuth link"""
    oauth_url = f"https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope=w_member_social&state=random123"
    
    return f'''
    <h1>LinkedIn OAuth Test</h1>
    <a href="{oauth_url}">Click here to authorize with LinkedIn</a>
    '''

@app.route('/callback')
def callback():
    """Handle the OAuth callback"""
    # Get the authorization code from the callback
    code = request.args.get('code')
    error = request.args.get('error')
    state = request.args.get('state')
    
    if error:
        return f"<h1>Error:</h1><p>{error}</p><p>Description: {request.args.get('error_description')}</p>"
    
    if not code:
        return "<h1>Error:</h1><p>No authorization code received</p>"
    
    # Exchange authorization code for access token
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    token_data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
    }
    
    try:
        token_response = requests.post(token_url, data=token_data)
        token_json = token_response.json()
        
        if 'access_token' in token_json:
            access_token = token_json['access_token']
            expires_in = token_json.get('expires_in', 'Unknown')
            
            return f'''
            <h1>Success!</h1>
            <p><strong>Authorization Code:</strong> {code}</p>
            <p><strong>Access Token:</strong> {access_token[:20]}...</p>
            <p><strong>Expires in:</strong> {expires_in} seconds</p>
            <p><strong>State:</strong> {state}</p>
            
            <h2>Token Response:</h2>
            <pre>{token_json}</pre>
            '''
        else:
            return f'''
            <h1>Token Exchange Failed</h1>
            <p><strong>Response:</strong></p>
            <pre>{token_json}</pre>
            '''
            
    except Exception as e:
        return f"<h1>Error exchanging token:</h1><p>{str(e)}</p>"

@app.route('/test')
def test():
    """Simple test endpoint"""
    return "<h1>Server is running!</h1><p>Go to <a href='/'>home</a> to start OAuth flow</p>"

if __name__ == '__main__':
    print("Starting server on http://localhost:8000")
    print("Go to http://localhost:8000 to start the OAuth flow")
    app.run(host='localhost', port=8000, debug=True)