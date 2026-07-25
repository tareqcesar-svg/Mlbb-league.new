import os
from flask import Flask
from pymongo import MongoClient


def create_app():
    app = Flask(__name__)

    mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    client = MongoClient(mongo_uri)
    db = client[os.environ.get("MONGO_DB_NAME", "mlbb_league")]

    # make db accessible everywhere via app config
    app.config["DB"] = db

    from app.routes import bp as main_bp
    app.register_blueprint(main_bp)

    return app
