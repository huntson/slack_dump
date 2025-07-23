from .db import db

class Channel(db.Model):
    __tablename__ = "channels"
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, nullable=False)
    is_private = db.Column(db.Boolean, nullable=False, default=False)
    created = db.Column(db.DateTime, nullable=True)

    messages = db.relationship("Message", back_populates="channel", lazy="dynamic")

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, nullable=False)
    real_name = db.Column(db.String, nullable=True)
    tz = db.Column(db.String, nullable=True)

    messages = db.relationship("Message", back_populates="user", lazy="dynamic")
    reactions = db.relationship("Reaction", back_populates="user", lazy="dynamic")

class Message(db.Model):
    __tablename__ = "messages"
    ts = db.Column(db.String, primary_key=True)
    channel_id = db.Column(db.String, db.ForeignKey("channels.id"), nullable=False)
    user_id = db.Column(db.String, db.ForeignKey("users.id"), nullable=True)
    text = db.Column(db.Text, nullable=True)
    thread_ts = db.Column(db.String, nullable=True)
    parent_user_id = db.Column(db.String, nullable=True)
    subtype = db.Column(db.String, nullable=True)

    channel = db.relationship("Channel", back_populates="messages")
    user = db.relationship("User", back_populates="messages")
    reactions = db.relationship("Reaction", back_populates="message", lazy="dynamic")

class Reaction(db.Model):
    __tablename__ = "reactions"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    message_ts = db.Column(db.String, db.ForeignKey("messages.ts"), nullable=False)
    name = db.Column(db.String, nullable=False)
    count = db.Column(db.Integer, nullable=False, default=0)
    user_id = db.Column(db.String, db.ForeignKey("users.id"), nullable=True)

    message = db.relationship("Message", back_populates="reactions")
    user = db.relationship("User", back_populates="reactions")
