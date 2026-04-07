from app import create_app
from data_manager import update_latest_draws
import logging

# Configure basic logging to see output
logging.basicConfig(level=logging.INFO)

app = create_app()

with app.app_context():
    logging.info("Calling update_latest_draws...")
    ssq_count, dlt_count = update_latest_draws(app)
    logging.info(f"Data update completed. SSQ added: {ssq_count}, DLT added: {dlt_count}")
