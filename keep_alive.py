import requests
import streamlit as st

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_KEY"]

url = f"{SUPABASE_URL}/rest/v1/vw_parcelas?select=id&limit=1"

headers = {
    "apikey": SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
}

response = requests.get(url, headers=headers, timeout=30)

print("Status:", response.status_code)
response.raise_for_status()