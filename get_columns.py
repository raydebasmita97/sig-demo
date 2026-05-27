import tomllib
import requests

with open(".streamlit/secrets.toml", "rb") as f:
    secrets = tomllib.load(f)

api_key = secrets["MONDAY_API_KEY"]
board_id = secrets["MONDAY_BOARD_ID"]

query = f"""
query {{
  boards(ids: {board_id}) {{
    columns {{
      id
      title
      type
    }}
  }}
}}
"""

response = requests.post(
    "https://api.monday.com/v2",
    headers={
        "Authorization": api_key,
        "Content-Type": "application/json",
        "API-Version": "2024-01",
    },
    json={"query": query},
)

data = response.json()

if "errors" in data:
    print("API errors:", data["errors"])
else:
    columns = data["data"]["boards"][0]["columns"]
    print(f"{'Title':<35} {'ID':<25} {'Type'}")
    print("-" * 75)
    for col in columns:
        print(f"{col['title']:<35} {col['id']:<25} {col['type']}")
