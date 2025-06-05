import requests
from typing import Dict
from django.conf import settings

class NewsAPI:
    BASE_URL = "https://newsapi.org/v2"
    
    @staticmethod
    def get_pharmacy_news() -> Dict:
        """
        Get pharmacy and healthcare related news
        """
        try:
            url = f"{NewsAPI.BASE_URL}/everything"
            params = {
                'q': 'pharmacy OR healthcare OR medicine',
                'language': 'ru',
                'sortBy': 'publishedAt',
                'apiKey': settings.NEWS_API_KEY
            }
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {'error': str(e)}

class WeatherAPI:
    BASE_URL = "https://api.openweathermap.org/data/2.5"
    
    @staticmethod
    def get_minsk_weather() -> Dict:
        """
        Get current weather in Minsk
        """
        try:
            url = f"{WeatherAPI.BASE_URL}/weather"
            params = {
                'q': 'Minsk,BY',
                'units': 'metric',  # Для отображения температуры в градусах Цельсия
                'lang': 'ru',       # Для получения описания погоды на русском
                'appid': settings.OPENWEATHER_API_KEY
            }
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'main' in data and 'weather' in data:
                return {
                    'temp': round(data['main']['temp']),  # Округляем температуру
                    'feels_like': round(data['main']['feels_like']),
                    'humidity': data['main']['humidity'],
                    'description': data['weather'][0]['description'],
                    'icon': data['weather'][0]['icon']
                }
            return {'error': 'Weather data not available'}
            
        except requests.RequestException as e:
            return {'error': str(e)} 