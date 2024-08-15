import requests
import logging
import os

API_KEY = os.getenv('API_KEY')
CLAN_TAG = os.getenv('CLAN_TAG')

def fetch_top_clan_trophies():
    logging.info("Fetching clan trophies...")
    url = f"https://api.clashofclans.com/v1/clans/{CLAN_TAG.replace('#', '%23')}"
    headers = {'Authorization': f'Bearer {API_KEY}'}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        logging.debug("Successfully fetched data from API.")
        data = response.json()
        members = data.get('memberList', [])
        sorted_members = sorted(members, key=lambda member: member['trophies'], reverse=True)
        top_members = sorted_members[:25]
        return top_members
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error: {e}")
        return None
