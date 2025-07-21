import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd

# Import the layouts and callback registration functions from your page files
from pages import monthly_breakdown, single_month_merger

# Initialize the Dash app
# __name__ is passed to Dash to help it locate assets like CSS
# suppress_callback_exceptions=True is useful for multi-page apps,
# but can hide legitimate errors if not used carefully.
app = dash.Dash(__name__, use_pages=True, suppress_callback_exceptions=True)

# Define the server variable, which Gunicorn will look for
# This is crucial for deployment to Render.
server = app.server

# Define the app layout
app.layout = html.Div([
    # Page Title
    html.H1("SpectraCell Dashboard", style={'textAlign': 'center', 'color': '#0056b3', 'margin-bottom': '40px'}),

    # Navigation Links
    html.Div([
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
    ], style={'textAlign': 'center', 'margin-bottom': '30px'}),

    html.Hr(), # Horizontal line separator

    # Content Area for different pages
    # This dcc.Location component updates the URL
    dcc.Location(id='url', refresh=False),
    # This html.Div will hold the content of the active page
    html.Div(id='page-content')
])

# Callback to update page content based on URL
@app.callback(Output('page-content', 'children'),
              Input('url', 'pathname'))
def display_page(pathname):
    if pathname == '/monthly-trends':
        return monthly_breakdown.layout # Return the layout from monthly_breakdown.py
    elif pathname == '/single-month-merger':
        return single_month_merger.layout # Return the layout from single_month_merger.py
    else:
        # Default page or a welcome page
        return html.Div([
            html.H2("Welcome to the SpectraCell Data Dashboard!", style={'textAlign': 'center', 'margin-top': '50px'}),
            html.P("Use the navigation links above to explore different reports.", style={'textAlign': 'center'})
        ])

# Register callbacks from individual page modules
# This needs to be done *after* the app is initialized and layout is set,
# but before app.run_server() is called.
monthly_breakdown.register_callbacks(app)
single_month_merger.register_callbacks(app)

# Run the app locally
# This block is only executed when app.py is run directly (e.g., python app.py)
# and not when Gunicorn runs it on Render.
if __name__ == '__main__':
    app.run(debug=True) # debug=True enables hot-reloading and helpful error messages