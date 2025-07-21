import dash
from dash.dependencies import Input, Output, State
from dash import dcc, html, dash_table
import pandas as pd
import base64
import io
import datetime
import re

# --- Kit to tube mapping (kept as it's core to the outbound data processing) ---
# IMPORTANT: Ensure these match exact kit names in your 'out_*.csv' files
kit_to_tube = {
    'MNT & Telomere Kit (2 ACD, 1 Blue Sodium Citrate)': {'ACD': 2, 'Blue': 1},
    'MNT Kit Only (2 ACD)': {'ACD': 2},
    'MTHFR Kit (1 Blue Sodium Citrate)': {'Blue': 1},
    'Telomere Kit (1 Blue Sodium Citrate)': {'Blue': 1},
    'Tube - ACD (8.5 mL) Yellow Tops': {'ACD': 1},
    'Tube - Lt. Blue (3mL) Telo/MTHFR-Sodium Citrate': {'Blue': 1},
    'Tube - SST (7.5 mL) Tiger Top': {'SST': 1},
    # Additional mappings for common variations or typos found in your data:
    'MNT & Tel. 1 Blue Sor': {'ACD': 2, 'Blue': 1},
    'MNT Kit O': {'ACD': 2},
    'Tube - ACD Tube': {'ACD': 1},
    'Tube - Lt. LTtube': {'Blue': 1}, # Assuming 'LTtube' is a typo or shorthand for 'Lt. Blue'
    '-SST MNT Kit Only (2 ACD)': {'SST': 1, 'ACD': 2}, # Example of a kit that might contain SST and ACD
}

# --- Helper function to parse uploaded content ---
# This function is designed to be robust and provide specific error messages
def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    df = None
    error_message = None

    try:
        # Determine if it's an outbound or inbound file based on filename pattern
        is_outbound = "out_" in filename
        is_inbound = "in_" in filename

        if is_outbound and filename.endswith(".csv"):
            # Outbound file processing (assuming header on 2nd row, i.e., header=1)
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')), header=1, on_bad_lines='skip', engine='python')
            df.columns = df.columns.str.strip() # Clean column names

            # --- CRITICAL FIX: Explicitly rename core columns for outbound file ---
            # These are the columns expected to be used as 'fixed_id_cols'
            expected_outbound_columns = {
                'Host Code': 'Order_ID',
                'Organization Name': 'Location',
                'Territory Name': 'Location_Code',
                'Sales Rep Full Name': 'SalesRep'
            }

            # Only rename columns that exist in the DataFrame
            columns_to_rename = {k: v for k, v in expected_outbound_columns.items() if k in df.columns}
            df = df.rename(columns=columns_to_rename)

            # Ensure the expected fixed ID columns are now present after renaming
            required_outbound_cols = ['Order_ID', 'Location', 'Location_Code', 'SalesRep']
            for col in required_outbound_cols:
                if col not in df.columns:
                    error_message = f"Missing required column '{col}' after renaming in Outbound file. Please check your CSV header structure."
                    return None, error_message

            # Drop the duplicate column if it exists, as per your original code
            if 'MNT Kit Only (2 ACD).1' in df.columns:
                df = df.drop(columns=['MNT Kit Only (2 ACD).1'])

            # Extract YearMonth from filename (e.g., "out_june.csv" -> 2025-06-01)
            # Assuming current year for the files based on 'now()'.
            # For robust production, you might want to infer year from data or add a year input.
            month_name_abbr = filename.split('_')[1].split('.')[0] # e.g., 'jan'
            current_year = datetime.datetime.now().year

            # More robust month parsing for various short forms
            month_num = None
            try:
                month_num = datetime.datetime.strptime(month_name_abbr, '%b').month # Try 'Jan', 'Feb', etc.
            except ValueError:
                try:
                    month_num = datetime.datetime.strptime(month_name_abbr, '%B').month # Try 'January', 'February', etc.
                except ValueError:
                    # Fallback for common short forms not covered by %b or %B
                    month_map = {
                        'jan': 1, 'feb': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
                        'july': 7, 'aug': 8, 'sept': 9, 'oct': 10, 'nov': 11, 'dec': 12
                    }
                    month_num = month_map.get(month_name_abbr.lower())

            if month_num is None:
                error_message = f"Could not determine month from outbound filename: {filename}. Please ensure it follows 'out_MONTH.csv' format (e.g., out_jan.csv)."
                return None, error_message

            df['YearMonth'] = pd.to_datetime(f"{current_year}-{month_num:02d}-01")

            # Identify fixed ID columns and kit type columns
            fixed_id_cols = ['Order_ID', 'Location', 'Location_Code', 'SalesRep', 'YearMonth']
            # Find kit columns by checking against kit_to_tube keys
            kit_cols = [col for col in df.columns if col not in fixed_id_cols and col in kit_to_tube]

            if not kit_cols:
                error_message = "No kit type columns found matching 'kit_to_tube' keys. " \
                                "Please ensure keys in 'kit_to_tube' exactly match actual kit column headers in your CSV."
                return None, error_message

            # Melt the DataFrame to transform kit columns into rows
            id_vars_for_melt = [col for col in df.columns if col not in kit_cols]
            df_melted = df.melt(id_vars=id_vars_for_melt,
                                 var_name='KitDescription',
                                 value_name='KitCount')

            # Convert KitCount to numeric, handling non-numeric entries
            df_melted['KitCount'] = pd.to_numeric(df_melted['KitCount'], errors='coerce').fillna(0)
            df_melted = df_melted[df_melted['KitCount'] > 0] # Filter out zero or NaN counts

            # Initialize tube type columns for calculation
            for tube_type in ['ACD', 'Blue', 'Lav', 'SST']: # Define all possible tube types
                df_melted[tube_type] = 0

            # Distribute tubes based on kit_to_tube mapping
            for index, row in df_melted.iterrows():
                kit_desc = str(row['KitDescription']) # Ensure it's a string for dictionary lookup
                kit_count = row['KitCount']
                if kit_desc in kit_to_tube:
                    for tube_type_in_kit, qty_per_kit in kit_to_tube[kit_desc].items():
                        # Add calculated tubes to the corresponding tube type column
                        df_melted.at[index, tube_type_in_kit] += kit_count * qty_per_kit

            # Melt again to aggregate the tube counts by tube type
            df_outbound_tubes = df_melted.melt(
                id_vars=[col for col in df_melted.columns if col not in ['ACD', 'Blue', 'Lav', 'SST', 'KitDescription', 'KitCount']],
                value_vars=['ACD', 'Blue', 'Lav', 'SST'],
                var_name='TubeType',
                value_name='TubesSent'
            )
            df_outbound_tubes = df_outbound_tubes[df_outbound_tubes['TubesSent'] > 0] # Keep only tubes that were sent
            # Final aggregation for outbound data: sum TubesSent by Location, YearMonth, TubeType
            df_outbound_tubes = df_outbound_tubes.groupby(['Location', 'YearMonth', 'TubeType']).agg(TubesSent=('TubesSent', 'sum')).reset_index()

            return df_outbound_tubes, None

        elif is_inbound and filename.endswith(".csv"):
            # Inbound file processing
            # Assuming header is the first row and data starts from the second row
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')), header=None)
            df.columns = df.iloc[0] # Set the first row as column headers
            df = df[1:] # Remove the first row (now the header)
            df.columns = df.columns.str.strip() # Clean column names

            df = df.rename(columns={
                'color': 'TubeType', # Standardize 'color' column to 'TubeType'
                'Num': 'Count'       # Standardize 'Num' column to 'Count'
            })
            df['Count'] = pd.to_numeric(df['Count'], errors='coerce').fillna(0) # Ensure count is numeric

            # Check for essential 'YearMonth' column
            if 'YearMonth' not in df.columns:
                error_message = "Missing 'YearMonth' column in Incoming file. Please check its header."
                return None, error_message

            # Convert 'YearMonth' to datetime, handling errors (e.g., if format is %Y%m)
            df['YearMonth'] = pd.to_datetime(df['YearMonth'], format='%Y%m', errors='coerce')
            df = df.dropna(subset=['YearMonth']) # Remove rows where YearMonth couldn't be parsed

            # Aggregate incoming samples by Location, YearMonth, and TubeType
            df_inbound_agg = df.groupby(['Location', 'YearMonth', 'TubeType']).agg(TubesReturned=('Count', 'sum')).reset_index()

            return df_inbound_agg, None

        else:
            return None, "Unsupported file name. Please upload 'out_MONTH.csv' or 'in_MONTH.csv'."

    except Exception as e:
        import traceback
        traceback.print_exc() # Print full traceback to console for detailed debugging
        print(f"Error parsing file {filename}: {e}")
        return None, f"Error processing {filename}. Please check file format and column names: {e}"

# --- Define the layout for this page ---
# This 'layout' variable will be imported by app.py to display this page
layout = html.Div([
    html.H2("Single Month Kit Data Merger", style={'textAlign': 'center', 'color': '#333', 'margin-bottom': '30px'}),

    html.Div([
        html.Div([
            html.H3("Upload Outbound Kits Report (e.g., out_jan.csv)", style={'color': '#555'}),
            dcc.Upload(
                id='upload-outbound-data',
                children=html.Div(['Drag and Drop or ', html.A('Select File')]),
                style={
                    'width': '100%', 'height': '60px', 'lineHeight': '60px',
                    'borderWidth': '1px', 'borderStyle': 'dashed', 'borderRadius': '5px',
                    'textAlign': 'center', 'margin': '10px 0'
                },
                multiple=False, # Only allow one file at a time
                accept='.csv'    # Only accept CSV files
            ),
            html.Div(id='outbound-upload-status', style={'color': 'green', 'textAlign': 'center'}),
        ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top', 'marginRight': '2%'}),

        html.Div([
            html.H3("Upload Inbound Samples Report (e.g., in_jan.csv)", style={'color': '#555'}),
            dcc.Upload(
                id='upload-inbound-data',
                children=html.Div(['Drag and Drop or ', html.A('Select File')]),
                style={
                    'width': '100%', 'height': '60px', 'lineHeight': '60px',
                    'borderWidth': '1px', 'borderStyle': 'dashed', 'borderRadius': '5px',
                    'textAlign': 'center', 'margin': '10px 0'
                },
                multiple=False,
                accept='.csv'
            ),
            html.Div(id='inbound-upload-status', style={'color': 'green', 'textAlign': 'center'}),
        ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top', 'marginLeft': '2%'}),
    ], style={'display': 'flex', 'justifyContent': 'center', 'margin-bottom': '40px'}),

    html.Div(id='merge-status', style={'textAlign': 'center', 'margin-bottom': '20px', 'font-weight': 'bold'}),

    # dcc.Store components are used to temporarily store data in the browser's memory
    # This prevents re-processing files unnecessarily and allows data to be shared between callbacks
    dcc.Store(id='outbound-data-store'),
    dcc.Store(id='inbound-data-store'),
    dcc.Store(id='merged-data-store'),

    html.Hr(style={'margin': '40px 0'}), # Horizontal rule for visual separation

    html.H2("Merged Kit Data Table", style={'textAlign': 'center', 'color': '#333', 'margin-bottom': '20px'}),
    dash_table.DataTable(
        id='data-table',
        columns=[{"name": i, "id": i} for i in []], # Initial empty columns
        data=[], # Initial empty data
        filter_action="native", # Enable in-table filtering
        sort_action="native",   # Enable in-table sorting
        style_table={'overflowX': 'auto', 'margin': '0 auto', 'width': '90%'}, # Table styling
        style_header={
            'backgroundColor': 'rgb(230, 230, 230)',
            'fontWeight': 'bold'
        },
        style_cell={
            'textAlign': 'left',
            'padding': '8px',
            'minWidth': '80px', 'width': '100px', 'maxWidth': '180px',
        },
        page_size=15, # Number of rows per page
    ),

    html.Button("Download Merged Report (CSV)", id="btn-download-csv",
                style={'margin': '30px auto', 'display': 'block', 'padding': '10px 20px'}),
    dcc.Download(id="download-dataframe-csv"), # Component to trigger file download
])

# --- Register Callbacks (for multi-page Dash apps) ---
# This function is called by the main app.py to register all interactive callbacks
# specific to this page with the main Dash application instance.
def register_callbacks(app):
    @app.callback(
        Output('outbound-data-store', 'data'),
        Output('inbound-data-store', 'data'),
        Output('outbound-upload-status', 'children'),
        Output('inbound-upload-status', 'children'),
        Input('upload-outbound-data', 'contents'),
        State('upload-outbound-data', 'filename'),
        Input('upload-inbound-data', 'contents'),
        State('upload-inbound-data', 'filename')
    )
    def handle_uploads(outbound_contents, outbound_filename, inbound_contents, inbound_filename):
        outbound_json = dash.no_update
        inbound_json = dash.no_update
        outbound_status = ""
        inbound_status = ""

        ctx = dash.callback_context
        # Check if any input triggered the callback
        if not ctx.triggered:
            return dash.no_update, dash.no_update, "No Outbound file uploaded yet.", "No Inbound file uploaded yet."

        # Determine which upload triggered the callback
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

        if trigger_id == 'upload-outbound-data' and outbound_contents:
            df, err = parse_contents(outbound_contents, outbound_filename)
            if err:
                outbound_status = html.Span(f"Error: {err}", style={'color': 'red'})
                outbound_json = None # Clear previous data if error
            elif df is not None:
                # Convert YearMonth to string before storing in JSON for consistency
                if 'YearMonth' in df.columns:
                    df['YearMonth'] = df['YearMonth'].dt.date.astype(str)
                outbound_json = df.to_json(orient='split') # Store DataFrame as JSON string
                outbound_status = html.Span(f"Outbound: {outbound_filename} loaded.", style={'color': 'green'})
        elif trigger_id == 'upload-inbound-data' and inbound_contents:
            df, err = parse_contents(inbound_contents, inbound_filename)
            if err:
                inbound_status = html.Span(f"Error: {err}", style={'color': 'red'})
                inbound_json = None # Clear previous data if error
            elif df is not None:
                # Convert YearMonth to string before storing
                if 'YearMonth' in df.columns:
                    df['YearMonth'] = df['YearMonth'].dt.date.astype(str)
                inbound_json = df.to_json(orient='split')
                inbound_status = html.Span(f"Inbound: {inbound_filename} loaded.", style={'color': 'green'})

        return outbound_json, inbound_json, outbound_status, inbound_status


    @app.callback(
        Output('merged-data-store', 'data'),
        Output('merge-status', 'children'),
        Input('outbound-data-store', 'data'),
        Input('inbound-data-store', 'data')
    )
    def merge_data(outbound_json, inbound_json):
        # Only attempt merge if both data stores contain data
        if outbound_json is None or inbound_json is None:
            return None, "Upload both files to see merged data."

        try:
            # Read JSON data back into Pandas DataFrames
            df_outbound_tubes = pd.read_json(outbound_json, orient='split')
            df_inbound_agg = pd.read_json(inbound_json, orient='split')

            # Convert 'YearMonth' columns back to datetime objects for merging
            for df_temp in [df_outbound_tubes, df_inbound_agg]:
                if 'YearMonth' in df_temp.columns:
                    df_temp['YearMonth'] = pd.to_datetime(df_temp['YearMonth'])

            # Perform the outer merge to include all locations/tube types present in either file
            merged_df = pd.merge(
                df_outbound_tubes,
                df_inbound_agg,
                on=['Location', 'YearMonth', 'TubeType'],
                how='outer'
            ).fillna(0) # Fill NaN values (from outer merge) with 0

            # Calculate 'RemainingTubes'
            merged_df['RemainingTubes'] = merged_df['TubesSent'] - merged_df['TubesReturned']
            merged_df = merged_df.sort_values(by=['YearMonth', 'Location', 'TubeType']).reset_index(drop=True)
            # Create a display-friendly YearMonth column
            merged_df['YearMonth_Display'] = merged_df['YearMonth'].dt.strftime('%Y-%m')

            # Store the merged DataFrame as JSON for other callbacks to access
            return merged_df.to_json(date_format='iso', orient='split'), "Data merged and processed successfully!"

        except Exception as e:
            import traceback
            traceback.print_exc() # Print full traceback to console
            print(f"Error during merge: {e}")
            return None, html.Span(f"An error occurred during merge: {e}", style={'color': 'red'})

    @app.callback(
        Output('data-table', 'columns'),
        Output('data-table', 'data'),
        Input('merged-data-store', 'data')
    )
    def update_table(jsonified_data):
        if jsonified_data:
            df = pd.read_json(jsonified_data, orient='split')
            # Define desired column order for display
            display_cols_order = ['Location', 'YearMonth_Display', 'TubeType', 'TubesSent', 'TubesReturned', 'RemainingTubes']
            # Get actual columns that exist and reorder them
            final_display_columns = [col for col in display_cols_order if col in df.columns] + \
                                   [col for col in df.columns if col not in display_cols_order and col not in ['YearMonth']] # Add any other columns that exist but aren't in desired order

            columns = [{"name": col, "id": col} for col in final_display_columns]
            data = df.to_dict('records') # Convert DataFrame to list of dictionaries for DataTable
            return columns, data
        return [], [] # Return empty if no data

    @app.callback(
        Output("download-dataframe-csv", "data"),
        Input("btn-download-csv", "n_clicks"),
        State('merged-data-store', 'data'),
        prevent_initial_call=True, # Prevents callback from firing on initial load
    )
    def download_csv(n_clicks, jsonified_data):
        if n_clicks and jsonified_data: # Only trigger if button clicked and data exists
            df = pd.read_json(jsonified_data, orient='split')
            # Ensure YearMonth is in YYYY-MM format for the downloaded CSV
            if 'YearMonth' in df.columns and pd.api.types.is_string_dtype(df['YearMonth']):
                df['YearMonth'] = pd.to_datetime(df['YearMonth'], errors='coerce')
            if 'YearMonth' in df.columns and pd.api.types.is_datetime64_any_dtype(df['YearMonth']):
                df['YearMonth'] = df['YearMonth'].dt.strftime('%Y-%m')
            # Remove the 'YearMonth_Display' column if it exists, as 'YearMonth' is now formatted for CSV
            if 'YearMonth_Display' in df.columns:
                df = df.drop(columns=['YearMonth_Display'])
            # Send the DataFrame as a CSV file
            return dcc.send_data_frame(df.to_csv, filename="SpectraCell_Merged_Monthly_Report.csv", index=False)
        return None # No download if conditions not met