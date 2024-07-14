import sqlite3

def is_wallet_address_present(cursor, wallet_address):
    """
    Check if a wallet address is present in the database.

    Args:
    cursor (sqlite3.Cursor): The database cursor.
    wallet_address (str): The wallet address to check.

    Returns:
    bool: True if the wallet address is present, False otherwise.
    """
    result = cursor.execute("SELECT EXISTS(SELECT 1 FROM deposits WHERE wallet_address = ?)", (wallet_address,)).fetchone()[0]
    return bool(result)

# Set up a test SQLite database
def setup_test_db():
    conn = sqlite3.connect(':memory:')  # In-memory database for testing
    cursor = conn.cursor()
    
    # Create a table
    cursor.execute('''
        CREATE TABLE deposits (
            id INTEGER PRIMARY KEY,
            wallet_address TEXT NOT NULL,
            amount REAL NOT NULL
        )
    ''')
    
    # Insert some test data
    cursor.execute("INSERT INTO deposits (wallet_address, amount) VALUES (?, ?)", ('test_wallet_1', 10))
    cursor.execute("INSERT INTO deposits (wallet_address, amount) VALUES (?, ?)", ('test_wallet_1', 15))
    cursor.execute("INSERT INTO deposits (wallet_address, amount) VALUES (?, ?)", ('test_wallet_2', 5))
    conn.commit()
    
    return conn, cursor

# Main function to test is_wallet_address_present
def main():
    conn, cursor = setup_test_db()
    
    test_addresses = ['test_wallet_1', 'test_wallet_2', 'test_wallet_3']
    for address in test_addresses:
        is_present = is_wallet_address_present(cursor, address)
        print(f"Is wallet address {address} present: {is_present}")
    
    conn.close()

if __name__ == "__main__":
    main()
