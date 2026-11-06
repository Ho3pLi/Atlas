import json
import logging
import unicodedata
from datetime import datetime, timedelta, timezone

import requests

import atlas.config as config

WEEKDAY_MAP = {
    "lunedi": 0,
    "martedi": 1,
    "mercoledi": 2,
    "giovedi": 3,
    "venerdi": 4,
    "sabato": 5,
    "domenica": 6,
}


def handleWeatherPrompt(prompt):
    logging.info("Entering handleWeatherPrompt() function...")
    request = extractWeatherInfo(prompt)
    if request["status"] != "ok":
        return _build_error_result(request["message"])

    report = getWeather(city=request["city"], date=request.get("date_kind", request["date"]))
    if report["status"] == "ok":
        request["date"] = report["date"]
    result = {
        "request": request,
        "report": report,
        "context": buildWeatherContext(request, report),
        "message": buildWeatherMessage(report),
    }
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

    try:
        chat_completion = config.get_groq_client().chat.completions.create(
            messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": prompt}],
            model=config.app.groq_model,
        )
        response = chat_completion.choices[0].message.content
        data = json.loads(response)

        date_str = _normalize_text(data["date"])
        today = datetime.today()

        if date_str == "today":
            target_date = today
        elif date_str == "tomorrow":
            target_date = today + timedelta(days=1)
        elif date_str in WEEKDAY_MAP:
            target_date = next_weekday(today, date_str)
        else:
            target_date = datetime.strptime(date_str, "%Y-%m-%d")

        result = {
            "status": "ok",
            "city": data["city"],
            "date": target_date.strftime("%Y-%m-%d"),
            "date_kind": date_str,
        }
        return result
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logging.error("Weather request parsing failed (%s)", type(exc).__name__)
        return {
            "status": "error",
            "message": "Non sono riuscito a capire per quale citta o giorno vuoi il meteo.",
        }
    except Exception as exc:
        logging.error("Weather intent extraction failed (%s)", type(exc).__name__)
        return {
            "status": "error",
            "message": "C'e stato un problema mentre preparavo la richiesta meteo.",
        }


def next_weekday(current_date, weekday_name):
    logging.info("Entering next_weekday() function...")
    weekday = WEEKDAY_MAP[_normalize_text(weekday_name)]
    days_ahead = weekday - current_date.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return current_date + timedelta(days=days_ahead)


def getWeather(city, lang="it", units="metric", date="today"):
    logging.info("Entering getWeather() function...")
    if not config.app.weather_api_key:
        return _build_weather_error(city, date, "Manca la chiave API per il servizio meteo.")

    base_url = "https://api.openweathermap.org/data/2.5/"

    try:
        if date == "today":
            url = f"{base_url}weather"
            response = requests.get(url, params={"q": city, "appid": config.app.weather_api_key, "units": units, "lang": lang}, timeout=15)
            response.raise_for_status()
            payload = response.json()

            if payload.get("cod") != 200:
                return _build_weather_error(city, date, "Non sono riuscito a recuperare il meteo di oggi.")

            return {
                "status": "ok",
                "city": city,
                "date": datetime.now(timezone(timedelta(seconds=payload.get("timezone", 0)))).strftime("%Y-%m-%d"),
                "description": payload["weather"][0]["description"],
                "temperature_c": payload["main"]["temp"],
                "source": "current",
            }

        url = f"{base_url}forecast"
        response = requests.get(url, params={"q": city, "appid": config.app.weather_api_key, "units": units, "lang": lang}, timeout=15)
        response.raise_for_status()
        payload = response.json()

        if payload.get("cod") != "200":
            return _build_weather_error(city, date, "Non sono riuscito a recuperare le previsioni meteo.")

        city_timezone = timezone(timedelta(seconds=payload.get("city", {}).get("timezone", 0)))
        local_now = datetime.now(city_timezone)
        if date == "tomorrow":
            target_date = (local_now + timedelta(days=1)).date()
        elif date in WEEKDAY_MAP:
            target_date = next_weekday(local_now, date).date()
        else:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        forecasts = payload["list"]
        target_forecasts = [item for item in forecasts if datetime.fromtimestamp(item["dt"], city_timezone).date() == target_date]

        if not target_forecasts:
            return _build_weather_error(city, date, f"Non ho trovato informazioni meteo per la data {date}.")

        avg_temp = sum(item["main"]["temp"] for item in target_forecasts) / len(target_forecasts)
        return {
            "status": "ok",
            "city": city,
            "date": target_date.strftime("%Y-%m-%d"),
            "description": target_forecasts[0]["weather"][0]["description"],
            "temperature_c": round(avg_temp, 1),
            "source": "forecast",
        }
    except requests.RequestException as exc:
        logging.error("Weather request failed (%s)", type(exc).__name__)
        return _build_weather_error(city, date, "Si e verificato un errore di rete durante il recupero del meteo.")
    except (KeyError, ValueError, TypeError) as exc:
        logging.error("Weather response parsing failed (%s)", type(exc).__name__)
        return _build_weather_error(city, date, "Il servizio meteo ha restituito una risposta non valida.")
    except Exception as exc:
        logging.error("Unexpected weather error (%s)", type(exc).__name__)
        return _build_weather_error(city, date, "Si e verificato un errore imprevisto durante il recupero del meteo.")


def buildWeatherContext(request, report):
    return {
        "request_city": request.get("city"),
        "request_date": request.get("date"),
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
            f"Oggi a {report['city']} il meteo e {report['description']}, "
            f"con una temperatura di {report['temperature_c']} gradi C."
        )

    return (
        f"A {report['city']} il {report['date']} e previsto {report['description']}, "
        f"con una temperatura media di {report['temperature_c']} gradi C."
    )


def _build_weather_error(city, date, message):
    return {"status": "error", "city": city, "date": date, "message": message}


def _build_error_result(message):
    report = {"status": "error", "message": message}
    request = {"status": "error"}
    return {
        "request": request,
        "report": report,
        "context": buildWeatherContext(request, report),
        "message": message,
    }


def _normalize_text(value):
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_value.strip().lower()
