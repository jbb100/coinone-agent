#!/usr/bin/env python3
"""Quick test to check if prices are calculated correctly"""

import requests
from decimal import Decimal

# Test BTC price
btc_response = requests.get('https://api.coinone.co.kr/public/v2/ticker/krw/BTC')
btc_ticker = btc_response.json()

print("BTC Ticker Response:")
print(f"  Result: {btc_ticker.get('result')}")
print(f"  Data: {btc_ticker.get('data', {})}")
print(f"  Close price: {btc_ticker.get('data', {}).get('close_24h')}")

btc_amount = Decimal('0.002116')
btc_price = Decimal(btc_ticker.get('data', {}).get('close_24h', '0'))
btc_value = btc_amount * btc_price

print(f"\nBTC Calculation:")
print(f"  Amount: {btc_amount}")
print(f"  Price: ₩{btc_price:,.0f}")
print(f"  Value: ₩{btc_value:,.0f}")

# Test ETH price
eth_response = requests.get('https://api.coinone.co.kr/public/v2/ticker/krw/ETH')
eth_ticker = eth_response.json()

eth_amount = Decimal('0.046167')
eth_price = Decimal(eth_ticker.get('data', {}).get('close_24h', '0'))
eth_value = eth_amount * eth_price

print(f"\nETH Calculation:")
print(f"  Amount: {eth_amount}")
print(f"  Price: ₩{eth_price:,.0f}")
print(f"  Value: ₩{eth_value:,.0f}")

print(f"\nTotal crypto value: ₩{(btc_value + eth_value):,.0f}")