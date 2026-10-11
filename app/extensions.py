"""
Flask Extensions
----------------
Instantiated here (without app binding) so they can be imported
anywhere without circular imports. Bound to the app in create_app().
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_apscheduler import APScheduler

db = SQLAlchemy()
login_manager = LoginManager()
scheduler = APScheduler()
