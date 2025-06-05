from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .utils.api_utils import WeatherAPI
import logging

logger = logging.getLogger(__name__)

@require_http_methods(["GET"])
def get_minsk_weather(request):
    """Get current weather in Minsk"""
    try:
        weather_data = WeatherAPI.get_minsk_weather()
        if 'error' in weather_data:
            logger.error(f"Error getting weather: {weather_data['error']}")
            return JsonResponse({'error': 'Weather data not available'}, status=500)
        return JsonResponse(weather_data)
    except Exception as e:
        logger.error(f"Error in weather API: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500) 