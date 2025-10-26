import requests
import pandas as pd

def fetch_cdc_data(url='https://data.cdc.gov/api/views/9bhg-hcku/rows.csv?accessType=DOWNLOAD'):
    response = requests.get(url)
    response.raise_for_status()
    with open('cdc_data.csv', 'wb') as f:
        f.write(response.content)
    df = pd.read_csv('cdc_data.csv')
    print("Columns available:", df.columns.tolist())
    return df
