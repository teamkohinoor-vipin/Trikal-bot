import re
import html
import json
import requests
import logging
from io import BytesIO
from datetime import datetime
from config import PHONE_API_NEW

logger = logging.getLogger(__name__)

def normalize_phone_number(text):
    digits = re.sub(r'\D', '', text)
    if len(digits) == 10:
        return digits
    elif len(digits) == 12 and digits.startswith('91'):
        return digits[2:]
    elif len(digits) == 11 and digits.startswith('0'):
        return digits[1:] if len(digits[1:]) == 10 else None
    elif len(digits) > 10:
        return digits[-10:]
    return None

def format_address(address):
    if not address or address == 'N/A':
        return 'N/A'
    address = re.sub(r'\s+', ' ', address.strip())
    words = address.split()
    unique = []
    for w in words:
        if w not in unique:
            unique.append(w)
    return ' '.join(unique)

def create_safe_filename(query, search_type, bot_username):
    safe = re.sub(r'[<>:"/\\|?*]', '_', str(query))[:50]
    return f"{search_type}_{safe} @{bot_username}.txt"

def create_search_result_file(result_text, query, search_type, bot_username):
    clean = re.sub(r'<[^>]+>', '', result_text)
    clean = html.unescape(clean)
    content = f"Search Query: {query}\nSearch Type: {search_type}\nGenerated: {datetime.now()}\nBot: @{bot_username}\n{'='*50}\n\n{clean}"
    f = BytesIO(content.encode('utf-8'))
    f.name = create_safe_filename(query, search_type, bot_username)
    return f

# ---------- UPDATED fetch_phone_info for new API ----------
def fetch_phone_info(phone_number):
    """
    Fetch phone details from new API.
    Returns a list of subscriber dicts (empty if no data or error).
    """
    url = PHONE_API_NEW.format(num=phone_number)
    try:
        resp = requests.get(url, timeout=7)
        if resp.status_code != 200:
            logger.warning(f"API returned {resp.status_code}")
            return []

        data = resp.json()

        # ========== NEW API FORMAT (status: true, result: { results: [...] }) ==========
        if data.get('status') is True and 'result' in data:
            result = data.get('result', {})
            results = result.get('results', [])
            if results and isinstance(results, list):
                normalized = []
                # Field mapping: API field -> our display field
                field_map = {
                    'name': 'name',
                    'fname': 'father_name',
                    'address': 'address',
                    'mobile': 'mobile',
                    'alt': 'alternate_number',
                    'circle': 'circle',
                    'id': 'id',
                    'email': 'email'
                }
                for rec in results:
                    new_rec = {}
                    for api_key, our_key in field_map.items():
                        if api_key in rec and rec[api_key]:
                            # Handle None or empty strings
                            value = rec[api_key]
                            if value is not None and str(value).strip():
                                new_rec[our_key] = str(value)
                    if new_rec:
                        normalized.append(new_rec)
                return normalized

        # ========== OLD API FORMAT (for backward compatibility) ==========
        if data.get('status') == 'success' and 'data' in data:
            subscriber = data['data'].get('subscriber')
            if subscriber and isinstance(subscriber, dict):
                return [subscriber]

        # Fallback: if direct list or 'records' key
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and 'records' in data:
            return data['records']

        return []

    except requests.exceptions.Timeout:
        logger.warning(f"⏱️ API timeout for {phone_number} (5s)")
        return []
    except requests.exceptions.ConnectionError:
        logger.warning(f"🔌 API connection error for {phone_number}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON decode error: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ API error: {e}")
        return []
