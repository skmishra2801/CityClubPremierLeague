import os
from dotenv import load_dotenv


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}"
        f"@{os.getenv('MYSQL_HOST')}:{os.getenv('MYSQL_PORT')}/{os.getenv('MYSQL_DB')}"
    )

    # SQLALCHEMY_DATABASE_URI = (
    #     "mysql+pymysql://avnadmin:AVNS_m3B8hIbb_zFmshELa10@mysql-1c9fb5e6-skmishra2801-3a55-cpl.i.aivencloud.com:10985/CPL"
    # )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")
    PER_PAGE = 10
