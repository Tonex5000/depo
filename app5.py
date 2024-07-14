import time
import sqlite3
import requests
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Function to get paper balance in USD
def get_paper_balance_usd(cursor, wallet_address):
    paper_balance_bnb = cursor.execute("SELECT SUM(amount) FROM deposits WHERE wallet_address = ?", (wallet_address,)).fetchone()[0]
  
    if paper_balance_bnb is None:
        return 0

    coingecko_symbol = 'binancecoin'
    response = requests.get('https://api.coingecko.com/api/v3/simple/price', 
                            params={'ids': coingecko_symbol, 'vs_currencies': 'usd'})
    response_data = response.json()
    if coingecko_symbol not in response_data or 'usd' not in response_data[coingecko_symbol]:
        logging.error(f"Unable to retrieve BNB to USD conversion rate")
        raise Exception("Unable to retrieve conversion rate")

    bnb_to_usd_rate = response_data[coingecko_symbol]['usd']
    paper_balance_usd = paper_balance_bnb * bnb_to_usd_rate
    
    return paper_balance_usd

# Main function to test get_paper_balance_usd
def main():
    # Connect to your existing database
    database_path = 'trading_bot.db'
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()
    
    wallet_address = '0x2260E6137E221cfD0cC4993Fb08Bb189A3D8000a'
    try:
        while True:
            balance_usd = get_paper_balance_usd(cursor, wallet_address)
            print(f"Paper balance for wallet {wallet_address} in USD: {balance_usd}")
            # Add a delay to avoid spamming requests (e.g., 10 seconds)
            time.sleep(10)
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()