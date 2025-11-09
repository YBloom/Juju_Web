from sqlmodel import SQLModel, create_engine
from .models import User, Subscription


engine = create_engine("sqlite:///data/musicalbot.db", echo=False)


def init_db():
    SQLModel.metadata.create_all(engine)