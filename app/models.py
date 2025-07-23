from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, ForeignKey
from sqlalchemy.orm import relationship
from .db import Base

class Channel(Base):
    __tablename__ = "channels"
    id = Column(String, primary_key=True)  # Slack channel id
    name = Column(String, nullable=False)
    is_private = Column(Boolean, nullable=False, default=False)
    created = Column(DateTime, nullable=True)

    messages = relationship("Message", back_populates="channel")

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)  # Slack user id
    name = Column(String, nullable=False)
    real_name = Column(String, nullable=True)
    tz = Column(String, nullable=True)

    messages = relationship("Message", back_populates="user")
    reactions = relationship("Reaction", back_populates="user")

class Message(Base):
    __tablename__ = "messages"
    ts = Column(String, primary_key=True)  # Slack ts as string
    channel_id = Column(String, ForeignKey("channels.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    text = Column(Text, nullable=True)
    thread_ts = Column(String, nullable=True)
    parent_user_id = Column(String, nullable=True)
    subtype = Column(String, nullable=True)

    channel = relationship("Channel", back_populates="messages")
    user = relationship("User", back_populates="messages")
    reactions = relationship("Reaction", back_populates="message")

class Reaction(Base):
    __tablename__ = "reactions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_ts = Column(String, ForeignKey("messages.ts"), nullable=False)
    name = Column(String, nullable=False)
    count = Column(Integer, nullable=False, default=0)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)

    message = relationship("Message", back_populates="reactions")
    user = relationship("User", back_populates="reactions")
