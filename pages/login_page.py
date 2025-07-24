import dash
from dash import dcc, html

# Define the layout for the login page
layout = html.Div([
    html.Div([
        html.H2("SpectraCell Kit Tracking Login", style={
            'textAlign': 'center',
            'marginBottom': '25px', 
            'color': '#0056b3',    
            'fontWeight': '700'
        }),
        html.P("Enter your password to access the dashboard:", style={
            'textAlign': 'center',
            'marginBottom': '20px', 
            'color': '#343a40',    
            'fontSize': '1.1em' 
        }),
        dcc.Input(
            id='password-input',
            type='password',
            placeholder='Enter password',
            style={
                'width': 'calc(100% - 20px)', 
                'padding': '12px',           
                'margin': '0 auto 20px auto', 
                'display': 'block',
                'border': '1px solid #6c757d', 
                'borderRadius': '5px',       
                'fontSize': '1.0em'          
            }
        ),
        html.Button(
            'Login',
            id='login-button',
            n_clicks=0,
            style={
                'width': 'calc(100% - 20px)', 
                'padding': '12px',          
                'margin': '0 auto',          
                'display': 'block',
                'backgroundColor': '#007bff', 
                'color': 'white',            
                'border': 'none',
                'borderRadius': '5px',
                'cursor': 'pointer',
                'fontSize': '1.1em',
                'fontWeight': '600',        
                'boxShadow': '0 2px 4px rgba(0,0,0,0.1)' 
            }
        ),
        html.Div(id='login-message', style={
            'textAlign': 'center',
            'marginTop': '25px',  
            'color': '#dc3545',  
            'fontWeight': 'bold'  
        })
    ], style={
        'width': '400px',
        'padding': '40px', # Increased padding inside the box
        'boxShadow': '0 8px 16px rgba(0,0,0,0.15)', # More prominent shadow
        'borderRadius': '10px', # Slightly more rounded corners for the box
        'margin': '0 auto', # Set margin to 0 top/bottom, auto left/right for horizontal centering
        'marginTop': '-450px', # <--- Adjust this value to move the box up or down
        'backgroundColor': 'white',
        'boxSizing': 'border-box' # Ensure padding doesn't increase total width
    })
], style={
    'fontFamily': 'Inter, sans-serif', # Applied Inter font
    'backgroundColor': '#f8f9fa',     
    'minHeight': '100vh',
    'display': 'flex',
    'alignItems': 'center',
    'justifyContent': 'center',
    'padding': '20px' # Add some overall padding to prevent content touching edges on small screens
})

# No callbacks are registered directly in this file.
# Login logic will be handled in app.py to manage session state.
def register_callbacks(app):
    pass