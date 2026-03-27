import logging
import sys

import atlas


def configure_logging():
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=logging.INFO,
        handlers=[
            logging.FileHandler(atlas.config.app.log_path),
            logging.StreamHandler(),
        ],
    )


if __name__ == "__main__":
    configure_logging()
    atlas.config.validate_config()
    if "--gui" in sys.argv:
        atlas.run_gui()
    else:
        atlas.run()
