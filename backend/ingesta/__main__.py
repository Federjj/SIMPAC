"""python -m backend.ingesta: una corrida suelta de la ingesta."""
import logging

from backend.ingesta import run

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
run()
