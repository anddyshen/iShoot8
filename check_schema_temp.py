from app import app, db
from sqlalchemy import inspect

with app.app_context():
    i = inspect(db.engine)
    print('ssq_draws columns:', [c['name'] for c in i.get_columns('ssq_draws')])
    print('dlt_draws columns:', [c['name'] for c in i.get_columns('dlt_draws')])
