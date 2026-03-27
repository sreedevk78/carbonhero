import os
import json
import re
import numpy as np
from sklearn.linear_model import LinearRegression
import google.generativeai as genai
import speech_recognition as sr
import openai
from groq import Groq
from app.utils.carbon import compute_emissions_from_activity

# Gemini AI Configuration
GOOGLE_API_KEY = os.environ.get('GEMINI_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)

# OpenAI Fallback Configuration
def get_openai_client():
    """Returns an OpenAI client if a valid API key is available."""
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        try:
            env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
            with open(env_path, 'r') as f:
                for line in f:
                    if line.strip().startswith('OPENAI_API_KEY='):
                        api_key = line.strip().split('=', 1)[1]
                        break
        except:
            pass
    if api_key:
        return openai.OpenAI(api_key=api_key)
    return None

# Groq Configuration
def get_groq_client():
    """Returns a Groq client if a valid API key is available."""
    api_key = os.environ.get('GROQ_API_KEY')
    if not api_key:
        try:
            env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
            with open(env_path, 'r') as f:
                for line in f:
                    if line.strip().startswith('GROQ_API_KEY='):
                        api_key = line.strip().split('=', 1)[1]
                        break
        except:
            pass
    if api_key:
        return Groq(api_key=api_key)
    return None

model = None

def build_gemini_model():
    candidates = []
    explicit_model = os.environ.get('GEMINI_MODEL', '').strip()
    if explicit_model:
        candidates.append(explicit_model)
    candidates.extend(['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro'])
    try:
        for discovered in genai.list_models():
            methods = getattr(discovered, 'supported_generation_methods', []) or []
            if 'generateContent' in methods:
                name = getattr(discovered, 'name', '')
                if name.startswith('models/'):
                    name = name.split('/', 1)[1]
                if name:
                    candidates.append(name)
    except Exception:
        pass

    seen = set()
    for candidate in candidates:
        if not candidate: continue
        if candidate in seen: continue
        seen.add(candidate)
        try:
            return genai.GenerativeModel(candidate)
        except Exception:
            continue
    return None

def get_gemini_model():
    global model
    if model is None:
        model = build_gemini_model()
    return model

def generate_ai_text(prompt):
    """Multi-tier AI generation: Groq (Primary) -> Gemini -> OpenAI."""
    # --- 1. GROQ (User Preferred) ---
    try:
        client = get_groq_client()
        if client:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                timeout=12
            )
            return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Groq error: {str(e)}")

    # --- 2. GEMINI (Secondary) ---
    active_model = get_gemini_model()
    if active_model is not None:
        try:
            response = active_model.generate_content(prompt, request_options={"timeout": 12})
            return response.text.strip() if getattr(response, 'text', None) else None
        except Exception as e:
            print(f"Gemini error: {str(e)}")

    # --- 3. OPENAI (Tertiary) ---
    try:
        client = get_openai_client()
        if client:
            openai_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                timeout=12
            )
            return openai_response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI error: {str(e)}")

    return None

def generate_gemini_text(prompt):
    """Wrapper for legacy calls to ensure they use the new multi-tier engine."""
    return generate_ai_text(prompt)

def extract_activity_data_local(activity_description):
    text = (activity_description or "").lower().strip()
    data = {
        'transport_type': None,
        'distance_km': None,
        'energy_kwh': None,
        'fuel_liters': None,
        'fuel_type': None,
        'diet_type': None,
        'flight_distance_km': None
    }
    # Use position-based extraction to favor the first mentioned activity if there are multiple (e.g. "walked instead of bike")
    found_types = []
    if any(w in text for w in ['flight', 'plane', 'airplane', 'aeroplane']):
        pos = min([text.find(w) for w in ['flight', 'plane', 'airplane', 'aeroplane'] if w in text])
        found_types.append(('flight', pos))
    if any(w in text for w in ['car', 'taxi', 'uber', 'cab']):
        pos = min([text.find(w) for w in ['car', 'taxi', 'uber', 'cab'] if w in text])
        found_types.append(('car', pos))
    if 'bus' in text:
        found_types.append(('bus', text.find('bus')))
    if any(w in text for w in ['train', 'metro']):
        pos = min([text.find(w) for w in ['train', 'metro'] if w in text])
        found_types.append(('train', pos))
    if any(w in text for w in ['bike', 'bicycle']):
        pos = min([text.find(w) for w in ['bike', 'bicycle'] if w in text])
        found_types.append(('bike', pos))
    if any(w in text for w in ['walk', 'walking']):
        pos = min([text.find(w) for w in ['walk', 'walking'] if w in text])
        found_types.append(('walk', pos))
    
    if found_types:
        found_types.sort(key=lambda x: x[1])
        data['transport_type'] = found_types[0][0]

    distance_match = re.search(r"(\d+(?:\.\d+)?)\s*(kms?|kilometres?|kilometers?|miles?|mis?|meters?|m)\b", text)
    if distance_match:
        value = float(distance_match.group(1))
        unit = distance_match.group(2)
        if unit.startswith('mi'):
            km_value = value * 1.60934
        elif unit.startswith('m') and not unit.startswith('mi') and not unit.startswith('k'):
            km_value = value / 1000.0 # meters
        else:
            km_value = value
        data['distance_km'] = km_value
        if data['transport_type'] == 'flight':
            data['flight_distance_km'] = km_value

    liters_match = re.search(r"(\d+(?:\.\d+)?)\s*(l|liters?|litres?)\b", text)
    if liters_match:
        data['fuel_liters'] = float(liters_match.group(1))
        data['fuel_type'] = 'diesel' if 'diesel' in text else 'petrol'

    kwh_match = re.search(r"(\d+(?:\.\d+)?)\s*(kwh|kilowatt[- ]?hours?)\b", text)
    if kwh_match: data['energy_kwh'] = float(kwh_match.group(1))

    if any(w in text for w in ['beef', 'lamb', 'meat', 'chicken', 'mutton']): data['diet_type'] = 'meat'
    elif 'vegetarian' in text: data['diet_type'] = 'vegetarian'
    elif 'vegan' in text: data['diet_type'] = 'vegan'
    elif any(w in text for w in ['fish', 'egg', 'eggs', 'dairy']): data['diet_type'] = 'mixed'

    return data

def extract_activity_data_with_ai(activity_description):
    prompt = f"""
    Extract structured activity data from this text and return strict JSON only.
    Activity text: "{activity_description}"

    Return JSON with keys:
    - transport_type: one of [car,bus,train,bike,walk,flight,null]
    - distance_km: number or null
    - energy_kwh: number or null
    - fuel_liters: number or null
    - fuel_type: one of [petrol,diesel,null]
    - diet_type: one of [meat,mixed,vegetarian,vegan,null]
    - flight_distance_km: number or null

    Rules:
    - If uncertain, use null.
    """
    try:
        text = generate_ai_text(prompt)
        if not text: return None
        json_blob = re.search(r"\{[\s\S]*\}", text)
        if not json_blob: return None
        parsed = json.loads(json_blob.group(0))
        return {
            'transport_type': parsed.get('transport_type'),
            'distance_km': parsed.get('distance_km'),
            'energy_kwh': parsed.get('energy_kwh'),
            'fuel_liters': parsed.get('fuel_liters'),
            'fuel_type': parsed.get('fuel_type'),
            'diet_type': parsed.get('diet_type'),
            'flight_distance_km': parsed.get('flight_distance_km')
        }
    except:
        return None

def estimate_emissions_from_text(activity_description):
    local_data = extract_activity_data_local(activity_description)
    result = compute_emissions_from_activity(local_data)
    return result['total_kg']

def calculate_ai_emissions(activity_description):
    """Calculates emissions and returns a dict with 'total_kg' and extracted 'metadata'."""
    try:
        local_data = extract_activity_data_local(activity_description)
        ai_data = extract_activity_data_with_ai(activity_description)

        merged_data = dict(local_data)
        if ai_data:
            for key, value in ai_data.items():
                if value is not None and (merged_data.get(key) is None):
                    merged_data[key] = value

        result = compute_emissions_from_activity(merged_data)
        return {
            'total_kg': result['total_kg'],
            'metadata': {
                'transport_type': merged_data.get('transport_type'),
                'diet_type': merged_data.get('diet_type'),
                'distance_km': merged_data.get('distance_km')
            }
        }
    except Exception as e:
        print(f"AI Calculation Error: {str(e)}")
        local_data = extract_activity_data_local(activity_description)
        # Fallback to local only calculation if AI fails
        try:
            result = compute_emissions_from_activity(local_data)
            return {
                'total_kg': result['total_kg'],
                'metadata': {
                    'transport_type': local_data.get('transport_type'),
                    'diet_type': local_data.get('diet_type'),
                    'distance_km': local_data.get('distance_km')
                }
            }
        except Exception as e2:
            raise e2

def speech_to_text():
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            audio = recognizer.listen(source, timeout=5)
            return recognizer.recognize_google(audio)
    except:
        return None

def fetch_environmental_news():
    prompt = """
    Provide exactly 5 recent and significant environmental news stories.
    Return strict JSON only in this exact format:
    {
      "items": [
        {"title": "...", "description": "...", "source": "https://..."},
        {"title": "...", "description": "...", "source": "https://..."}
      ]
    }

    Requirements:
    - Keep each title under 120 characters.
    - Keep each description 2-3 sentences, factual and concise.
    - Focus on climate policy, renewables, conservation, and sustainable innovation.
    - For "source", provide a real URL to a credible news outlet (Reuters, BBC, Guardian, AP News, etc.). If unsure, provide a Google News search URL for the headline.
    """
    try:
        news_text = generate_ai_text(prompt)
        news_items = []
        
        if news_text:
            json_blob = re.search(r"\{[\s\S]*\}", news_text)
            if json_blob:
                parsed = json.loads(json_blob.group(0))
                items = parsed.get('items', [])
                for item in items:
                    title = str(item.get('title', '')).strip()
                    description = str(item.get('description', '')).strip()
                    source = str(item.get('source', '')).strip()
                    if not source or not source.startswith('http'):
                        source = 'https://www.google.com/search?q=' + '+'.join(title.split()[:8])
                    if title and description:
                        news_items.append({'title': title, 'description': description, 'source': source})

        if not news_items:
            current_stories = news_text.split('\n\n')
            for story in current_stories:
                if 'TITLE:' in story and 'DESCRIPTION:' in story:
                    title = story.split('TITLE:')[1].split('DESCRIPTION:')[0].strip()
                    description = story.split('DESCRIPTION:')[1].strip()
                    if title and description:
                        news_items.append({'title': title, 'description': description})

        # --- FALLBACK PROTECTION IF GEMINI QUOTA MET ---
        if not news_items:
            return [{'title': 'Global Renewable Capacity Hits Record High', 'description': 'Solar and wind energy installations have surpassed estimates, accounting for the highest percentage of grid power.', 'source': 'https://www.reuters.com/business/environment/'}, {'title': 'New Ocean Conservation Treaty Signed', 'description': 'Nations agree to protect 30% of international waters by 2030, a monumental step for biodiversity.', 'source': 'https://www.bbc.com/news/science_and_environment'}, {'title': 'Breakthrough in Solid-State Battery Tech', 'description': 'Researchers announce a new battery architecture that could double EV ranges and lower manufacturing carbon costs.', 'source': 'https://www.nature.com/environment/'}, {'title': 'Major Reforestation Initiative Launches', 'description': 'A multi-national coalition pledges billions to restore degraded sections of tracking progress with satellite AI.', 'source': 'https://www.theguardian.com/environment'}, {'title': 'Urban Farming Reduces City Heat Islands', 'description': 'A new study confirms that aggressive green-roofing dramatically lowers local temperatures and offsets emissions.', 'source': 'https://www.apnews.com/hub/climate'}]

        return news_items[:5] if news_items else None
    except:
        return [{'title': 'Global Renewable Capacity Hits Record High', 'description': 'Solar and wind energy installations have surpassed estimates, accounting for the highest percentage of grid power.', 'source': 'https://www.reuters.com/business/environment/'}, {'title': 'New Ocean Conservation Treaty Signed', 'description': 'Nations agree to protect 30% of international waters by 2030, a monumental step for biodiversity.', 'source': 'https://www.bbc.com/news/science_and_environment'}, {'title': 'Breakthrough in Solid-State Battery Tech', 'description': 'Researchers announce a new battery architecture that could double EV ranges and lower manufacturing carbon costs.', 'source': 'https://www.nature.com/environment/'}, {'title': 'Major Reforestation Initiative Launches', 'description': 'A multi-national coalition pledges billions to restore degraded sections of tracking progress with satellite AI.', 'source': 'https://www.theguardian.com/environment'}, {'title': 'Urban Farming Reduces City Heat Islands', 'description': 'A new study confirms that aggressive green-roofing dramatically lowers local temperatures and offsets emissions.', 'source': 'https://www.apnews.com/hub/climate'}]

class CarbonPredictor:
    def __init__(self):
        self.model = LinearRegression()
        # Mock training data
        X = np.array([[1, 2], [2, 3], [3, 4], [4, 5]])
        y = np.array([10, 20, 30, 40])
        self.model.fit(X, y)
    
    def predict_reduction(self, features):
        return self.model.predict([features])[0]
