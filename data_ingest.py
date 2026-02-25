import requests
import pandas as pd
import io

def fetch_cdc_data(url='https://data.cdc.gov/api/views/9bhg-hcku/rows.csv?accessType=DOWNLOAD'):
    """
    Fetches live COVID-19 mortality data from the CDC API.
    Includes filtering to prevent double-counting of demographics.
    """
    print(f"DEBUG: Fetching data from {url}...")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        # Read CSV directly from memory (no need to save to disk first)
        df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
        
        print("DEBUG: Columns available:", df.columns.tolist())
        
        # --- ARCHITECTURAL FILTERING ---
        # The CDC dataset includes breakdowns by State, Sex, and Age.
        # We must filter to 'United States', 'All Sexes', and 'All Ages' 
        # to get the correct national timeline without duplicates.
        
        # 1. Filter for National Level (if 'State' column exists)
        if 'State' in df.columns:
            df = df[df['State'] == 'United States']
            
        # 2. Filter for Aggregate Sex (if 'Sex' column exists)
        if 'Sex' in df.columns:
            df = df[df['Sex'] == 'All Sexes']
            
        # 3. Filter for Aggregate Age (if 'Age Group' column exists)
        if 'Age Group' in df.columns:
            df = df[df['Age Group'] == 'All Ages']

        # 4. Clean and Numericize
        # Ensure 'COVID-19 Deaths' is numeric and fill NaNs with 0
        if 'COVID-19 Deaths' in df.columns:
            df['COVID-19 Deaths'] = pd.to_numeric(df['COVID-19 Deaths'], errors='coerce').fillna(0)
        
        # 5. Ensure Year is integer
        if 'Year' in df.columns:
            df = df.dropna(subset=['Year'])
            df['Year'] = df['Year'].astype(int)

        print(f"DEBUG: Data fetched successfully. Rows after filtering: {len(df)}")
        return df

    except Exception as e:
        print(f"CRITICAL ERROR fetching CDC data: {e}")
        # Fallback to empty dataframe structure to prevent crash
        return pd.DataFrame(columns=["Year", "COVID-19 Deaths"])
