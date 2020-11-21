import os
import configparser
import time
import requests
import sys
from flask import Flask, g, session, redirect, request, make_response, jsonify, render_template
from requests_oauthlib import OAuth2Session
from struct import pack, unpack

config = configparser.ConfigParser()
config.read('config.ini')
OAUTH2_CLIENT_ID = config['OAUTH2']['ClientID']
OAUTH2_CLIENT_SECRET = config['OAUTH2']['ClientSecret']
OAUTH2_REDIRECT_URI = 'http://distant-horizon.io/authresult'
LOGIN_EXPIRY = float(config['LOGIN']['Timeout'])
SERVER_URL = config['SERVERS']['Address']
SERVER_SECRET = config['SERVERS']['Secret']
API_BASE_URL = 'https://discordapp.com/api'
AUTHORIZATION_BASE_URL = API_BASE_URL + '/oauth2/authorize'
TOKEN_URL = API_BASE_URL + '/oauth2/token'

app = Flask(__name__, template_folder='', static_folder='', static_url_path='')
application = app #for passenger wsgi
app.debug = True
app.config['SECRET_KEY'] = OAUTH2_CLIENT_SECRET

requests.Session().verify = False

if 'http://' in OAUTH2_REDIRECT_URI:
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = 'true'

def load_build_time():
    timestr = ""
    with open('lastbuild.txt', 'r') as file:
        timestr = file.read()
    return int(timestr)
    
BUILD_TIME = load_build_time()

def token_updater(token):
    session['oauth2_token'] = token

def make_session(token=None, state=None, scope=None):
    return OAuth2Session(
        client_id=OAUTH2_CLIENT_ID,
        token=token,
        state=state,
        scope=scope,
        redirect_uri=OAUTH2_REDIRECT_URI,
        auto_refresh_kwargs={
            'client_id': OAUTH2_CLIENT_ID,
            'client_secret': OAUTH2_CLIENT_SECRET,
        },
        auto_refresh_url=TOKEN_URL,
        token_updater=token_updater)

@app.route('/')
def index():
    if session.get('auth_choice_made') and session['auth_choice_made'] == True:
        session['auth_choice_made'] = False
        return render_template("Distant-Horizon.html")
    else:
        return render_template("Welcome.html")
    
@app.route('/quickplay')
def quick_play():
    session['auth_choice_made'] = True
    if 'oauth2_token' in session: 
        session.pop('oauth2_token')
    return redirect('./')
    
@app.route('/authenticate')
def request_auth():
    if 'oauth2_token' in session and session['oauth2_token']:
        session['auth_choice_made'] = True
        return redirect('./')
    discord = make_session(scope=['identify'])
    authorization_url, state = discord.authorization_url(AUTHORIZATION_BASE_URL)
    session['oauth2_state'] = state
    ultimate_url = authorization_url + '&prompt=none'
    return redirect(ultimate_url)


@app.route('/authresult')
def auth_result():
    if request.values.get('error'):
        return request.values['error']
    discord = make_session(state=session.get('oauth2_state'))
    token = discord.fetch_token(
        TOKEN_URL,
        client_secret=OAUTH2_CLIENT_SECRET,
        authorization_response=request.url)
    session['oauth2_token'] = token
    session['auth_choice_made'] = True
    response = make_response(redirect('./'))
    return response

@app.route('/controls')
def controls():
    return render_template("Controls.html")

@app.route('/about')
def about():
    return render_template("About.html")
    
@app.route('/me')
def me():
    discord = make_session(token=session.get('oauth2_token'))
    user = discord.get(API_BASE_URL + '/users/@me').json()
    return jsonify(user=user)

@app.route('/client_login')
def client_begin_login():
    discord = make_session(token=session.get('oauth2_token'))
    user = discord.get(API_BASE_URL + '/users/@me').json()
    server_addr = get_server_address()
    if user and "username" in user and "discriminator" in user:
        request_url = get_server_base_url() + '/prepLogin/' + account_name_from_discord_data(user)
        server_response = requests.get(request_url, verify=False)
        if server_response.status_code == 200:
            return jsonify(logged_in=True, discord_user=user, server_data=server_response.json(), server_address=server_addr)
        else:
            raise ValueError("unable to connect to server at address " + server_addr) 
    else:
        print("unexpected discord response: ", user)
        return jsonify(logged_in=False, server_address=server_addr)
        
@app.route('/account_data')
def get_account_data():
    request_url = get_server_base_url() + '/account/' + account_name_from_discord()
    print("proxying request for account data")
    return requests.get(request_url, verify=False).json()
    
@app.route('/create_actor', methods=["POST"])
def create_actor():
    request_url = 'http://' + SERVER_URL + '/' + SERVER_SECRET + '/account/' + 'asdf' + '/createActor'
    return jsonify(requrl=request_url)
    #print("handling request to create actor, body is ", request.json)
    #result = requests.post(request_url, data={request.json}, verify=False).json()
    #print("proxied request to create actor, result is ", result)
    #return result
   
@app.route('/delete_actor', methods=["POST"])
def delete_actor():
    request_url = '' + '/account/' + account_name_from_discord() + '/deleteActor'
    print("handling request to delete actor, body is ", request.json)
    result = requests.post(request_url, data={request.json}, verify=False).json()
    print("proxied request to delete actor, result is ", result)
    
@app.route('/build_time')
def get_build_time():
    return jsonify(time=BUILD_TIME)

@app.route('/issues')
def go_to_issues():
    return redirect("https://github.com/Dibujaron/DistantHorizonIssues/issues")
    
@app.route('/report_bug')
def report_bug():
    return redirect("https://github.com/Dibujaron/DistantHorizonIssues/issues/new")
    
@app.after_request
def add_header(response):
    response.cache_control.no_cache = True
    return response
    
def get_server_address():
    return select_server()[0]
    
def select_server():
    return [SERVER_URL, SERVER_SECRET]
    
def account_name_from_discord():
    discord = make_session(token=session.get('oauth2_token'))
    user = discord.get(API_BASE_URL + '/users/@me').json()
    return account_name_from_discord_data(user)
    
def account_name_from_discord_data(discord_data):
    if discord_data and "username" in discord_data and "discriminator" in discord_data:
        return discord_data["username"] + discord_data["discriminator"]
    else:
        return None
    
def get_server_base_url():
    server_info = select_server()
    return 'http://' + server_info[0] + '/' + server_info[1]

if __name__ == '__main__':
    app.run()