import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from atlas import weather


def _mock_chat_completion(content):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


class WeatherTests(unittest.TestCase):
    @patch("atlas.weather.config.get_groq_client")
    def test_extract_weather_info_normalizes_tomorrow(self, groq_client_mock):
        groq_client_mock.return_value.chat.completions.create.return_value = _mock_chat_completion(
            '{"city":"Rome","date":"tomorrow"}'
        )

        result = weather.extractWeatherInfo("Che meteo fa a Roma domani?")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["city"], "Rome")
        self.assertRegex(result["date"], r"\d{4}-\d{2}-\d{2}")

    @patch("atlas.weather.requests.get")
    @patch("atlas.weather.config.app.weather_api_key", "dummy-key")
    def test_get_weather_returns_error_on_network_failure(self, requests_get_mock):
        requests_get_mock.side_effect = Exception("boom")

        result = weather.getWeather("Rome", date="2026-03-25")

        self.assertEqual(result["status"], "error")
        self.assertIn("errore imprevisto", result["message"])

    def test_build_weather_message_for_forecast(self):
        message = weather.buildWeatherMessage(
            {
                "status": "ok",
                "source": "forecast",
                "city": "Rome",
                "date": "2026-03-25",
                "description": "sereno",
                "temperature_c": 20.5,
            }
        )

        self.assertIn("Rome", message)
        self.assertIn("2026-03-25", message)
        self.assertIn("20.5", message)


if __name__ == "__main__":
    unittest.main()
