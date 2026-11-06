import logging
from logging.handlers import RotatingFileHandler
from atlas.logging_utils import RedactingFormatter
import sys

import atlas


def configure_logging():
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        handler.close()

    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=logging.INFO,
        handlers=[
            RotatingFileHandler(
                atlas.config.app.log_path,
                maxBytes=2_000_000,
                backupCount=3,
                encoding="utf-8",
            ),
            logging.StreamHandler(),
        ],
    )

    formatter = RedactingFormatter("%(asctime)s - %(levelname)s - %(message)s")
    for handler in logging.root.handlers:
        handler.setFormatter(formatter)
    for name in ("httpx", "httpx2", "httpcore", "google_genai"):
        logging.getLogger(name).setLevel(logging.WARNING)


if __name__ == "__main__":
    configure_logging()
    atlas.config.validate_config()
    if "--gui" in sys.argv:
        atlas.run_gui()
    else:
        atlas.run()
