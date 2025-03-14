import logging
import json
from datetime import datetime, timedelta
import requests

from atlas.config import groqClient, weatherApiKey

def handleWeatherPrompt(prompt):
    info = extractWeatherInfo(prompt)
    city = info['city']
    date = info['date']
    logging.info(f"Weather requested for: City = {city}, Date = {date}")

    weatherReport = getWeather(city=city, date=date)
    logging.info(f'Weather report: {weatherReport}')
    return weatherReport

def extractWeatherInfo(prompt):
    sysMsg = (
        "You extract ONLY the city name and the date from the user's request.\n"
        "Examples:\n"
        "- 'What's the weather in Rome tomorrow?' -> {\"city\":\"Rome\",\"date\":\"tomorrow\"}\n"
        "- 'Weather in Paris on 2024-03-12' -> {\"city\":\"Paris\",\"date\":\"2024-03-12\"}\n"
        "- 'Weather in Milan friday' -> {\"city\":\"Milan\",\"date\":\"friday\"}\n"
        "- 'Weather in Rho' -> {\"city\":\"Rho\",\"date\":\"today\"}\n"
        "Respond always in JSON: {\"city\":\"city_name\",\"date\":\"YYYY-MM-DD/tomorrow/today/weekday\"}"
    )

    chatCompletion = groqClient.chat.completions.create(
        messages=[{'role':'system', 'content':sysMsg}, {'role':'user', 'content':prompt}],
        model='llama-3.1-8b-instant'
    )

    response = chatCompletion.choices[0].message.content
    data = json.loads(response)

    date_str = data["date"].lower()
    today = datetime.today()
    days = [
        "lunedi", "lunedì", "lunedí", "lunedî", "lunedï",
        "martedi", "martedì", "martedí", "martedî", "martedï",
        "mercoledi", "mercoledì", "mercoledí", "mercoledî", "mercoledï",
        "giovedi", "giovedì", "giovedí", "giovedî", "giovedï",
        "venerdi", "venerdì", "venerdí", "venerdî", "venerdï",
        "sabato",
        "domenica"
    ]

    if date_str == 'today':
        target_date = today
    elif date_str == 'tomorrow':
        target_date = today + timedelta(days=1)
    elif date_str in days:
        target_date = next_weekday(today, date_str)
    else:
        target_date = datetime.strptime(date_str, '%Y-%m-%d')

    data['date'] = target_date.strftime('%Y-%m-%d')
    return data

def next_weekday(d, weekday_name):
    weekdays = {
        'lunedi': 0, 'lunedì': 0, 'lunedí': 0, 'lunedî': 0, 'lunedï': 0,
        'martedi': 1, 'martedì': 1, 'martedí': 1, 'martedî': 1, 'martedï': 1,
        'mercoledi': 2, 'mercoledì': 2, 'mercoledí': 2, 'mercoledî': 2, 'mercoledï': 2,
        'giovedi': 3, 'giovedì': 3, 'giovedí': 3, 'giovedî': 3, 'giovedï': 3,
        'venerdi': 4, 'venerdì': 4, 'venerdí': 4, 'venerdî': 4, 'venerdï': 4,
        'sabato': 5,
        'domenica': 6
    }

    weekday = weekdays[weekday_name.lower()]
    days_ahead = weekday - d.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return d + timedelta(days=days_ahead)

def getWeather(city, lang="it", units="metric", date='today'):
    baseUrl = "http://api.openweathermap.org/data/2.5/"

    if date == 'today':
        url = f"{baseUrl}weather?q={city}&appid={weatherApiKey}&units={units}&lang={lang}"
        response = requests.get(url).json()
        
        if response.get('cod') != 200:
            return "I'm sorry, I couldn't retrieve today's weather."
        
        weather_desc = response['weather'][0]['description']
        temp = response['main']['temp']
        return f"Today's weather in {city}: {weather_desc}, temperature {temp}°C."
    else:
        url = f"{baseUrl}forecast?q={city}&appid={weatherApiKey}&units={units}&lang={lang}"
        response = requests.get(url).json()

        if response.get('cod') != "200":
            return "I'm sorry, I couldn't retrieve the forecast."

        if date == 'tomorrow':
            target_date = (datetime.now() + timedelta(days=1)).date()
        else:
            target_date = datetime.strptime(date, '%Y-%m-%d').date()

        forecasts = response['list']
        target_forecasts = [f for f in forecasts if datetime.fromtimestamp(f['dt']).date() == target_date]

        if not target_forecasts:
            return f"I'm sorry, I couldn't find weather information for {date}."

        avg_temp = sum([f['main']['temp'] for f in target_forecasts]) / len(target_forecasts)
        weather_desc = target_forecasts[0]['weather'][0]['description']

        formatted_date = target_date.strftime("%Y-%m-%d")
        return f"in {city} on {formatted_date}: {weather_desc}, average temperature {avg_temp:.1f}°C."