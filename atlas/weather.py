import json
import logging
from datetime import datetime, timedelta

import requests

import atlas.config as config

WEEKDAY_MAP = {
    "lunedi": 0,
    "lunedì": 0,
    "lunedí": 0,
    "lunedî": 0,
    "lunedï": 0,
    "martedi": 1,
    "martedì": 1,
    "martedí": 1,
    "martedî": 1,
    "martedï": 1,
    "mercoledi": 2,
    "mercoledì": 2,
    "mercoledí": 2,
    "mercoledî": 2,
    "mercoledï": 2,
    "giovedi": 3,
    "giovedì": 3,
    "giovedí": 3,
    "giovedî": 3,
    "giovedï": 3,
    "venerdi": 4,
    "venerdì": 4,
    "venerdí": 4,
    "venerdî": 4,
    "venerdï": 4,
    "sabato": 5,
    "domenica": 6,
}


def handleWeatherPrompt(prompt):
    logging.info("Entering handleWeatherPrompt() function...")
    request = extractWeatherInfo(prompt)
    logging.info(f"Weather requested for: City = {request['city']}, Date = {request['date']}")

    report = getWeather(city=request["city"], date=request["date"])
    result = {
        "request": request,
        "report": report,
        "context": buildWeatherContext(request, report),
        "message": buildWeatherMessage(report),
    }
    logging.info(f"Weather result: {result}")
    return result


def extractWeatherInfo(prompt):
    logging.info("Entering extractWeatherInfo() function...")
    sys_msg = (
        "You extract ONLY the city name and the date from the user's request.\n"
        "Examples:\n"
        "- 'What's the weather in Rome tomorrow?' -> {\"city\":\"Rome\",\"date\":\"tomorrow\"}\n"
        "- 'Weather in Paris on 2024-03-12' -> {\"city\":\"Paris\",\"date\":\"2024-03-12\"}\n"
        "- 'Weather in Milan friday' -> {\"city\":\"Milan\",\"date\":\"friday\"}\n"
        "- 'Weather in Rho' -> {\"city\":\"Rho\",\"date\":\"today\"}\n"
        "Respond always in JSON: {\"city\":\"city_name\",\"date\":\"YYYY-MM-DD/tomorrow/today/weekday\"}"
    )

    chat_completion = config.get_groq_client().chat.completions.create(
        messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": prompt}],
        model=config.app.groq_model,
    )

    response = chat_completion.choices[0].message.content
    logging.info(f"Response in extractWeatherInfo: {response}")
    data = json.loads(response)

    date_str = data["date"].lower()
    today = datetime.today()

    if date_str == "today":
        target_date = today
    elif date_str == "tomorrow":
        target_date = today + timedelta(days=1)
    elif date_str in WEEKDAY_MAP:
        target_date = next_weekday(today, date_str)
    else:
        target_date = datetime.strptime(date_str, "%Y-%m-%d")

    result = {"city": data["city"], "date": target_date.strftime("%Y-%m-%d")}
    logging.info(f"Normalized weather request: {result}")
    return result


def next_weekday(current_date, weekday_name):
    logging.info("Entering next_weekday() function...")
    weekday = WEEKDAY_MAP[weekday_name.lower()]
    days_ahead = weekday - current_date.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    logging.info(f"next_weekday result: {current_date + timedelta(days=days_ahead)}")
    return current_date + timedelta(days=days_ahead)


def getWeather(city, lang="it", units="metric", date="today"):
    logging.info("Entering getWeather() function...")
    base_url = "http://api.openweathermap.org/data/2.5/"

    if date == "today":
        url = f"{base_url}weather?q={city}&appid={config.app.weather_api_key}&units={units}&lang={lang}"
        response = requests.get(url).json()

        if response.get("cod") != 200:
            return {"status": "error", "city": city, "date": date, "message": "Unable to retrieve today's weather."}

        return {
            "status": "ok",
            "city": city,
            "date": datetime.today().strftime("%Y-%m-%d"),
            "description": response["weather"][0]["description"],
            "temperature_c": response["main"]["temp"],
            "source": "current",
        }

    url = f"{base_url}forecast?q={city}&appid={config.app.weather_api_key}&units={units}&lang={lang}"
    response = requests.get(url).json()

    if response.get("cod") != "200":
        return {"status": "error", "city": city, "date": date, "message": "Unable to retrieve the forecast."}

    target_date = datetime.strptime(date, "%Y-%m-%d").date()
    forecasts = response["list"]
    target_forecasts = [item for item in forecasts if datetime.fromtimestamp(item["dt"]).date() == target_date]

    if not target_forecasts:
        return {
            "status": "error",
            "city": city,
            "date": date,
            "message": f"No weather information found for {date}.",
        }

    avg_temp = sum(item["main"]["temp"] for item in target_forecasts) / len(target_forecasts)
    return {
        "status": "ok",
        "city": city,
        "date": target_date.strftime("%Y-%m-%d"),
        "description": target_forecasts[0]["weather"][0]["description"],
        "temperature_c": round(avg_temp, 1),
        "source": "forecast",
    }


def buildWeatherContext(request, report):
    return {
        "request_city": request["city"],
        "request_date": request["date"],
        "status": report["status"],
        "city": report.get("city"),
        "date": report.get("date"),
        "description": report.get("description"),
        "temperature_c": report.get("temperature_c"),
        "source": report.get("source"),
        "message": report.get("message"),
    }


def buildWeatherMessage(report):
    if report["status"] != "ok":
        return report["message"]

    if report["source"] == "current":
        return (
            f"Today's weather in {report['city']}: {report['description']}, "
            f"temperature {report['temperature_c']}°C."
        )

    return (
        f"Weather in {report['city']} on {report['date']}: {report['description']}, "
        f"average temperature {report['temperature_c']}°C."
    )
