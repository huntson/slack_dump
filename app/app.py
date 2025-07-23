import os
import threading
import uuid
import logging

from flask import Flask, render_template, request, jsonify, redirect, url_for
from sqlalchemy import text

from .db import db
from .models import Channel, Message, User
from .sync import run_sync, safe_call
from slack_sdk import WebClient

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

jobs = {}  # job_id -> progress dict

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    db_url = f"postgresql+psycopg://{os.getenv('DB_USER','slack')}:{os.getenv('DB_PASSWORD','slack')}@{os.getenv('DB_HOST','db')}:{os.getenv('DB_PORT','5432')}/{os.getenv('DB_NAME','slackdump')}"
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/channels")
    def channels():
        token = os.getenv("SLACK_TOKEN")
        types = os.getenv("SLACK_TYPES", "public_channel,private_channel")
        client = WebClient(token=token)
        chans = []
        cursor = None
        while True:
            resp = safe_call(client.conversations_list, cursor=cursor, limit=200, types=types)
            chans.extend(resp["channels"])
            cursor = resp["response_metadata"].get("next_cursor")
            if not cursor:
                break
        # mark selected if in DB already
        existing_ids = {c.id for c in Channel.query.all()}
        return render_template("channels.html", channels=chans, existing_ids=existing_ids)

    @app.route("/sync", methods=["POST"])
    def sync():
        ids = request.form.getlist("channel_id")
        job_id = str(uuid.uuid4())
        progress = {"phase": "starting", "users": 0, "messages": {}}
        jobs[job_id] = progress

        def worker():
            try:
                run_sync(ids, progress)
            except Exception as e:
                progress["phase"] = "error"
                progress["error"] = str(e)
                log.exception("sync failed")

        threading.Thread(target=worker, daemon=True).start()
        return redirect(url_for("job_status_page", job_id=job_id))

    @app.route("/job/<job_id>")
    def job_status_page(job_id):
        return render_template("job.html", job_id=job_id)

    @app.route("/api/job/<job_id>")
    def job_status_api(job_id):
        return jsonify(jobs.get(job_id, {"phase": "unknown"}))

    @app.route("/browse")
    def browse():
        channels = Channel.query.order_by(Channel.name.asc()).all()
        return render_template("browse.html", channels=channels)

    @app.route("/channel/<cid>")
    def channel_view(cid):
        page = int(request.args.get("page", 1))
        per_page = 100
        q = Message.query.filter_by(channel_id=cid).order_by(Message.ts.asc())
        items = q.paginate(page=page, per_page=per_page, error_out=False)
        # preload users map
        uids = {m.user_id for m in items.items if m.user_id}
        users = {u.id: u for u in User.query.filter(User.id.in_(uids)).all()}
        chan = Channel.query.get(cid)
        return render_template("channel.html", chan=chan, messages=items, users=users)

    @app.route("/search")
    def search():
        term = request.args.get("q", "").strip()
        page = int(request.args.get("page", 1))
        per_page = 100
        if not term:
            return render_template("search.html", messages=None, q=term)

        q = Message.query.filter(Message.text.ilike(f"%{term}%")).order_by(Message.ts.asc())
        items = q.paginate(page=page, per_page=per_page, error_out=False)
        uids = {m.user_id for m in items.items if m.user_id}
        users = {u.id: u for u in User.query.filter(User.id.in_(uids)).all()}
        return render_template("search.html", messages=items, q=term, users=users)

    return app

app = create_app()

if __name__ == "__main__":
    # Use waitress to serve
    from waitress import serve
    serve(app, host="0.0.0.0", port=8000)
