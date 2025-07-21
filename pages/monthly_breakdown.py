import pandas as pd
import plotly.express as px
from dash import html, dcc
import os

# --- Configuration ---
# This DATA_DIR is relative to the root of the project (where app.py is)
# So if app.py is in spectracell_dashboard/, and data/ is inside spectracell_dashboard/,
# then 'data' is the correct path here.
DATA_DIR = 'data'

# Define the months to process in chronological order
months_abbr = ['jan', 'feb', 'march', 'april', 'may', 'june', 'july']
month_name_map = {
    'jan': 'January', 'feb': 'February', 'march': 'March', 'april': 'April',
    'may': 'May', 'june': 'June', 'july': 'July', 'aug': 'August',
    'sep': 'September', 'oct': 'October', 'nov': 'November', 'dec': 'December'
}
ordered_months = [month_name_map[m] for m in months_abbr]

# Kit to tube mapping
# IMPORTANT: Ensure these match exact kit names in your 'out_*.csv' files
kit_to_tube = {
    'MNT & Telomere Kit (2 ACD 1 Blue Sodium Citrate)': {'ACD': 2, 'Blue': 1},
    'MNT Kit Only (2 ACD)': {'ACD': 2},
    'MTHFR Kit (1 Blue Sodium Citrate)': {'Blue': 1},
    'Telomere Kit (1 Blue Sodium Citrate)': {'Blue': 1},
    'Tube - ACD (8.5 mL) Yellow Tops': {'ACD': 1},
    'Tube - Lt. Blue (3mL) Telo/MTHFR-Sodium Citrate': {'Blue': 1},
    'Tube - SST (7.5 mL) Tiger Top': {'SST': 1},
    # Add any missing mappings you observed during previous debugging or in your actual CSVs:
    'MNT & Tel. 1 Blue Sor': {'ACD': 2, 'Blue': 1},
    'MNT Kit O': {'ACD': 2},
    'Tube - ACD Tube': {'ACD': 1},
    'Tube - Lt. LTtube': {'Blue': 1},
    '-SST MNT Kit Only (2 ACD)': {'SST': 1, 'ACD': 2},
}

all_monthly_data = []
categories = ['ACD', 'Blue', 'Lav', 'SST'] # Define tube categories

# --- Data Processing Logic (This code runs once when the Dash app starts) ---
print("Starting data processing for Monthly Trends page...")
for month_abbr in months_abbr:
    month_full_name = month_name_map[month_abbr]
    print(f"Processing data for {month_full_name}...")

    # --- Process Outgoing Data ---
    # Use os.path.join to correctly build the file path, compatible across OS
    outgoing_filename = os.path.join(DATA_DIR, f'out_{month_abbr}.csv')
    try:
        # Check if the file exists before attempting to read
        if not os.path.exists(outgoing_filename):
            raise FileNotFoundError(f"File not found at {outgoing_filename}")

        # Read CSV, skipping first header row (header=1)
        outgoing_df = pd.read_csv(outgoing_filename, header=1, on_bad_lines='skip', engine='python')
        outgoing_df.columns = outgoing_df.columns.str.strip() # Strip whitespace from column names

        # Standardize specific column names if they vary in source files
        column_rename_map = {
            'Host Code': 'Order_ID',
            'Organization Name': 'Location',
            'Territory Name': 'Location_Code',
            'Sales Rep Full Name': 'SalesRep'
        }
        # Only rename columns that actually exist in the DataFrame
        outgoing_df = outgoing_df.rename(columns={k: v for k, v in column_rename_map.items() if k in outgoing_df.columns})

        # Drop the duplicate column if it exists, as per your original code
        if 'MNT Kit Only (2 ACD).1' in outgoing_df.columns:
            outgoing_df = outgoing_df.drop(columns=['MNT Kit Only (2 ACD).1'])

        # Initialize tube count columns for the current month's outgoing data
        for cat in categories:
            outgoing_df[cat] = 0

        # Calculate tube counts based on kit_to_tube mapping
        for kit_col, tube_counts in kit_to_tube.items():
            if kit_col in outgoing_df.columns:
                # Ensure kit count column is numeric to avoid errors in multiplication
                outgoing_df[kit_col] = pd.to_numeric(outgoing_df[kit_col], errors='coerce').fillna(0)
                for tube_type, qty in tube_counts.items():
                    if tube_type in categories: # Only add to defined categories ('ACD', 'Blue', 'Lav', 'SST')
                        outgoing_df[tube_type] += outgoing_df[kit_col] * qty

        # Sum up total sent tubes for the current month across defined categories
        month_total_sent = outgoing_df[categories].sum()

        # Prepare data for the combined DataFrame
        df_sent = month_total_sent.reset_index()
        df_sent.columns = ['Tube Type', 'Count']
        df_sent['Type'] = 'Sent'
        df_sent['Month'] = month_full_name # Use full month name for display
        all_monthly_data.append(df_sent)
        print(f"   {month_full_name} Outgoing Processed.")

    except FileNotFoundError:
        print(f"   Warning: {outgoing_filename} not found. Skipping {month_full_name} outgoing data.")
    except Exception as e:
        print(f"   Error processing {outgoing_filename}: {e}")

    # --- Process Incoming Data ---
    incoming_filename = os.path.join(DATA_DIR, f'in_{month_abbr}.csv')
    try:
        if not os.path.exists(incoming_filename):
            raise FileNotFoundError(f"File not found at {incoming_filename}")

        # Read CSV, assuming no header row for the data itself (header=None), then manually set header
        incoming_df = pd.read_csv(incoming_filename, header=None)
        incoming_df.columns = incoming_df.iloc[0] # Set the first row as column headers
        incoming_df = incoming_df[1:] # Remove the first row (which is now the header)
        incoming_df = incoming_df.reset_index(drop=True) # Reset index after removing row
        incoming_df.columns = incoming_df.columns.str.strip() # Strip whitespace from incoming headers too

        # Rename columns for consistency
        incoming_df = incoming_df.rename(columns={
            'color': 'TubeType', # Assuming 'color' is the column with tube type (e.g., 'ACD', 'Blue')
            'Num': 'Count'       # Assuming 'Num' is the column with the count of tubes
        })

        # Convert 'Count' to numeric, handling potential errors and filling NaN with 0
        incoming_df['Count'] = pd.to_numeric(incoming_df['Count'], errors='coerce').fillna(0)
        
        # Ensure 'TubeType' column exists, if not, raise a specific error
        if 'TubeType' not in incoming_df.columns:
             raise ValueError("Incoming file is missing 'TubeType' column. Please check its header.")
        
        # Group by TubeType and sum counts, only for defined categories
        month_total_incoming = incoming_df[incoming_df['TubeType'].isin(categories)].groupby('TubeType')['Count'].sum()
        # Reindex to ensure all categories exist for the month, filling missing with 0
        month_total_incoming = month_total_incoming.reindex(categories, fill_value=0)

        # Prepare data for the combined DataFrame
        df_returned = month_total_incoming.reset_index()
        df_returned.columns = ['Tube Type', 'Count']
        df_returned['Type'] = 'Returned'
        df_returned['Month'] = month_full_name # Use full month name
        all_monthly_data.append(df_returned)
        print(f"   {month_full_name} Incoming Processed.")

    except FileNotFoundError:
        print(f"   Warning: {incoming_filename} not found. Skipping {month_full_name} incoming data.")
    except Exception as e:
        print(f"   Error processing {incoming_filename}: {e}")

# Combine all monthly data into a single DataFrame
if all_monthly_data:
    final_combined_df = pd.concat(all_monthly_data, ignore_index=True)
else:
    print("No data processed for any month. Dashboard will be empty.")
    # Create an empty DataFrame with expected columns to prevent errors in Plotly/Dash
    final_combined_df = pd.DataFrame(columns=['Tube Type', 'Count', 'Type', 'Month', 'Month_TubeType'])

# Create a combined X-axis label: "Month - Tube Type"
if not final_combined_df.empty:
    final_combined_df['Month_TubeType'] = final_combined_df['Month'] + ' - ' + final_combined_df['Tube Type']

    # Ensure the order of months for plotting using a Categorical type
    final_combined_df['Month'] = pd.Categorical(final_combined_df['Month'], categories=ordered_months, ordered=True)
    # Sort the DataFrame for better plotting order
    final_combined_df = final_combined_df.sort_values(by=['Month', 'Tube Type', 'Type']).reset_index(drop=True)

# Print a preview of the processed data (for debugging/verification during local run)
print("\n--- Combined Monthly Data (First 56 Rows) ---")
if not final_combined_df.empty:
    print(final_combined_df.head(56).to_markdown(index=False))
else:
    print("DataFrame for monthly breakdown is empty. No data to display.")


# --- Define the layout for this page ---
# This 'layout' variable will be imported by app.py to display this page
layout = html.Div([
    html.H2("Monthly Tubes Sent vs Returned Overview", style={'textAlign': 'center'}),
    # dcc.Graph is used to display Plotly figures
    dcc.Graph(
        id='monthly-bar-chart',
        figure=px.bar(
            final_combined_df, # The pre-processed DataFrame
            x='Month_TubeType', # Combined Month and Tube Type on X-axis
            y='Count',
            color='Type', # Color bars by 'Sent' or 'Returned'
            barmode='group', # Group Sent and Returned bars side-by-side
            title="Monthly Tubes Sent vs Returned by Type (Jan-July 2025)", # Chart title
            labels={'Count': 'Number of Tubes', 'Month_TubeType': 'Month - Tube Type'}, # Axis labels
            hover_data=['Month', 'Tube Type', 'Type', 'Count'], # Show detailed info on hover
            color_discrete_map={'Sent': '#4CAF50', 'Returned': '#2196F3'} # Custom colors
        ).update_layout( # Further layout customizations
            xaxis_tickangle=-45, # Rotate x-axis labels for readability
            xaxis_title="Month and Tube Type",
            yaxis_title="Count",
            legend_title="Type",
            height=600, # Adjust height for better viewing
            margin=dict(l=50, r=50, t=80, b=150) # Adjust margins
        )
    )
])

# --- Register Callbacks (for multi-page Dash apps) ---
# This function is called by the main app.py to register any interactive callbacks
# specific to this page. Currently, this page is static, so no callbacks are defined here.
def register_callbacks(app):
    # No callbacks to register for this static page yet.
    # If you later add interactive elements (e.g., dropdowns, sliders) to this page,
    # you would define their @app.callback functions here.
    pass