
"""
Inventory Adjustment Report Automation Script

This script connects to a SQL Server database to extract inventory adjustment data,
process it, and export client-specific Excel reports for operational and audit use.

Author: Tommy Warren
Date: 2025-04-16
"""

import pandas as pd
import pyodbc
import numpy as np
import os
import argparse
from datetime import datetime

# === CONFIGURATION ===
DEFAULT_OUTPUT_DIR = "./reports/"

# === DATABASE CONNECTION ===
def get_connection():
    """
    Establishes a trusted connection to the SQL Server database.
    Returns a live database connection object.
    """
    
    return pyodbc.connect(
        'Driver={SQL Server};'
        'Server=YOUR_SERVER;'  # Replace with your server
        'Database=YOUR_DATABASE;'  # Replace with your DB name
        'Trusted_Connection=yes;'
    )

# === GET CLIENT CODES FROM DATABASE ===
def get_client_codes(conn):
    """
    Retrieves a distinct list of client codes by extracting the first 3 characters
    from the 'Source No_' field in the Inventory Adjustment Header table.
    """
    
    client_query = """
    SELECT DISTINCT LEFT([Source No_], 3) AS ClientCode
    FROM [Inventory Adj Header]
    WHERE [Source No_] IS NOT NULL AND LEN([Source No_]) >= 3
    """
    df = pd.read_sql(client_query, conn)
    return df['ClientCode'].dropna().unique().tolist()

# === MAIN FUNCTION ===
def generate_inventory_adjustments(output_dir, clients=None):
    
    """
    Queries, processes, and exports inventory adjustment data grouped by client.
    Saves the results as Excel files, one per client, in the specified output directory.
    """
    
    conn = get_connection()

    if not clients:
        clients = get_client_codes(conn)

    # Step 1: Query ledger activity
    ledger_query = """
    SELECT [Item No], [Document No], [Posting Date], [Entry Type], [Quantity],
           [Location Code], [Reason Code]
    FROM [Inventory Ledger Entry]
    """
    ledger_df = pd.read_sql(ledger_query, conn)

    # Step 2: Query adjustment header info
    header_query = """
    SELECT [Document No], [User ID], [Source No_]
    FROM [Inventory Adj Header]
    """
    header_df = pd.read_sql(header_query, conn)

    # Step 3: Query reason code descriptions
    reason_query = """
    SELECT [Code], [Description]
    FROM [Reason Code]
    """
    reason_df = pd.read_sql(reason_query, conn)

    conn.close()

    # Step 4: Clean and merge data
    adj_df = ledger_df[ledger_df['Entry Type'] == 1]  # Filter for adjustments
    adj_df = adj_df[adj_df['Quantity'] != 0]  # Remove zero-qty rows
    adj_df = adj_df[adj_df['Reason Code'].notnull()]

    merged_df = adj_df.merge(header_df, on='Document No', how='left')
    merged_df = merged_df.merge(reason_df, left_on='Reason Code', right_on='Code', how='left')

    # Step 5: Group and export by client
    for client in clients:
        client_df = merged_df[merged_df['Source No_'].str.startswith(client)]
        if not client_df.empty:
            filename = f"{client}_Inventory_Adjustments_{datetime.now().strftime('%Y%m%d')}.xlsx"
            client_df.to_excel(os.path.join(output_dir, filename), index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate daily inventory adjustment reports.")
    parser.add_argument('--output_dir', type=str, default=DEFAULT_OUTPUT_DIR,
                        help='Directory to save Excel reports.')
    parser.add_argument('--clients', nargs='+',
                        help='Optional: specify client codes to include in the report (e.g., GRL MRA KAV). If omitted, the script will automatically retrieve all distinct client codes from the database.')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    generate_inventory_adjustments(args.output_dir, args.clients)
