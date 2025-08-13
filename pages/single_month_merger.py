import dash
from dash.dependencies import Input, Output, State
from dash import dcc, html, dash_table
import pandas as pd
import base64
import io
import datetime
import re
import plotly.express as px

# Kit to tube mapping
kit_to_tube = {
    'MNT & Telomere Kit (2 ACD, 1 Blue Sodium Citrate)': {'ACD': 2, 'Blue': 1},
    'MNT Kit Only (2 ACD)': {'ACD': 2},
    'MTHFR Kit (1 Blue Sodium Citrate)': {'Blue': 1},
    'Telomere Kit (1 Blue Sodium Citrate)': {'Blue': 1},
    'Tube - ACD (8.5 mL) Yellow Tops': {'ACD': 1},
    'Tube - Lt. Blue (3mL) Telo/MTHFR-Sodium Citrate': {'Blue': 1},
    'Tube - SST (7.5 mL) Tiger Top': {'SST': 1},
    # Additional mappings for common variations or typos found in data:
    'MNT & Tel. 1 Blue Sor': {'ACD': 2, 'Blue': 1},
    'MNT Kit O': {'ACD': 2},
    'Tube - ACD Tube': {'ACD': 1},
    'Tube - Lt. LTtube': {'Blue': 1},
    '-SST MNT Kit Only (2 ACD)': {'SST': 1, 'ACD': 2},
}

def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    df = None
    error_message = None

    try:
        is_outbound = "out_" in filename
        is_inbound = "in_" in filename

        if is_outbound and filename.endswith(".csv"):
            df_raw = pd.read_csv(io.StringIO(decoded.decode('utf-8')), header=None, on_bad_lines='skip', engine='python')

            if df_raw.empty:
                error_message = "Outbound file is empty or contains no data rows."
                return None, error_message
            if len(df_raw) < 2:
                error_message = "Outbound file has too few rows. Expected at least 2 header rows and data."
                return None, error_message
            
            header_row1 = df_raw.iloc[0].squeeze()
            header_row2 = df_raw.iloc[1].squeeze()

            fixed_id_cols_names = ['Host Code', 'Organization Name', 'Territory Name', 'Sales Rep Full Name']
            
            new_columns = []
            for i in range(len(header_row2)):
                col_name_r2 = str(header_row2[i]).strip()
                col_name_r1 = str(header_row1[i]).strip()

                if i < len(fixed_id_cols_names):
                    new_columns.append(fixed_id_cols_names[i])
                else:
                    try:
                        month_num = int(float(col_name_r1))
                        new_columns.append(f"{col_name_r2}_Month_{month_num}")
                    except ValueError:
                        new_columns.append(f"{col_name_r2}_Month_Unknown_{i}") 

            df_raw.columns = new_columns
            df = df_raw.iloc[2:].reset_index(drop=True)

            expected_outbound_columns_mapping = {
                'Host Code': 'Order_ID',
                'Organization Name': 'Location',
                'Territory Name': 'Outbound_Territory',
                'Sales Rep Full Name': 'SalesRep'
            }

            columns_to_rename = {k: v for k, v in expected_outbound_columns_mapping.items() if k in df.columns}
            df = df.rename(columns=columns_to_rename)

            required_outbound_cols = ['Order_ID', 'Location', 'Outbound_Territory', 'SalesRep']
            for col in required_outbound_cols:
                if col not in df.columns:
                    error_message = f"Missing required column '{col}' after renaming in Outbound file. Please check your CSV header structure."
                    return None, error_message

            month_columns = [col for col in df.columns if re.search(r'_Month_\d+', col)]

            if not month_columns:
                error_message = "No month-specific kit columns found. Please ensure your outbound file has month numbers in the first header row and kit names in the second."
                return None, error_message

            df_melted_multi_month = df.melt(
                id_vars=[col for col in df.columns if col not in month_columns],
                var_name='KitMonthColumn',
                value_name='KitCount'
            )

            df_melted_multi_month['KitDescription'] = df_melted_multi_month['KitMonthColumn'].apply(lambda x: x.split('_Month_')[0].strip())
            df_melted_multi_month['MonthNumStr'] = df_melted_multi_month['KitMonthColumn'].apply(lambda x: x.split('_Month_')[-1].strip())
            
            current_year = datetime.datetime.now().year
            df_melted_multi_month['YearMonth'] = pd.to_datetime(
                df_melted_multi_month.apply(lambda row: f"{current_year}-{row['MonthNumStr']}-01", axis=1),
                errors='coerce'
            )
            df_melted_multi_month = df_melted_multi_month.drop(columns=['MonthNumStr'])
            df_melted_multi_month = df_melted_multi_month.dropna(subset=['YearMonth'])

            df_melted_multi_month['KitCount'] = pd.to_numeric(df_melted_multi_month['KitCount'], errors='coerce').fillna(0)
            df_melted_multi_month = df_melted_multi_month[df_melted_multi_month['KitCount'] > 0]

            for tube_type in ['ACD', 'Blue', 'Lav', 'SST']:
                df_melted_multi_month[tube_type] = 0

            for index, row in df_melted_multi_month.iterrows():
                kit_desc = str(row['KitDescription'])
                kit_count = row['KitCount']
                if kit_desc in kit_to_tube:
                    for tube_type_in_kit, qty_per_kit in kit_to_tube[kit_desc].items():
                        df_melted_multi_month.at[index, tube_type_in_kit] += kit_count * qty_per_kit

            cols_to_keep_before_final_melt = [col for col in df_melted_multi_month.columns if col not in ['ACD', 'Blue', 'Lav', 'SST', 'KitDescription', 'KitCount', 'KitMonthColumn']]

            df_outbound_tubes = df_melted_multi_month.melt(
                id_vars=cols_to_keep_before_final_melt,
                value_vars=['ACD', 'Blue', 'Lav', 'SST'],
                var_name='TubeType',
                value_name='TubesSent'
            )
            df_outbound_tubes = df_outbound_tubes[df_outbound_tubes['TubesSent'] > 0]

            df_outbound_tubes = df_outbound_tubes.groupby(['Location', 'YearMonth', 'TubeType', 'Order_ID', 'Outbound_Territory']).agg(TubesSent=('TubesSent', 'sum')).reset_index()
            df_outbound_tubes['Location_ID'] = pd.NA

            return df_outbound_tubes, None

        elif is_inbound and filename.endswith(".csv"):
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')), header=None)
            df.columns = df.iloc[0]
            df = df[1:]
            
            df.columns = df.columns.str.strip()

            inbound_column_mapping = {
                'LID': 'Location_ID',
                'Territory': 'Inbound_Territory',
                'color': 'TubeType',
                'Num': 'Count'
            }
            
            df = df.rename(columns={k: v for k, v in inbound_column_mapping.items() if k in df.columns})
            df['Count'] = pd.to_numeric(df['Count'], errors='coerce').fillna(0)

            if 'YearMonth' not in df.columns:
                error_message = "Missing 'YearMonth' column in Incoming file. Please check its header."
                return None, error_message
            if 'Location_ID' not in df.columns:
                 error_message = "Missing 'Location_ID' column in Incoming file. Please check its header."
                 return None, error_message
            if 'Inbound_Territory' not in df.columns:
                 error_message = "Missing 'Inbound_Territory' column in Incoming file. Please check its header."
                 return None, error_message

            df['YearMonth'] = pd.to_datetime(df['YearMonth'], format='%Y%m', errors='coerce')
            df = df.dropna(subset=['YearMonth'])
            
            df['Location_ID'] = pd.to_numeric(df['Location_ID'], errors='coerce')

            df_inbound_agg = df.groupby(['Location_ID', 'Location', 'YearMonth', 'TubeType', 'Inbound_Territory']).agg(SamplesReturned=('Count', 'sum')).reset_index()

            return df_inbound_agg, None

        else:
            return None, "Unsupported file name. Please upload 'out_MONTH.csv' (old format), 'out_MULTI_MONTH.csv' (new format) or 'in_MONTH.csv'."

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error parsing file {filename}: {e}")
        return None, f"Error processing {filename}. Please check file format and column names: {e}"


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
                    'width': '100%', 'height': '80px', 'lineHeight': '80px', 
                    'borderWidth': '2px', 'borderStyle': 'dashed', 'borderRadius': '10px', 
                    'textAlign': 'center', 'margin': '15px 0', 'cursor': 'pointer',
                    'backgroundColor': '#f9f9f9', 'transition': 'background-color 0.3s ease'
                },
                multiple=False,
                accept='.csv'
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
                    'width': '100%', 'height': '80px', 'lineHeight': '80px',
                    'borderWidth': '2px', 'borderStyle': 'dashed', 'borderRadius': '10px',
                    'textAlign': 'center', 'margin': '15px 0', 'cursor': 'pointer',
                    'backgroundColor': '#f9f9f9', 'transition': 'background-color 0.3s ease'
                },
                multiple=False,
                accept='.csv'
            ),
            html.Div(id='inbound-upload-status', style={'color': 'green', 'textAlign': 'center', 'margin-top': '10px', 'font-weight': 'bold'}),
        ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top', 'marginLeft': '2%', 'padding': '15px', 'border': '1px solid #ddd', 'borderRadius': '8px', 'boxShadow': '0 2px 5px rgba(0,0,0,0.05)'}),
    ], style={'display': 'flex', 'justifyContent': 'center', 'margin-bottom': '40px', 'gap': '20px'}),

    html.Div(id='merge-status', style={'textAlign': 'center', 'margin-bottom': '30px', 'font-weight': 'bold', 'font-size': '1.1em', 'color': '#007bff'}),

    dcc.Store(id='outbound-data-store'),
    dcc.Store(id='inbound-data-store'),
    dcc.Store(id='merged-data-store'),
    dcc.Store(id='aggregated-data-store'),

    html.Hr(style={'margin': '50px 0', 'borderTop': '1px solid #eee'}),

    html.H2("Merged Kit Data Table", style={'textAlign': 'center', 'color': '#333', 'margin-bottom': '25px'}),
    dash_table.DataTable(
        id='data-table',
        columns=[
            {"name": "Location ID", "id": "Location_ID"},
            {"name": "Location Name", "id": "Location"},
            {"name": "Territory", "id": "Territory_Name"},
            {"name": "Month", "id": "YearMonth_Display"},
            {"name": "Tube Type", "id": "TubeType"},
            {"name": "Tubes Sent", "id": "TubesSent"},
            {"name": "Samples Returned", "id": "SamplesReturned"},
            {"name": "Stock volume (Remaining Tubes)", "id": "RemainingKits"}
        ],
        data=[],
        filter_action="native",
        sort_action="native",
        page_action="native",
        style_table={'overflowX': 'auto', 'margin': '0 auto', 'width': '90%', 'boxShadow': '0 4px 8px rgba(0,0,0,0.1)', 'borderRadius': '8px'},
        style_header={
            'backgroundColor': '#e9ecef', 
            'fontWeight': 'bold',
            'textAlign': 'center',
            'borderBottom': '2px solid #dee2e6',
            'padding': '12px'
        },
        style_cell={
            'textAlign': 'left',
            'padding': '10px',
            'minWidth': '90px', 'width': '120px', 'maxWidth': '200px',
            'borderBottom': '1px solid #f2f2f2'
        },
        style_data_conditional=[
            {
                'if': {'row_index': 'odd'},
                'backgroundColor': 'rgb(250, 250, 250)'
            }
        ],
        page_size=15,
    ),
    html.P(
        "Disclaimer: The inbound dataset only includes samples returned in the form of their tube types, "
        "so it's not possible to display the total number of kits sent out at the moment.",
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
    dcc.Download(id="download-dataframe-csv"),
    
    html.Hr(style={'margin': '50px 0', 'borderTop': '1px solid #eee'}),

    html.H2("Total Remaining Tubes Per Client (All Months - Excluding DTC)", style={'textAlign': 'center', 'color': '#333', 'margin-bottom': '25px'}),
    html.Div([
        html.Div([
            html.Label("Top N Clients for Chart:", style={'marginRight': '10px', 'fontWeight': 'bold'}),
            dcc.Input(
                id='top-n-clients-input',
                type='number',
                value=10,
                min=1,
                step=1,
                style={'width': '80px', 'padding': '5px', 'border': '1px solid #ced4da', 'borderRadius': '5px'}
            )
        ], style={'textAlign': 'center', 'marginBottom': '20px', 'display': 'flex', 'justifyContent': 'center', 'alignItems': 'center'}),
        dcc.Graph(id='total-remaining-tubes-chart', style={'margin': '0 auto', 'width': '90%', 'height': '400px', 'boxShadow': '0 2px 5px rgba(0,0,0,0.05)', 'borderRadius': '8px'}),
    ], style={'padding': '20px', 'border': '1px solid #ddd', 'borderRadius': '8px', 'backgroundColor': '#f9f9f9', 'boxShadow': '0 2px 5px rgba(0,0,0,0.05)'}),

    html.Div([
        html.H3("Summary Table (All Months - Excluding DTC)", style={'textAlign': 'center', 'color': '#555', 'margin-top': '40px', 'margin-bottom': '20px'}),
        dash_table.DataTable(
            id='aggregated-data-table',
            columns=[{"name": i, "id": i} for i in []],
            data=[],
            filter_action="native",
            sort_action="native",
            page_size=10,
            style_table={'overflowX': 'auto', 'margin': '0 auto', 'width': '90%', 'boxShadow': '0 4px 8px rgba(0,0,0,0.1)', 'borderRadius': '8px'},
            style_header={'backgroundColor': '#e9ecef', 'fontWeight': 'bold', 'textAlign': 'center', 'borderBottom': '2px solid #dee2e6', 'padding': '12px'},
            style_cell={'textAlign': 'left', 'padding': '10px', 'minWidth': '90px', 'width': '120px', 'maxWidth': '200px', 'borderBottom': '1px solid #f2f2f2'},
            style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': 'rgb(250, 250, 250)'}],
        ),
        html.Button("Download Total Remaining Tubes Report (CSV)", id="btn-download-aggregated-csv",
                style={
                    'margin': '40px auto', 'display': 'block', 'padding': '12px 25px',
                    'backgroundColor': '#28a745', 'color': 'white', 'border': 'none',
                    'borderRadius': '5px', 'cursor': 'pointer', 'fontSize': '1.1em',
                    'fontWeight': 'bold', 'boxShadow': '0 2px 5px rgba(0,0,0,0.2)',
                    'transition': 'background-color 0.3s ease'
                }),
        dcc.Download(id="download-aggregated-dataframe-csv"),
    ], style={'padding': '20px', 'marginTop': '40px', 'border': '1px solid #ddd', 'borderRadius': '8px', 'backgroundColor': '#f9f9f9', 'boxShadow': '0 2px 5px rgba(0,0,0,0.05)'}),

], style={'fontFamily': 'Inter, sans-serif', 'padding': '20px', 'backgroundColor': '#f8f9fa'})

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
        if not ctx.triggered:
            return dash.no_update, dash.no_update, "No Outbound file uploaded yet.", "No Inbound file uploaded yet."

        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

        if trigger_id == 'upload-outbound-data' and outbound_contents:
            df, err = parse_contents(outbound_contents, outbound_filename)
            if err:
                outbound_status = html.Span(f"Error: {err}", style={'color': 'red'})
                outbound_json = None
            elif df is not None:
                if 'YearMonth' in df.columns:
                    df['YearMonth'] = df['YearMonth'].dt.date.astype(str)
                outbound_json = df.to_json(orient='split')
                outbound_status = html.Span(f"Outbound: {outbound_filename} loaded.", style={'color': 'green'})
        elif trigger_id == 'upload-inbound-data' and inbound_contents:
            df, err = parse_contents(inbound_contents, inbound_filename)
            if err:
                inbound_status = html.Span(f"Error: {err}", style={'color': 'red'})
                inbound_json = None
            elif df is not None:
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
        if outbound_json is None or inbound_json is None:
            return None, html.Span("Upload both files to see merged data.", style={'color': '#6c757d'})

        try:
            df_outbound_tubes = pd.read_json(outbound_json, orient='split')
            df_inbound_agg = pd.read_json(inbound_json, orient='split')

            for df_temp in [df_outbound_tubes, df_inbound_agg]:
                if 'YearMonth' in df_temp.columns:
                    df_temp['YearMonth'] = pd.to_datetime(df_temp['YearMonth'])

            merged_df = pd.merge(
                df_outbound_tubes,
                df_inbound_agg,
                on=['Location', 'YearMonth', 'TubeType'],
                how='outer',
                suffixes=('_out', '_in')
            )

            if 'Order_ID' in merged_df.columns:
                merged_df['Location_ID'] = merged_df['Location_ID_in'].fillna(merged_df['Order_ID'])
            else:
                merged_df['Location_ID'] = merged_df['Location_ID_in']
            
            merged_df['Territory_Name'] = merged_df['Inbound_Territory'].combine_first(merged_df['Outbound_Territory'])
            
            cols_to_fill_zero = ['TubesSent', 'SamplesReturned']
            for col in cols_to_fill_zero:
                if col in merged_df.columns:
                    merged_df[col] = merged_df[col].fillna(0)

            merged_df['RemainingKits'] = merged_df['TubesSent'] - merged_df['SamplesReturned']
            
            columns_to_drop = [
                'Location_ID_out', 'Location_ID_in', 'Outbound_Territory', 'Inbound_Territory', 'Order_ID'
            ]
            merged_df = merged_df.drop(columns=[
                col for col in columns_to_drop
                if col in merged_df.columns
            ])

            merged_df = merged_df.sort_values(by=['YearMonth', 'Location', 'TubeType']).reset_index(drop=True)
            merged_df['YearMonth_Display'] = merged_df['YearMonth'].dt.strftime('%Y-%m')

            final_cols = ['Location_ID', 'Location', 'Territory_Name', 'YearMonth', 'YearMonth_Display', 'TubeType', 'TubesSent', 'SamplesReturned', 'RemainingKits']
            merged_df = merged_df[[col for col in final_cols if col in merged_df.columns]]

            return merged_df.to_json(date_format='iso', orient='split'), html.Span("Data merged and processed successfully!", style={'color': '#28a745'})

        except Exception as e:
            import traceback
            traceback.print_exc()
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

            column_definitions = [
                {"name": "Location ID", "id": "Location_ID"},
                {"name": "Location Name", "id": "Location"},
                {"name": "Territory", "id": "Territory_Name"},
                {"name": "Month", "id": "YearMonth_Display"},
                {"name": "Tube Type", "id": "TubeType"},
                {"name": "Tubes Sent", "id": "TubesSent"},
                {"name": "Samples Returned", "id": "SamplesReturned"},
                {"name": "Stock volume (Remaining Tubes)", "id": "RemainingKits"}
            ]

            actual_columns = [col_def for col_def in column_definitions if col_def['id'] in df.columns]

            data = df.to_dict('records')
            return actual_columns, data
        return [], []

    @app.callback(
        Output("download-dataframe-csv", "data"),
        Input("btn-download-csv", "n_clicks"),
        State('data-table', 'derived_virtual_data'),
        prevent_initial_call=True, 
    )
    def download_csv(n_clicks, derived_virtual_data): 
        if n_clicks and derived_virtual_data:
            df = pd.DataFrame.from_records(derived_virtual_data)
            
            if 'YearMonth' in df.columns and pd.api.types.is_string_dtype(df['YearMonth']):
                df['YearMonth'] = pd.to_datetime(df['YearMonth'], errors='coerce')
            if 'YearMonth' in df.columns and pd.api.types.is_datetime64_any_dtype(df['YearMonth']):
                df['YearMonth'] = df['YearMonth'].dt.strftime('%Y-%m')
            if 'YearMonth_Display' in df.columns:
                df = df.drop(columns=['YearMonth_Display'])
            return dcc.send_data_frame(df.to_csv, filename="SpectraCell_Merged_Monthly_Report_Filtered.csv", index=False)
        return None 

    @app.callback(
        Output('aggregated-data-store', 'data'),
        Input('merged-data-store', 'data')
    )
    def calculate_aggregated_data(merged_json):
        if merged_json:
            df = pd.read_json(merged_json, orient='split')
            
            # Filter out DTC entries before aggregation
            if 'Location' in df.columns and 'Territory_Name' in df.columns:
                non_dtc_df = df[
                    ~df['Location'].astype(str).str.contains('DTC', case=False, na=False) &
                    ~df['Territory_Name'].astype(str).str.contains('DTC', case=False, na=False)
                ].copy()
            elif 'Location' in df.columns:
                 non_dtc_df = df[~df['Location'].astype(str).str.contains('DTC', case=False, na=False)].copy()
            elif 'Territory_Name' in df.columns:
                 non_dtc_df = df[~df['Territory_Name'].astype(str).str.contains('DTC', case=False, na=False)].copy()
            else:
                non_dtc_df = df.copy()

            groupby_cols = [col for col in ['Location_ID', 'Location', 'Territory_Name'] if col in non_dtc_df.columns]
            
            if not groupby_cols:
                return None

            aggregated_df = non_dtc_df.groupby(groupby_cols).agg(
                TotalRemainingTubes=('RemainingKits', 'sum')
            ).reset_index()
            
            aggregated_df = aggregated_df.sort_values(by='TotalRemainingTubes', ascending=False)
            
            return aggregated_df.to_json(orient='split')
        return None

    @app.callback(
        Output('total-remaining-tubes-chart', 'figure'),
        Input('aggregated-data-store', 'data'),
        Input('top-n-clients-input', 'value')
    )
    def update_total_remaining_chart(aggregated_json, top_n):
        if aggregated_json:
            aggregated_df = pd.read_json(aggregated_json, orient='split')
            
            if top_n is None or top_n <= 0:
                top_n = 10

            df_to_plot = aggregated_df.head(top_n)

            if df_to_plot.empty:
                return {}

            fig = px.bar(
                df_to_plot,
                x='Location',
                y='TotalRemainingTubes',
                title=f'Top {top_n} Clients by Total Stock Volume (Excluding DTC)',
                labels={'Location': 'Client/Location', 'TotalRemainingTubes': 'Total Stock Volume (Remaining Tubes)'},
                hover_data=['Location_ID', 'Territory_Name', 'TotalRemainingTubes']
            )
            fig.update_layout(
                xaxis={'categoryorder': 'total descending'},
                margin={'l': 40, 'b': 40, 't': 50, 'r': 0},
                plot_bgcolor='#f9f9f9',
                paper_bgcolor='#f9f9f9',
                font=dict(family="Inter, sans-serif", size=12, color="#333"),
                title_font_size=16
            )
            return fig
        return {}

    @app.callback(
        Output('aggregated-data-table', 'columns'),
        Output('aggregated-data-table', 'data'),
        Input('aggregated-data-store', 'data')
    )
    def update_aggregated_table(aggregated_json):
        if aggregated_json:
            aggregated_df = pd.read_json(aggregated_json, orient='split')

            columns_agg_def = [
                {"name": "Location ID", "id": "Location_ID"},
                {"name": "Location Name", "id": "Location"},
                {"name": "Territory", "id": "Territory_Name"},
                {"name": "Total Stock Volume (All Months)", "id": "TotalRemainingTubes"},
            ]
            
            actual_columns_agg = [col_def for col_def in columns_agg_def if col_def['id'] in aggregated_df.columns]
            data_agg = aggregated_df.to_dict('records')
            return actual_columns_agg, data_agg
        return [], []

    @app.callback(
        Output("download-aggregated-dataframe-csv", "data"),
        Input("btn-download-aggregated-csv", "n_clicks"),
        State('aggregated-data-table', 'derived_virtual_data'),
        prevent_initial_call=True,
    )
    def download_aggregated_csv(n_clicks, derived_virtual_data_agg):
        if n_clicks and derived_virtual_data_agg:
            df_agg = pd.DataFrame.from_records(derived_virtual_data_agg)
            return dcc.send_data_frame(df_agg.to_csv, filename="SpectraCell_Total_Remaining_Tubes_Report_Filtered.csv", index=False)
        return None
