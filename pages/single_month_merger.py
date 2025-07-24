import dash
from dash.dependencies import Input, Output, State
from dash import dcc, html, dash_table
import pandas as pd
import base64
import io
import datetime
import re

# --- Kit to tube mapping ---
# This dictionary defines how many tubes of each type are associated with a specific kit name.
# IMPORTANT: These kit names must exactly match the column headers in your 'out_*.csv' files.
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
# This function is designed to be robust, handle different file formats (outbound/inbound),
# and provide specific error messages for easier debugging.
def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    df = None
    error_message = None

    try:
        # Determine if the file is an outbound or inbound report based on its filename prefix.
        is_outbound = "out_" in filename
        is_inbound = "in_" in filename

        if is_outbound and filename.endswith(".csv"):
            # --- Outbound File Processing Logic (handles multi-month format) ---
            # Read the CSV without a header initially to capture both header rows.
            df_raw = pd.read_csv(io.StringIO(decoded.decode('utf-8')), header=None, on_bad_lines='skip', engine='python')

            # Add checks for minimum rows to ensure valid header structure.
            if df_raw.empty:
                error_message = "Outbound file is empty or contains no data rows."
                return None, error_message
            if len(df_raw) < 2:
                error_message = "Outbound file has too few rows. Expected at least 2 header rows and data."
                return None, error_message

            # Extract the first two rows as potential headers.
            # Use .squeeze() to ensure they are Series, not single-column DataFrames.
            header_row1 = df_raw.iloc[0].squeeze()
            header_row2 = df_raw.iloc[1].squeeze()

            # Identify fixed ID columns (the first 4 columns).
            fixed_id_cols_names = ['Host Code', 'Organization Name', 'Territory Name', 'Sales Rep Full Name']
            
            # Create the new multi-level columns based on the two header rows.
            new_columns = []
            for i in range(len(header_row2)):
                col_name_r2 = str(header_row2[i]).strip()
                col_name_r1 = str(header_row1[i]).strip()

                if i < len(fixed_id_cols_names):
                    # These are the fixed ID columns; they don't have a month associated.
                    new_columns.append(fixed_id_cols_names[i])
                else:
                    # These are the kit/tube columns, which have a month associated.
                    # The month number is typically in header_row1 (e.g., '1.00', '2.00').
                    try:
                        month_num = int(float(col_name_r1)) # Convert '1.00' to 1.
                        new_columns.append(f"{col_name_r2}_Month_{month_num}")
                    except ValueError:
                        # If it's not a month number, it might be a continuation of a previous kit type
                        # (e.g., 'MNT Kit Only (2 ACD).1'). Fallback to a generic name.
                        new_columns.append(f"{col_name_r2}_Month_Unknown_{i}") # Added {i} to ensure uniqueness.

            # Set the new columns to the DataFrame and drop the original header rows.
            df_raw.columns = new_columns
            df = df_raw.iloc[2:].reset_index(drop=True) # Data starts from the 3rd row (index 2).

            # --- CRITICAL FIX: Explicitly rename core columns for outbound file ---
            # These are the columns expected to be used as 'fixed_id_cols'.
            expected_outbound_columns_mapping = {
                'Host Code': 'Order_ID',
                'Organization Name': 'Location',
                'Territory Name': 'Location_Code',
                'Sales Rep Full Name': 'SalesRep'
            }

            # Only rename columns that exist in the DataFrame.
            columns_to_rename = {k: v for k, v in expected_outbound_columns_mapping.items() if k in df.columns}
            df = df.rename(columns=columns_to_rename)

            # Ensure the expected fixed ID columns are now present after renaming.
            required_outbound_cols = ['Order_ID', 'Location', 'Location_Code', 'SalesRep']
            for col in required_outbound_cols:
                if col not in df.columns:
                    error_message = f"Missing required column '{col}' after renaming in Outbound file. Please check your CSV header structure."
                    return None, error_message

            # Now, melt the DataFrame based on the new multi-month structure.
            # Identify columns that contain month information (e.g., "_Month_1", "_Month_2") using a regex pattern.
            month_columns = [col for col in df.columns if re.search(r'_Month_\d+', col)]

            if not month_columns:
                error_message = "No month-specific kit columns found. Please ensure your outbound file has month numbers in the first header row and kit names in the second."
                return None, error_message

            # Melt the DataFrame to transform month-specific kit columns into rows.
            # The id_vars are the fixed ID columns, plus any other non-month specific columns.
            id_vars_for_melt = [col for col in df.columns if col not in month_columns]

            df_melted_multi_month = df.melt(
                id_vars=id_vars_for_melt,
                var_name='KitMonthColumn', # e.g., "MNT Kit Only (2 ACD)_Month_1"
                value_name='KitCount'
            )

            # Extract KitDescription and Month from 'KitMonthColumn'.
            df_melted_multi_month['KitDescription'] = df_melted_multi_month['KitMonthColumn'].apply(lambda x: x.split('_Month_')[0].strip())
            
            # Extract month number as string first.
            df_melted_multi_month['MonthNumStr'] = df_melted_multi_month['KitMonthColumn'].apply(lambda x: x.split('_Month_')[-1].strip())
            
            # Construct YearMonth string and then convert to datetime.
            # Assumes the current year for the month data.
            current_year = datetime.datetime.now().year
            df_melted_multi_month['YearMonth'] = pd.to_datetime(
                df_melted_multi_month.apply(lambda row: f"{current_year}-{row['MonthNumStr']}-01", axis=1),
                errors='coerce' # Coerce errors to NaT (Not a Time).
            )
            df_melted_multi_month = df_melted_multi_month.drop(columns=['MonthNumStr']) # Drop temp column.
            df_melted_multi_month = df_melted_multi_month.dropna(subset=['YearMonth']) # Drop rows where YearMonth couldn't be parsed.

            # Convert KitCount to numeric, handling non-numeric entries and filling NaN with 0.
            df_melted_multi_month['KitCount'] = pd.to_numeric(df_melted_multi_month['KitCount'], errors='coerce').fillna(0)
            df_melted_multi_month = df_melted_multi_month[df_melted_multi_month['KitCount'] > 0] # Filter out zero or NaN counts.

            # Initialize tube type columns for calculation.
            for tube_type in ['ACD', 'Blue', 'Lav', 'SST']: # Define all possible tube types.
                df_melted_multi_month[tube_type] = 0

            # Distribute tubes based on kit_to_tube mapping.
            for index, row in df_melted_multi_month.iterrows():
                kit_desc = str(row['KitDescription']) # Ensure it's a string for dictionary lookup.
                kit_count = row['KitCount']
                if kit_desc in kit_to_tube:
                    for tube_type_in_kit, qty_per_kit in kit_to_tube[kit_desc].items():
                        # Add calculated tubes to the corresponding tube type column.
                        df_melted_multi_month.at[index, tube_type_in_kit] += kit_count * qty_per_kit

            # Melt again to aggregate the tube counts by tube type.
            # Ensure that 'KitMonthColumn', 'KitDescription', and 'KitCount' are dropped before the final melt.
            cols_to_keep_before_final_melt = [col for col in df_melted_multi_month.columns if col not in ['ACD', 'Blue', 'Lav', 'SST', 'KitDescription', 'KitCount', 'KitMonthColumn']]

            df_outbound_tubes = df_melted_multi_month.melt(
                id_vars=cols_to_keep_before_final_melt,
                value_vars=['ACD', 'Blue', 'Lav', 'SST'],
                var_name='TubeType',
                value_name='TubesSent' # Renamed for clarity.
            )
            df_outbound_tubes = df_outbound_tubes[df_outbound_tubes['TubesSent'] > 0] # Keep only tubes that were sent.
            
            # Final aggregation for outbound data: sum TubesSent by Location, YearMonth, TubeType.
            df_outbound_tubes = df_outbound_tubes.groupby(['Location', 'YearMonth', 'TubeType']).agg(TubesSent=('TubesSent', 'sum')).reset_index()

            return df_outbound_tubes, None

        elif is_inbound and filename.endswith(".csv"):
            # Inbound file processing.
            # Assuming header is the first row and data starts from the second row.
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')), header=None)
            df.columns = df.iloc[0] # Set the first row as column headers.
            df = df[1:] # Remove the first row (now the header).
            df.columns = df.columns.str.strip() # Clean column names.

            df = df.rename(columns={
                'color': 'TubeType', # Standardize 'color' column to 'TubeType'.
                'Num': 'Count'       # Standardize 'Num' column to 'Count'.
            })
            df['Count'] = pd.to_numeric(df['Count'], errors='coerce').fillna(0) # Ensure count is numeric.

            # Check for essential 'YearMonth' column.
            if 'YearMonth' not in df.columns:
                error_message = "Missing 'YearMonth' column in Incoming file. Please check its header."
                return None, error_message

            # Convert 'YearMonth' to datetime, handling errors (e.g., if format is %Y%m).
            # Assuming 'YearMonth' in inbound is like '202501', '202502'.
            df['YearMonth'] = pd.to_datetime(df['YearMonth'], format='%Y%m', errors='coerce')
            df = df.dropna(subset=['YearMonth']) # Remove rows where YearMonth couldn't be parsed.

            # Aggregate incoming samples by Location, YearMonth, and TubeType.
            df_inbound_agg = df.groupby(['Location', 'YearMonth', 'TubeType']).agg(SamplesReturned=('Count', 'sum')).reset_index()

            return df_inbound_agg, None

        else:
            return None, "Unsupported file name. Please upload 'out_MONTH.csv' (old format), 'out_MULTI_MONTH.csv' (new format) or 'in_MONTH.csv'."

    except Exception as e:
        import traceback
        traceback.print_exc() # Print full traceback to console for detailed debugging.
        print(f"Error parsing file {filename}: {e}")
        return None, f"Error processing {filename}. Please check file format and column names: {e}"

# --- Define the layout for this page ---
# This 'layout' variable will be imported by app.py to display this page.
layout = html.Div([
    html.H2("Monthly Kit Data Merger", style={'textAlign': 'center', 'color': '#333', 'margin-bottom': '30px'}),
    html.P(
        "This tool merges data from two types of reports: an outbound file from HC1 "
        "('Kit&Tube Trend by Location & Month.csv') and an inbound file from the SQL server "
        "('Count of Incoming Samples by Location.csv').",
        style={'textAlign': 'center', 'color': '#555', 'margin-bottom': '20px'}
    ),
    html.P(
    "For proper processing, please ensure your files are renamed as follows: "
    "Outbound files should start with 'out_' (e.g., `out_2025.csv`), "
    "and inbound files should start with 'in_' (e.g., `in_2025.csv`). "
    "The part after the underscore typically represents the month or year.",
    style={'textAlign': 'center', 'color': '#555', 'margin-bottom': '20px'}),

    html.Div([
        html.Div([
            html.H3("Upload Outbound Kits Report", style={'color': '#555', 'font-size': '1.1em'}),
            html.P("(e.g., out_jan.csv or multi-month format)", style={'font-size': '0.9em', 'color': '#777'}),
            dcc.Upload(
                id='upload-outbound-data',
                children=html.Div([
                    'Drag and Drop or ',
                    html.A('Select File', style={'color': '#007bff', 'text-decoration': 'none', 'font-weight': 'bold'})
                ]),
                style={
                    'width': '100%', 'height': '80px', 'lineHeight': '80px', # Increased height
                    'borderWidth': '2px', 'borderStyle': 'dashed', 'borderRadius': '10px', # Thicker, more rounded border
                    'textAlign': 'center', 'margin': '15px 0', 'cursor': 'pointer',
                    'backgroundColor': '#f9f9f9', 'transition': 'background-color 0.3s ease'
                },
                multiple=False, # Only allow one file at a time.
                accept='.csv'    # Only accept CSV files.
            ),
            html.Div(id='outbound-upload-status', style={'color': 'green', 'textAlign': 'center', 'margin-top': '10px', 'font-weight': 'bold'}),
        ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top', 'marginRight': '2%', 'padding': '15px', 'border': '1px solid #ddd', 'borderRadius': '8px', 'boxShadow': '0 2px 5px rgba(0,0,0,0.05)'}),

        html.Div([
            html.H3("Upload Inbound Samples Report", style={'color': '#555', 'font-size': '1.1em'}),
            html.P("(e.g., in_jan.csv)", style={'font-size': '0.9em', 'color': '#777'}),
            dcc.Upload(
                id='upload-inbound-data',
                children=html.Div([
                    'Drag and Drop or ',
                    html.A('Select File', style={'color': '#007bff', 'text-decoration': 'none', 'font-weight': 'bold'})
                ]),
                style={
                    'width': '100%', 'height': '80px', 'lineHeight': '80px', # Increased height
                    'borderWidth': '2px', 'borderStyle': 'dashed', 'borderRadius': '10px', # Thicker, more rounded border
                    'textAlign': 'center', 'margin': '15px 0', 'cursor': 'pointer',
                    'backgroundColor': '#f9f9f9', 'transition': 'background-color 0.3s ease'
                },
                multiple=False,
                accept='.csv'
            ),
            html.Div(id='inbound-upload-status', style={'color': 'green', 'textAlign': 'center', 'margin-top': '10px', 'font-weight': 'bold'}),
        ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top', 'marginLeft': '2%', 'padding': '15px', 'border': '1px solid #ddd', 'borderRadius': '8px', 'boxShadow': '0 2px 5px rgba(0,0,0,0.05)'}),
    ], style={'display': 'flex', 'justifyContent': 'center', 'margin-bottom': '40px', 'gap': '20px'}), # Added gap for spacing

    html.Div(id='merge-status', style={'textAlign': 'center', 'margin-bottom': '30px', 'font-weight': 'bold', 'font-size': '1.1em', 'color': '#007bff'}),

    # dcc.Store components are used to temporarily store data in the browser's memory.
    # This prevents re-processing files unnecessarily and allows data to be shared between callbacks.
    dcc.Store(id='outbound-data-store'),
    dcc.Store(id='inbound-data-store'),
    dcc.Store(id='merged-data-store'),

    html.Hr(style={'margin': '50px 0', 'borderTop': '1px solid #eee'}), # Horizontal rule for visual separation

    html.H2("Merged Kit Data Table", style={'textAlign': 'center', 'color': '#333', 'margin-bottom': '25px'}),
    dash_table.DataTable(
        id='data-table',
        columns=[{"name": i, "id": i} for i in []], # Initial empty columns.
        data=[], # Initial empty data.
        filter_action="native", # Enable in-table filtering.
        sort_action="native",    # Enable in-table sorting.
        style_table={'overflowX': 'auto', 'margin': '0 auto', 'width': '90%', 'boxShadow': '0 4px 8px rgba(0,0,0,0.1)', 'borderRadius': '8px'}, # Table styling.
        style_header={
            'backgroundColor': '#e9ecef', # Lighter gray for header.
            'fontWeight': 'bold',
            'textAlign': 'center',
            'borderBottom': '2px solid #dee2e6',
            'padding': '12px'
        },
        style_cell={
            'textAlign': 'left',
            'padding': '10px',
            'minWidth': '90px', 'width': '120px', 'maxWidth': '200px', # Adjusted cell width.
            'borderBottom': '1px solid #f2f2f2' # Lighter cell border.
        },
        style_data_conditional=[
            {
                'if': {'row_index': 'odd'},
                'backgroundColor': 'rgb(250, 250, 250)' # Zebra striping for rows.
            }
        ],
        page_size=15, # Number of rows per page.
    ),
    html.P(
        "Disclaimer: The inbound dataset only includes samples returned in the form of their tube types, "
        "so it's not possible to display the total number of kits sent out at the moment. Sorry about that! :c",
        style={'textAlign': 'center', 'color': '#777', 'margin-top': '25px', 'font-style': 'italic'}
    ),
    html.Button("Download Merged Report (CSV)", id="btn-download-csv",
                style={
                    'margin': '40px auto', 'display': 'block', 'padding': '12px 25px',
                    'backgroundColor': '#28a745', 'color': 'white', 'border': 'none',
                    'borderRadius': '5px', 'cursor': 'pointer', 'fontSize': '1.1em',
                    'fontWeight': 'bold', 'boxShadow': '0 2px 5px rgba(0,0,0,0.2)',
                    'transition': 'background-color 0.3s ease'
                }),
    dcc.Download(id="download-dataframe-csv"), # Component to trigger file download.
    
    html.Hr(style={'margin': '50px 0', 'borderTop': '1px solid #eee'}), # Separator for alerts section.

    html.H2("Unused Tube Sample Alerts", style={'textAlign': 'center', 'color': '#dc3545', 'margin-bottom': '25px'}), # Changed to a more standard red.
    html.Div([
        html.Label("Set Unused Tube Sample Alert Threshold:", style={'marginRight': '15px', 'fontWeight': 'bold', 'font-size': '1.05em'}),
        dcc.Input(
            id='alert-threshold-input',
            type='number',
            value=50, # Default threshold.
            min=0,
            step=1,
            style={'width': '120px', 'padding': '8px', 'border': '1px solid #ced4da', 'borderRadius': '5px', 'fontSize': '1em'}
        )
    ], style={'textAlign': 'center', 'margin-bottom': '30px', 'display': 'flex', 'justifyContent': 'center', 'alignItems': 'center'}),

    html.Div(id='unused-kit-alerts', style={'margin': '0 auto', 'width': '90%', 'padding': '20px', 'border': '1px solid #ffc107', 'borderRadius': '8px', 'backgroundColor': '#fff3cd', 'boxShadow': '0 2px 5px rgba(0,0,0,0.05)'}), # Enhanced alert box styling.
], style={'fontFamily': 'Inter, sans-serif', 'padding': '20px', 'backgroundColor': '#f8f9fa'}) # Overall page styling.

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
        # Check if any input triggered the callback.
        if not ctx.triggered:
            return dash.no_update, dash.no_update, "No Outbound file uploaded yet.", "No Inbound file uploaded yet."

        # Determine which upload triggered the callback.
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

        if trigger_id == 'upload-outbound-data' and outbound_contents:
            df, err = parse_contents(outbound_contents, outbound_filename)
            if err:
                outbound_status = html.Span(f"Error: {err}", style={'color': 'red'})
                outbound_json = None # Clear previous data if error.
            elif df is not None:
                # Convert YearMonth to string before storing in JSON for consistency.
                if 'YearMonth' in df.columns:
                    df['YearMonth'] = df['YearMonth'].dt.date.astype(str)
                outbound_json = df.to_json(orient='split') # Store DataFrame as JSON string.
                outbound_status = html.Span(f"Outbound: {outbound_filename} loaded.", style={'color': 'green'})
        elif trigger_id == 'upload-inbound-data' and inbound_contents:
            df, err = parse_contents(inbound_contents, inbound_filename)
            if err:
                inbound_status = html.Span(f"Error: {err}", style={'color': 'red'})
                inbound_json = None # Clear previous data if error.
            elif df is not None:
                # Convert YearMonth to string before storing.
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
        # Only attempt merge if both data stores contain data.
        if outbound_json is None or inbound_json is None:
            return None, html.Span("Upload both files to see merged data.", style={'color': '#6c757d'})

        try:
            # Read JSON data back into Pandas DataFrames.
            df_outbound_tubes = pd.read_json(outbound_json, orient='split')
            df_inbound_agg = pd.read_json(inbound_json, orient='split')

            # Convert 'YearMonth' columns back to datetime objects for merging.
            for df_temp in [df_outbound_tubes, df_inbound_agg]:
                if 'YearMonth' in df_temp.columns:
                    df_temp['YearMonth'] = pd.to_datetime(df_temp['YearMonth'])

            # Perform the outer merge to include all locations/tube types present in either file.
            merged_df = pd.merge(
                df_outbound_tubes,
                df_inbound_agg,
                on=['Location', 'YearMonth', 'TubeType'],
                how='outer'
            ).fillna(0) # Fill NaN values (from outer merge) with 0.

            # Calculate 'RemainingKits' (now 'RemainingTubes').
            merged_df['RemainingKits'] = merged_df['TubesSent'] - merged_df['SamplesReturned']
            merged_df = merged_df.sort_values(by=['YearMonth', 'Location', 'TubeType']).reset_index(drop=True)
            # Create a display-friendly YearMonth column.
            merged_df['YearMonth_Display'] = merged_df['YearMonth'].dt.strftime('%Y-%m')

            # Store the merged DataFrame as JSON for other callbacks to access.
            return merged_df.to_json(date_format='iso', orient='split'), html.Span("Data merged and processed successfully!", style={'color': '#28a745'})

        except Exception as e:
            import traceback
            traceback.print_exc() # Print full traceback to console.
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

            # Define a mapping for display names for the DataTable headers.
            column_display_names = {
                'Location': 'Location',
                'YearMonth_Display': 'Month',
                'TubeType': 'Tube Type',
                'TubesSent': 'Tubes Sent',
                'SamplesReturned': 'Samples Returned',
                'RemainingKits': 'Remaining Tubes' # This is the key change for display.
            }

            # Define desired column order for display (using internal DataFrame column IDs).
            internal_cols_order = ['Location', 'YearMonth_Display', 'TubeType', 'TubesSent', 'SamplesReturned', 'RemainingKits']

            # Get actual columns that exist in the DataFrame and reorder them.
            # This ensures we only try to display columns that are actually in the DataFrame.
            final_display_columns_ids = [col_id for col_id in internal_cols_order if col_id in df.columns] + \
                                        [col_id for col_id in df.columns if col_id not in internal_cols_order and col_id not in ['YearMonth']]

            # Create the columns list for DataTable, using the display names mapping.
            columns = [
                {"name": column_display_names.get(col_id, col_id), "id": col_id}
                for col_id in final_display_columns_ids
            ]
            data = df.to_dict('records') # Convert DataFrame to list of dictionaries for DataTable.
            return columns, data
        return [], [] # Return empty if no data.

    @app.callback(
        Output("download-dataframe-csv", "data"),
        Input("btn-download-csv", "n_clicks"),
        State('merged-data-store', 'data'),
        prevent_initial_call=True, # Prevents callback from firing on initial load.
    )
    def download_csv(n_clicks, jsonified_data):
        if n_clicks and jsonified_data: # Only trigger if button clicked and data exists.
            df = pd.read_json(jsonified_data, orient='split')
            # Ensure YearMonth is in YYYY-MM format for the downloaded CSV.
            if 'YearMonth' in df.columns and pd.api.types.is_string_dtype(df['YearMonth']):
                df['YearMonth'] = pd.to_datetime(df['YearMonth'], errors='coerce')
            if 'YearMonth' in df.columns and pd.api.types.is_datetime64_any_dtype(df['YearMonth']):
                df['YearMonth'] = df['YearMonth'].dt.strftime('%Y-%m')
            # Remove the 'YearMonth_Display' column if it exists, as 'YearMonth' is now formatted for CSV.
            if 'YearMonth_Display' in df.columns:
                df = df.drop(columns=['YearMonth_Display'])
            # Send the DataFrame as a CSV file.
            return dcc.send_data_frame(df.to_csv, filename="SpectraCell_Merged_Monthly_Report.csv", index=False)
        return None # No download if conditions not met.

    # --- New Callback for Unused Kit Alerts ---
    @app.callback(
        Output('unused-kit-alerts', 'children'),
        Input('merged-data-store', 'data'),
        Input('alert-threshold-input', 'value')
    )
    def generate_alerts(jsonified_data, threshold):
        if not jsonified_data:
            return html.P("Upload data to see unused tube sample alerts.", style={'color': '#6c757d', 'font-style': 'italic'})

        if threshold is None or threshold < 0:
            return html.P("Please enter a valid positive threshold for alerts.", style={'color': '#dc3545', 'font-weight': 'bold'})

        df = pd.read_json(jsonified_data, orient='split')

        # Filter for rows where RemainingKits exceed the threshold.
        # Group by Location and sum RemainingKits to get total unused kits per client.
        # Then filter this aggregated data.
        alerts_df = df[df['RemainingKits'] > threshold].groupby(['Location', 'YearMonth_Display']).agg(
            TotalUnusedKits=('RemainingKits', 'sum')
        ).reset_index()

        # Sort for better readability.
        alerts_df = alerts_df.sort_values(by=['TotalUnusedKits'], ascending=False)

        if alerts_df.empty:
            return html.P(f"No clients with more than {int(threshold)} unused tube samples found.", style={'color': '#28a744', 'font-weight': 'bold'})
        else:
            alert_messages = []
            alert_messages.append(html.H4("Clients with Significant Unused Tube Samples:", style={'color': '#dc3545', 'marginBottom': '15px', 'borderBottom': '1px solid #f5c6cb', 'paddingBottom': '10px'}))
            for index, row in alerts_df.iterrows():
                message = html.P(
                    f"⚠️ {row['Location']} (Month: {row['YearMonth_Display']}): {int(row['TotalUnusedKits'])} unused tube samples.",
                    style={'color': '#721c24', 'fontWeight': 'bold', 'backgroundColor': '#f8d7da', 'padding': '10px', 'borderRadius': '5px', 'marginBottom': '8px', 'borderLeft': '5px solid #dc3545'}
                )
                alert_messages.append(message)
            return html.Div(alert_messages)

