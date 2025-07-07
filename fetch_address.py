import requests

def fetch_all_tokens():
    response = requests.get("https://token.jup.ag/all")
    response.raise_for_status()
    return response.json()

def get_token_address(symbol: str, tokens: list):
    for token in tokens:
        if token['symbol'].upper() == symbol.upper():
            return token['address']
    raise ValueError(f"Token symbol '{symbol}' not found.")

if __name__ == "__main__":
    tokens = fetch_all_tokens()

    token_symbol = "USDT"
    usdt_address = get_token_address(token_symbol, tokens)

    print(f"Retrieved address for {token_symbol}: {usdt_address}")
