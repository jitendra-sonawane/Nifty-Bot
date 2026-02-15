import pandas as pd
import os

# Get the correct path to NSE.csv (in backend directory)
csv_path = os.path.join(os.path.dirname(__file__), "..", "backend", "NSE.csv")
df = pd.read_csv(csv_path)

def get_instrument_keys(current_price:float,expiry_date:str,num_strikes:int=5):

    nifty_options = df[
        (df['expiry'] == expiry_date) & 
        (df['name'] == 'NIFTY')
    ]
    if nifty_options.empty:
        print("No option found")
        return None

    strike = sorted(nifty_options['strike'].unique())

    atm_strike = min(strike,key=lambda x:abs(x-current_price))
    atm_index = strike.index(atm_strike)

    start_index =  atm_index - num_strikes +1
    end_index = atm_index + num_strikes+1
    
    selected_strike = strike[start_index:end_index]
    selected_options = nifty_options[nifty_options['strike'].isin(selected_strike)]
    ce_options = selected_options[selected_options["option_type"] == "CE"].sort_values("strike")
    pe_options = selected_options[selected_options["option_type"] == "PE"].sort_values("strike")

    ce_instrument_keys = ce_options["instrument_key"].tolist()
    pe_instrument_keys = pe_options["instrument_key"].tolist()
    
    # Create Metadata Map: key -> {strike, type}
    metadata = {}
    for _, row in selected_options.iterrows():
        metadata[row['instrument_key']] = {
            'strike': row['strike'],
            'type': row['option_type']
        }

    result ={
        "current_price": current_price,
        "atm_strike": atm_strike,
        "ce_options": ce_instrument_keys,
        "pe_options": pe_instrument_keys,
        "metadata": metadata  # <--- NEW FIELD
    }
    return result
    
    # df2 = df.copy()
    # # if 
    # df2 = df2[df2['expiry'] == expiry_date]
    # # df2 = df2[df2['tradingsymbol'] == symbol]
    # df2 = df2[df2['strike'] == strike_price]
    # df2 = df2[df2['option_type'] == option_type]
    # print(df2)
    # return df2
    # print(df2[df2['expiry_date'] == expiry_date])


result =get_instrument_keys(26000,"2025-12-09")
print(result)