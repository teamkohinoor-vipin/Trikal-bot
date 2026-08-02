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

# ---------- UPDATED fetch_phone_info for new API format (supports source1/source2) ----------
def fetch_phone_info(phone_number):
    """
    Fetch phone details from new API.
    Returns a list of subscriber dicts (empty if no data or error).
    Timeout set to 5 seconds.
    """
    url = PHONE_API_NEW.format(num=phone_number)
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            logger.warning(f"API returned {resp.status_code} for {phone_number}")
            return []

        data = resp.json()

        # ========== NEW API FORMAT (multiple sources) ==========
        if data.get('status') is True and 'result' in data:
            result_data = data['result']
            all_records = []
            # Check if 'data' contains source objects
            if 'data' in result_data and isinstance(result_data['data'], dict):
                sources = result_data['data']
                for source_key, source_value in sources.items():
                    if isinstance(source_value, dict) and 'records' in source_value:
                        records = source_value['records']
                        if not isinstance(records, list):
                            continue
                        for rec in records:
                            normalized = {}
                            # Map fields from different sources
                            if 'FullName' in rec and rec['FullName']:
                                normalized['name'] = str(rec['FullName'])
                            if 'FatherName' in rec and rec['FatherName']:
                                normalized['father_name'] = str(rec['FatherName'])
                            # Address: prefer Adres, else Adres2
                            if 'Adres' in rec and rec['Adres']:
                                normalized['address'] = str(rec['Adres'])
                            elif 'Adres2' in rec and rec['Adres2']:
                                normalized['address'] = str(rec['Adres2'])
                            # Phone numbers
                            if 'Phone' in rec and rec['Phone']:
                                normalized['mobile'] = str(rec['Phone'])
                            elif 'Phone2' in rec and rec['Phone2']:
                                normalized['mobile'] = str(rec['Phone2'])
                            elif 'Phone3' in rec and rec['Phone3']:
                                normalized['mobile'] = str(rec['Phone3'])
                            # Alternate number (if different from mobile)
                            if 'Phone2' in rec and rec['Phone2'] and rec['Phone2'] != normalized.get('mobile'):
                                normalized['alternate_number'] = str(rec['Phone2'])
                            elif 'Phone3' in rec and rec['Phone3'] and rec['Phone3'] != normalized.get('mobile'):
                                normalized['alternate_number'] = str(rec['Phone3'])
                            # Circle/Region
                            if 'Region' in rec and rec['Region']:
                                normalized['circle'] = str(rec['Region'])
                            elif 'Stat' in rec and rec['Stat']:
                                normalized['circle'] = str(rec['Stat'])
                            # ID / Document Number
                            if 'DocumentNumber' in rec and rec['DocumentNumber']:
                                normalized['id'] = str(rec['DocumentNumber'])
                            # Age or other fields can be added if needed
                            if normalized:
                                all_records.append(normalized)
                if all_records:
                    return all_records

        # ========== OLD API FORMAT 1 (single subscriber) ==========
        if data.get('status') == 'success' and 'data' in data:
            subscriber = data['data'].get('subscriber')
            if subscriber and isinstance(subscriber, dict):
                return [subscriber]

        # ========== OLD FORMAT 2 (direct list) ==========
        if isinstance(data, list):
            return data

        # ========== OLD FORMAT 3 (records key) ==========
        if isinstance(data, dict) and 'records' in data:
            return data['records']

        logger.warning(f"⚠️ No data found for {phone_number}")
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
