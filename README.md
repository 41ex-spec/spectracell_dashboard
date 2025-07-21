# SpectraCell Dashboard

A multi-page interactive web dashboard built with Dash (Plotly/Dash) for analyzing SpectraCell monthly kit data. This application provides insights into monthly trends of kits sent vs. samples returned and allows for the on-demand merging and analysis of single-month inbound and outbound reports.

## Table of Contents

* [Features](#features)
* [Local Setup](#local-setup)
    * [Prerequisites](#prerequisites)
    * [Installation](#installation)
    * [Running Locally](#running-locally)
* [License](#license)
* [Contact](#contact)

## Features

* **Monthly Trends Overview:** Visualize historical data of kits sent versus samples returned by tube type across multiple months (Jan-July 2025 data included).
* **Interactive Bar Chart:** Explore tube data with Plotly's interactive bar charts, showing breakdowns by month and tube type.
* **Single Month Data Merger:** Upload two CSV files (one outbound kit report, one inbound sample report) for a specific month.
* **Dynamic Data Processing:** Automatically processes uploaded files, calculates remaining kits, and displays a merged, filterable, and sortable table.
* **CSV Download:** Download the merged monthly report directly from the dashboard.
* **Multi-page Application:** Seamless navigation between different analysis views.

## Local Setup

Follow these steps to get the dashboard up and running on your local machine.

### Prerequisites

Before you begin, ensure you have the following installed:

* **Python 3.8+** (Recommended: Python 3.9, 3.10, or 3.11)
* **Git** (for cloning the repository)
* **VS Code** (or any preferred code editor)

### Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/](https://github.com/)[YourUsername]/spectracell_dashboard.git
    cd spectracell_dashboard
    ```
    *(Replace `[YourUsername]` with your actual GitHub username.)*

2.  **Create and activate a virtual environment:**
    It's highly recommended to use a virtual environment to manage dependencies.

    * **For Windows:**
        ```bash
        python -m venv venv
        .\venv\Scripts\activate
        ```
    * **For macOS/Linux:**
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```

3.  **Install project dependencies:**
    With the virtual environment activated, install the required Python packages:

    ```bash
    pip install -r requirements.txt
    ```

### Running Locally

1.  **Start the Dash application:**
    Ensure your virtual environment is active (you should see `(venv)` in your terminal prompt).
    ```bash
    python app.py
    ```

2.  **Access the dashboard:**
    Open your web browser and navigate to the URL displayed in your terminal (e.g., `http://127.0.0.1:8050/`).
