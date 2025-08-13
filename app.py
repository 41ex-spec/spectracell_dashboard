import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import plotly.express as px
import pandas as pd
import os
import hashlib

# Import layouts and callback registration functions from page files.
from pages import monthly_breakdown, single_month_merger, login_page

# Initialize the Dash app.
app = dash.Dash(__name__, use_pages=True, suppress_callback_exceptions=True)

# Define the server variable for production deployment.
server = app.server

# --- Security Configuration ---
# Set a secret key for the Flask server.
app.server.secret_key = os.environ.get('SECRET_KEY', 'your_super_secret_key_here_replace_me_in_prod')

# --- Basic Single-User Authentication ---
VALID_PASSWORD_HASH = '469c34f452736efd07e97f4e3893cb445b179b00ce0871bf329af3a7f97b5095'

# Define the main application layout.
app.layout = html.Div([
    # dcc.Store to manage login state.
    dcc.Store(id='login-status', storage_type='session', data={'logged_in': False}),

    # dcc.Location to track URL changes and redirect.
    dcc.Location(id='url', refresh=False),

    # Main dashboard title.
    html.H1("SpectraCell Kit Tracking Dashboard", style={
        'textAlign': 'center',
        'color': '#0056b3',
        'margin-bottom': '40px',
        'padding-top': '20px',
        'fontFamily': 'Inter, sans-serif'
    }),

    # Navigation Links Container, conditionally displayed.
    html.Div(id='navbar-container', children=[
        html.Nav([
            # Link to Monthly Trends page.
            dcc.Link(
                "Monthly Trends",
                href="/monthly-trends",
                style={
                    'margin-right': '25px',
                    'font-size': '1.15em',
                    'color': '#007bff',
                    'text-decoration': 'none',
                    'fontWeight': '600',
                    'padding': '8px 12px',
                    'borderRadius': '5px',
                    'transition': 'background-color 0.3s ease, color 0.3s ease'
                },
                className='nav-link'
            ),
            # Link to Single Month Merger page.
            dcc.Link(
                "Single Month Merger",
                href="/single-month-merger",
                style={
                    'font-size': '1.15em',
                    'color': '#007bff',
                    'text-decoration': 'none',
                    'fontWeight': '600',
                    'padding': '8px 12px',
                    'borderRadius': '5px',
                    'transition': 'background-color 0.3s ease, color 0.3s ease'
                },
                className='nav-link'
            ),
            # Logout link.
            html.A(
                "Logout",
                href="/logout",
                id="logout-link",
                style={
                    'marginLeft': '25px',
                    'font-size': '1.15em',
                    'color': '#dc3545',
                    'text-decoration': 'none',
                    'fontWeight': '600',
                    'padding': '8px 12px',
                    'borderRadius': '5px',
                    'transition': 'background-color 0.3s ease, color 0.3s ease'
                },
                className='nav-link'
            )
        ], style={
            'textAlign': 'center',
            'margin-bottom': '30px',
            'backgroundColor': '#e9ecef',
            'padding': '15px 0',
            'borderRadius': '8px',
            'boxShadow': '0 2px 4px rgba(0,0,0,0.08)'
        }),
        html.Hr(style={'margin': '30px 0', 'borderTop': '1px solid #dee2e6'}),
    ], style={'display': 'none'}),

    # Content Area for different pages.
    html.Div(id='page-content', style={'padding': '20px'})
], style={
    'fontFamily': 'Inter, sans-serif',
    'backgroundColor': '#f8f9fa',
    'minHeight': '100vh',
    'padding': '0 20px'
})

# --- Callback to update page content and handle authentication/redirection ---
@app.callback(
    Output('page-content', 'children'),
    Output('navbar-container', 'style'),
    Output('login-status', 'data'),
    Input('url', 'pathname'),
    Input('login-status', 'data')
)
def display_page(pathname, login_data):
    logged_in = login_data and login_data.get('logged_in', False)
    navbar_style = {'display': 'block'} if logged_in else {'display': 'none'}
    
    # Handle explicit logout request.
    if pathname == '/logout':
        return login_page.layout, {'display': 'none'}, {'logged_in': False}

    # Redirect to login page if not logged in and not already on login page.
    if not logged_in and pathname != '/login':
        return login_page.layout, {'display': 'none'}, dash.no_update
    
    # Route to the appropriate page based on the pathname.
    if pathname == '/monthly-trends':
        return monthly_breakdown.layout, navbar_style, dash.no_update
    elif pathname == '/single-month-merger':
        return single_month_merger.layout, navbar_style, dash.no_update
    elif pathname == '/login':
        # If already logged in and tries to go to /login, redirect.
        if logged_in:
            # Changed default redirect after login to single-month-merger
            return dcc.Location(pathname='/single-month-merger', id='redirect-after-login'), navbar_style, dash.no_update
        return login_page.layout, {'display': 'none'}, dash.no_update
    else:
        # Default page handling based on login status.
        if logged_in:
            # Changed default redirect to single-month-merger
            return dcc.Location(pathname='/single-month-merger', id='default-redirect'), navbar_style, dash.no_update
        return login_page.layout, {'display': 'none'}, dash.no_update


# --- Callback to handle login attempt ---
@app.callback(
    Output('login-message', 'children'),
    Output('url', 'pathname', allow_duplicate=True),
    Output('login-status', 'data', allow_duplicate=True),
    Input('login-button', 'n_clicks'),
    State('password-input', 'value'),
    prevent_initial_call=True
)
def authenticate(n_clicks, password):
    if n_clicks > 0:
        if password:
            hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()
            if hashed_password == VALID_PASSWORD_HASH:
                # Direct to single-month-merger after successful authentication
                return "", "/single-month-merger", {'logged_in': True}
            else:
                return html.Span("Incorrect password. Please try again.", style={'color': '#dc3545', 'fontWeight': 'bold'}), dash.no_update, {'logged_in': False}
        else:
            return html.Span("Please enter a password.", style={'color': '#ffc107', 'fontWeight': 'bold'}), dash.no_update, {'logged_in': False}
    return "", dash.no_update, dash.no_update

# Register callbacks from individual page modules.
monthly_breakdown.register_callbacks(app)
single_month_merger.register_callbacks(app)
login_page.register_callbacks(app) 

# Run the app locally.
if __name__ == '__main__':
    app.run(debug=True)
