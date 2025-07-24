import pandas as pd
import plotly.express as px
from dash import html, dcc
import os

# --- Configuration ---
# Define the directory where data files (out_*.csv and in_*.csv) are located.
# This path is relative to the root of the project (where app.py is typically located).
DATA_DIR = 'data'

# Define the months to process in chronological order using their abbreviations.
months_abbr = ['jan', 'feb', 'march', 'april', 'may', 'june', 'july']

# Map month abbreviations to their full names for better display in charts.
month_name_map = {
    'jan': 'January', 'feb': 'February', 'march': 'March', 'april': 'April',
    'may': 'May', 'june': 'June', 'july': 'July', 'aug': 'August',
    'sep': 'September', 'oct': 'October', 'nov': 'November', 'dec': 'December'
}

# Create an ordered list of full month names based on the abbreviations.
ordered_months = [month_name_map[m] for m in months_abbr]

# Kit to tube mapping: This dictionary defines how many tubes of each type
# are associated with a specific kit name.
# IMPORTANT: These kit names must exactly match the column headers in your 'out_*.csv' files.
kit_to_tube = {
    'MNT & Telomere Kit (2 ACD 1 Blue Sodium Citrate)': {'ACD': 2, 'Blue': 1},
    'MNT Kit Only (2 ACD)': {'ACD': 2},
    'MTHFR Kit (1 Blue Sodium Citrate)': {'Blue': 1},
    'Telomere Kit (1 Blue Sodium Citrate)': {'Blue': 1},
    'Tube - ACD (8.5 mL) Yellow Tops': {'ACD': 1},
    'Tube - Lt. Blue (3mL) Telo/MTHFR-Sodium Citrate': {'Blue': 1},
    'Tube - SST (7.5 mL) Tiger Top': {'SST': 1},
    # Add any missing mappings observed in your actual CSVs to ensure correct processing.
    'MNT & Tel. 1 Blue Sor': {'ACD': 2, 'Blue': 1},
    'MNT Kit O': {'ACD': 2},
    'Tube - ACD Tube': {'ACD': 1},
    'Tube - Lt. LTtube': {'Blue': 1},
    '-SST MNT Kit Only (2 ACD)': {'SST': 1, 'ACD': 2},
}

# Initialize an empty list to store processed dataframes for each month.
all_monthly_data = []

# Define the categories (tube types) to track.
categories = ['ACD', 'Blue', 'Lav', 'SST']

# --- Data Processing Logic (This code runs once when the Dash app starts) ---
print("Starting data processing for Monthly Trends page...")

# Iterate through each defined month to process its outgoing and incoming data.
for month_abbr in months_abbr:
    month_full_name = month_name_map[month_abbr]
    print(f"Processing data for {month_full_name}...")

    # --- Process Outgoing Data (out_*.csv) ---
    # Construct the full file path using os.path.join for cross-platform compatibility.
    outgoing_filename = os.path.join(DATA_DIR, f'out_{month_abbr}.csv')
    try:
        # Check if the outgoing file exists before attempting to read it.
        if not os.path.exists(outgoing_filename):
            raise FileNotFoundError(f"File not found at {outgoing_filename}")

        # Read the outgoing CSV file.
        # header=1: Specifies that the second row (0-indexed) is the header.
        # on_bad_lines='skip': Skips rows that cause parsing errors.
        # engine='python': Used for better handling of on_bad_lines.
        outgoing_df = pd.read_csv(outgoing_filename, header=1, on_bad_lines='skip', engine='python')
        # Strip whitespace from all column names for consistent access.
        outgoing_df.columns = outgoing_df.columns.str.strip()

        # Standardize specific column names if they vary across source files.
        column_rename_map = {
            'Host Code': 'Order_ID',
            'Organization Name': 'Location',
            'Territory Name': 'Location_Code',
            'Sales Rep Full Name': 'SalesRep'
        }
        # Apply renaming only to columns that actually exist in the DataFrame.
        outgoing_df = outgoing_df.rename(columns={k: v for k, v in column_rename_map.items() if k in outgoing_df.columns})

        # Drop a specific duplicate column if it exists, as per previous observations.
        if 'MNT Kit Only (2 ACD).1' in outgoing_df.columns:
            outgoing_df = outgoing_df.drop(columns=['MNT Kit Only (2 ACD).1'])

        # Initialize tube count columns (ACD, Blue, Lav, SST) to 0 for the current month's outgoing data.
        for cat in categories:
            outgoing_df[cat] = 0

        # Calculate tube counts based on the kit_to_tube mapping.
        for kit_col, tube_counts in kit_to_tube.items():
            if kit_col in outgoing_df.columns:
                # Convert the kit count column to numeric, coercing errors to NaN and filling NaN with 0.
                outgoing_df[kit_col] = pd.to_numeric(outgoing_df[kit_col], errors='coerce').fillna(0)
                for tube_type, qty in tube_counts.items():
                    # Only add to defined categories ('ACD', 'Blue', 'Lav', 'SST').
                    if tube_type in categories:
                        outgoing_df[tube_type] += outgoing_df[kit_col] * qty

        # Sum up the total sent tubes for the current month across all defined categories.
        month_total_sent = outgoing_df[categories].sum()

        # Prepare the processed outgoing data for appending to the combined DataFrame.
        df_sent = month_total_sent.reset_index()
        df_sent.columns = ['Tube Type', 'Count'] # Rename columns for consistency.
        df_sent['Type'] = 'Sent' # Label this data as 'Sent'.
        df_sent['Month'] = month_full_name # Add the full month name.
        all_monthly_data.append(df_sent) # Add to the list of all monthly data.
        print(f"    {month_full_name} Outgoing Processed.")

    except FileNotFoundError:
        print(f"    Warning: {outgoing_filename} not found. Skipping {month_full_name} outgoing data.")
    except Exception as e:
        # Catch any other exceptions during outgoing data processing.
        print(f"    Error processing {outgoing_filename}: {e}")

    # --- Process Incoming Data (in_*.csv) ---
    incoming_filename = os.path.join(DATA_DIR, f'in_{month_abbr}.csv')
    try:
        # Check if the incoming file exists.
        if not os.path.exists(incoming_filename):
            raise FileNotFoundError(f"File not found at {incoming_filename}")

        # Read the incoming CSV file.
        # header=None: Reads without assuming a header, so the first row is treated as data.
        incoming_df = pd.read_csv(incoming_filename, header=None)
        # Set the first row as column headers.
        incoming_df.columns = incoming_df.iloc[0]
        # Remove the first row (which is now the header).
        incoming_df = incoming_df[1:]
        # Reset the DataFrame index after removing a row.
        incoming_df = incoming_df.reset_index(drop=True)
        # Strip whitespace from incoming headers.
        incoming_df.columns = incoming_df.columns.str.strip()

        # Rename columns for consistency with the expected 'TubeType' and 'Count'.
        incoming_df = incoming_df.rename(columns={
            'color': 'TubeType', # Assuming 'color' is the column with tube type (e.g., 'ACD', 'Blue')
            'Num': 'Count'       # Assuming 'Num' is the column with the count of tubes
        })

        # Convert 'Count' to numeric, handling potential errors and filling NaN with 0.
        incoming_df['Count'] = pd.to_numeric(incoming_df['Count'], errors='coerce').fillna(0)

        # Ensure 'TubeType' column exists, if not, raise a specific error.
        if 'TubeType' not in incoming_df.columns:
            raise ValueError("Incoming file is missing 'TubeType' column. Please check its header.")

        # Group by TubeType and sum counts, only for defined categories.
        month_total_incoming = incoming_df[incoming_df['TubeType'].isin(categories)].groupby('TubeType')['Count'].sum()
        # Reindex to ensure all categories exist for the month, filling missing with 0.
        # This is crucial so that if a tube type has 0 incoming, it's still represented.
        month_total_incoming = month_total_incoming.reindex(categories, fill_value=0)

        # Prepare the processed incoming data for appending.
        df_returned = month_total_incoming.reset_index()
        df_returned.columns = ['Tube Type', 'Count'] # Rename columns.
        df_returned['Type'] = 'Returned' # Label this data as 'Returned'.
        df_returned['Month'] = month_full_name # Add the full month name.
        all_monthly_data.append(df_returned) # Add to the list.
        print(f"    {month_full_name} Incoming Processed.")

    except FileNotFoundError:
        print(f"    Warning: {incoming_filename} not found. Skipping {month_full_name} incoming data.")
    except Exception as e:
        # Catch any other exceptions during incoming data processing.
        print(f"    Error processing {incoming_filename}: {e}")

# Combine all monthly data into a single DataFrame for plotting.
if all_monthly_data:
    final_combined_df = pd.concat(all_monthly_data, ignore_index=True)
else:
    print("No data processed for any month. Dashboard will be empty.")
    # Create an empty DataFrame with expected columns to prevent errors in Plotly/Dash
    # if no data files are found or processed.
    final_combined_df = pd.DataFrame(columns=['Tube Type', 'Count', 'Type', 'Month', 'Month_TubeType'])

# Create a combined X-axis label: "Month - Tube Type" for better visualization.
if not final_combined_df.empty:
    final_combined_df['Month_TubeType'] = final_combined_df['Month'] + ' - ' + final_combined_df['Tube Type']

    # Ensure the order of months for plotting using a Categorical type.
    # This guarantees that months appear in chronological order on the x-axis.
    final_combined_df['Month'] = pd.Categorical(final_combined_df['Month'], categories=ordered_months, ordered=True)
    # Sort the DataFrame for better plotting order, first by month, then tube type, then type (Sent/Returned).
    final_combined_df = final_combined_df.sort_values(by=['Month', 'Tube Type', 'Type']).reset_index(drop=True)

# Print a preview of the processed data (useful for debugging/verification during local development).
print("\n--- Combined Monthly Data (First 56 Rows) ---")
if not final_combined_df.empty:
    print(final_combined_df.head(56).to_markdown(index=False))
else:
    print("DataFrame for monthly breakdown is empty. No data to display.")


# --- Define the layout for this Dash page ---
# This 'layout' variable will be imported by app.py to display this page in the multi-page app.
layout = html.Div([
    # Page title.
    html.H2("Monthly Tubes Sent vs Returned Overview", style={'textAlign': 'center'}),
    # dcc.Graph is a Dash component used to display Plotly figures.
    dcc.Graph(
        id='monthly-bar-chart',
        figure=px.bar(
            final_combined_df, # The pre-processed DataFrame containing all monthly data.
            x='Month_TubeType', # X-axis: Combined Month and Tube Type for clear grouping.
            y='Count',           # Y-axis: The number of tubes.
            color='Type',        # Color bars based on 'Sent' or 'Returned' type.
            barmode='group',     # Display 'Sent' and 'Returned' bars side-by-side for each Month-TubeType.
            title="Monthly Tubes Sent vs Returned by Type (Jan-July 2025)", # Main chart title.
            labels={'Count': 'Number of Tubes', 'Month_TubeType': 'Month - Tube Type'}, # Customize axis labels.
            hover_data=['Month', 'Tube Type', 'Type', 'Count'], # Data to show when hovering over bars.
            color_discrete_map={'Sent': '#4CAF50', 'Returned': '#2196F3'} # Custom colors for 'Sent' (green) and 'Returned' (blue).
        ).update_layout( # Further customize the chart's layout.
            xaxis_tickangle=-45, # Rotate x-axis labels to prevent overlap, especially with many categories.
            xaxis_title="Month and Tube Type", # Explicit x-axis title.
            yaxis_title="Count",               # Explicit y-axis title.
            legend_title="Type",               # Title for the legend.
            height=600,                        # Set the height of the graph for better viewing.
            margin=dict(l=50, r=50, t=80, b=150) # Adjust margins around the plot area.
        )
    )
])

# --- Register Callbacks (for multi-page Dash apps) ---
# This function is called by the main app.py to register any interactive callbacks
# specific to this page.
def register_callbacks(app):
    pass

