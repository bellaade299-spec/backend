import os
import uuid
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app.config["SECRET_KEY"] = "change-me-in-production"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'foundation.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "uploads")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db = SQLAlchemy(app)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}


# ── Models ────────────────────────────────────────────────────────────────────

class Admin(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)  # plain text; use hashing in production


class GalleryPhoto(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category    = db.Column(db.String(80))
    filename    = db.Column(db.String(200), nullable=False)
    is_featured = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)


# ── Helpers ───────────────────────────────────────────────────────────────────

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post("/api/login")
def login():
    data     = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password =  data.get("password") or ""

    if not username or not password:
        return jsonify({"ok": False, "message": "Username and password are required."}), 400

    admin = Admin.query.filter_by(username=username, password=password).first()
    if not admin:
        return jsonify({"ok": False, "message": "Invalid username or password."}), 401

    return jsonify({"ok": True, "message": "Login successful.", "admin_id": admin.id})


# ── Gallery ───────────────────────────────────────────────────────────────────

@app.post("/api/gallery")
def upload_photo():
    if "file" not in request.files:
        return jsonify({"ok": False, "message": "No file provided."}), 400

    file = request.files["file"]
    if not file.filename or not allowed_file(file.filename):
        return jsonify({"ok": False, "message": "Invalid file type. Use JPG, PNG, WEBP or GIF."}), 400

    title       = (request.form.get("title")       or "").strip()
    description = (request.form.get("description") or "").strip()

    if not title or not description:
        return jsonify({"ok": False, "message": "Title and description are required."}), 400

    ext      = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    photo = GalleryPhoto(
        title       = title,
        description = description,
        category    = (request.form.get("category") or "General").strip(),
        filename    = filename,
        is_featured = request.form.get("is_featured", "false").lower() == "true",
    )
    db.session.add(photo)
    db.session.commit()

    return jsonify({
        "ok":      True,
        "message": "Photo uploaded successfully.",
        "photo": {
            "id":          photo.id,
            "title":       photo.title,
            "description": photo.description,
            "category":    photo.category,
            "image_url":   f"/api/gallery/image/{photo.filename}",
            "is_featured": photo.is_featured,
            "created_at":  photo.created_at.isoformat(),
        }
    }), 201


@app.get("/api/gallery")
def list_photos():
    photos = GalleryPhoto.query.order_by(GalleryPhoto.created_at.desc()).all()
    return jsonify([{
        "id":          p.id,
        "title":       p.title,
        "description": p.description,
        "category":    p.category,
        "image_url":   f"/api/gallery/image/{p.filename}",
        "is_featured": p.is_featured,
        "created_at":  p.created_at.isoformat(),
    } for p in photos])

@app.delete("/api/gallery/<int:photo_id>")
def delete_photo(photo_id):
    photo = GalleryPhoto.query.get(photo_id)
    if not photo:
        return jsonify({"ok": False, "message": "Photo not found."}), 404

    # Delete the file from disk
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], photo.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    db.session.delete(photo)
    db.session.commit()

    return jsonify({"ok": True, "message": "Photo deleted successfully."})

@app.get("/api/debug/admins")
def debug_admins():
    admins = Admin.query.all()
    return jsonify([{"id": a.id, "username": a.username, "password": a.password} for a in admins])

@app.get("/api/gallery/image/<filename>")
def serve_image(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


# ── Init ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        if not Admin.query.first():
            db.session.add(Admin(username="admin", password="elias2025"))
            db.session.commit()
            print("Default admin created → username: admin  password: elias2025")
    app.run(debug=True, port=5000)