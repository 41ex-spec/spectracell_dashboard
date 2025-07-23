import dash
from dash import dcc, html

# Define the layout for the login page
layout = html.Div([
    html.Div([
        html.H2("Dashboard Login", style={'textAlign': 'center', 'marginBottom': '20px', 'color': '#333'}),
        html.P("Enter password to access the dashboard:", style={'textAlign': 'center', 'marginBottom': '15px', 'color': '#555'}),
        dcc.Input(
            id='password-input',
            type='password',
            placeholder='Enter password',
            style={
                'width': '80%', 'padding': '10px', 'margin': '0 auto 15px auto',
                'display': 'block', 'border': '1px solid #ddd', 'borderRadius': '5px'
            }
        ),
        html.Button(
            'Login',
            id='login-button',
            n_clicks=0,
            style={
                'width': '80%', 'padding': '10px', 'margin': '0 auto', 'display': 'block',
                'backgroundColor': '#007bff', 'color': 'white', 'border': 'none',
                'borderRadius': '5px', 'cursor': 'pointer', 'fontSize': '1.1em'
            }
        ),
        html.Div(id='login-message', style={'textAlign': 'center', 'marginTop': '20px', 'color': 'red'})
    ], style={
        'width': '400px', 'padding': '30px', 'boxShadow': '0 4px 8px rgba(0,0,0,0.1)',
        'borderRadius': '8px', 'margin': '100px auto', 'backgroundColor': 'white'
    })
], style={'fontFamily': 'Arial, sans-serif', 'backgroundColor': '#f4f4f4', 'minHeight': '100vh', 'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center'})

# No callbacks are registered directly in this file.
# Login logic will be handled in app.py to manage session state.
def register_callbacks(app):
    pass
