import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import plotly.express as px
import pandas as pd
import os # Import os to access environment variables
import hashlib # For hashing passwords

# Import the layouts and callback registration functions from your page files
from pages import monthly_breakdown, single_month_merger, login_page

# Initialize the Dash app
app = dash.Dash(__name__, use_pages=True, suppress_callback_exceptions=True)

# Define the server variable, which Gunicorn will look for
server = app.server

# --- Security Configuration ---
app.server.secret_key = os.environ.get('SECRET_KEY', 'your_super_secret_key_here_replace_me_in_prod')

# --- Single user ---
VALID_PASSWORD_HASH = '469c34f452736efd07e97f4e3893cb445b179b00ce0871bf329af3a7f97b5095'

# Define the app layout
app.layout = html.Div([
    # dcc.Store to manage login state in the browser session
    dcc.Store(id='login-status', storage_type='session', data={'logged_in': False}),

    # dcc.Location to track URL changes and redirect
    dcc.Location(id='url', refresh=False),

    html.H1("SpectraCell Dashboard", style={'textAlign': 'center', 'color': '#0056b3', 'margin-bottom': '40px'}),

    # Navigation Links (only visible if logged in)
    html.Div(id='navbar-container', children=[
        html.Nav([
            dcc.Link(
                "Monthly Trends",
                href="/monthly-trends",
                style={'margin-right': '20px', 'font-size': '1.2em', 'color': '#007bff', 'text-decoration': 'none'}
            ),
            dcc.Link(
                "Single Month Merger",
                href="/single-month-merger",
                style={'font-size': '1.2em', 'color': '#007bff', 'text-decoration': 'none'}
            ),
            html.A(
                "Logout",
                href="/logout", # This will trigger a logout
                id="logout-link",
                style={'marginLeft': '20px', 'font-size': '1.2em', 'color': 'red', 'text-decoration': 'none'}
            )
        ], style={'textAlign': 'center', 'margin-bottom': '30px'}),
        html.Hr(), # Horizontal line separator
    ], style={'display': 'none'}), # Hidden by default, shown after login

    # Content Area for different pages
    html.Div(id='page-content')
])

# --- Callback to update page content and handle authentication ---
@app.callback(
    Output('page-content', 'children'),
    Output('navbar-container', 'style'), # To show/hide navigation
    Output('login-status', 'data'),      # To update login status on logout
    Input('url', 'pathname'),
    Input('login-status', 'data') # Listen to changes in login status
)
def display_page(pathname, login_data):
    logged_in = login_data and login_data.get('logged_in', False)
    navbar_style = {'display': 'block'} if logged_in else {'display': 'none'}
    
    # Handle logout explicitly
    if pathname == '/logout':
        return login_page.layout, {'display': 'none'}, {'logged_in': False}

    if not logged_in and pathname != '/login':
        # Redirect to login page if not logged in and not already on login page
        return login_page.layout, {'display': 'none'}, dash.no_update
    
    if pathname == '/monthly-trends':
        return monthly_breakdown.layout, navbar_style, dash.no_update
    elif pathname == '/single-month-merger':
        return single_month_merger.layout, navbar_style, dash.no_update
    elif pathname == '/login':
        # If already logged in and tries to go to /login, redirect to monthly trends
        if logged_in:
            return dcc.Location(pathname='/monthly-trends', id='redirect-after-login'), navbar_style, dash.no_update
        return login_page.layout, {'display': 'none'}, dash.no_update
    else:
        # Default page if logged in (e.g., redirect to monthly trends)
        if logged_in:
            return dcc.Location(pathname='/monthly-trends', id='default-redirect'), navbar_style, dash.no_update
        # Default if not logged in
        return login_page.layout, {'display': 'none'}, dash.no_update


# --- Callback to handle login attempt ---
@app.callback(
    Output('login-message', 'children'),
    Output('url', 'pathname', allow_duplicate=True), # Redirect after successful login
    Output('login-status', 'data', allow_duplicate=True), # Update login status
    Input('login-button', 'n_clicks'),
    State('password-input', 'value'),
    prevent_initial_call=True
)
def authenticate(n_clicks, password):
    if n_clicks > 0:
        if password:
            hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()
            if hashed_password == VALID_PASSWORD_HASH:
                return "", "/monthly-trends", {'logged_in': True} # Success: clear message, redirect, set logged_in true
            else:
                return "Incorrect password. Please try again.", dash.no_update, {'logged_in': False} # Failure: error message
        else:
            return "Please enter a password.", dash.no_update, {'logged_in': False}
    return "", dash.no_update, dash.no_update # Default state

# Register callbacks from individual page modules
monthly_breakdown.register_callbacks(app)
single_month_merger.register_callbacks(app)
login_page.register_callbacks(app) # Register the (empty) callback function for login_page

# Run the app locally
if __name__ == '__main__':
    app.run(debug=True)