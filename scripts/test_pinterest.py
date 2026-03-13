"""Pinterest API bağlantı testi."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from pinterest.pinterest_client import PinterestClient

client = PinterestClient()

print(f"Pinterest Env: {client.env}")
print(f"Base URL: {client.base_url}")
print(f"Token: {client.access_token[:20]}...{client.access_token[-10:]}")
print()

# Test connection
print("=== Bağlantı Testi ===")
result = client.test_connection()
for k, v in result.items():
    print(f"  {k}: {v}")
print()

if result["status"] == "ok":
    # List boards
    print("=== Panolar ===")
    boards = client.get_boards()
    for board in boards.get("items", []):
        print(f"  [{board['id']}] {board['name']} - {board.get('pin_count', 0)} pin")
else:
    print("Bağlantı başarısız. Token'ı kontrol edin.")
    print("Yardım: https://developers.pinterest.com/apps/")
