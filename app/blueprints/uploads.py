"""Image uploads and serving.

  GET  /uploads/<filename>            serve any uploaded image
  POST /api/upload/avatar             the caller's profile picture
  POST /api/upload/event/<event_id>   event banner   (promoter, admin)
  POST /api/upload/gym/<gym_id>       gym photo      (owning coach, admin)

Files are stored under a random name by services/storage.py (local disk or
Cloud Storage); the database holds only that name.
"""

import uuid
from flask import Blueprint, jsonify, request, current_app
from ..helpers import err, login_required, roles_required, subscription_required, current_user
from ..extensions import db, limiter
from ..models.event import Event
from ..models.gym import Gym
from ..services.storage import get_storage

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

uploads_bp = Blueprint("uploads", __name__)


def _allowed(filename: str) -> bool:
    """Does the filename have an allowed image extension?"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _save_upload(file_key: str = 'file') -> tuple:
    """Store the uploaded file under a random name.

    Returns (filename, None) on success or (None, error_message).
    """
    f = request.files.get(file_key)
    if not f or not f.filename:
        return None, "No file provided."
    if not _allowed(f.filename):
        return None, "Only image files are allowed (PNG, JPG, WEBP, GIF)."
    ext = f.filename.rsplit('.', 1)[1].lower()
    filename = uuid.uuid4().hex + '.' + ext
    try:
        get_storage().save(f, filename)
    except Exception as exc:                      # bucket missing, no credentials, …
        current_app.logger.exception("upload failed")
        return None, f"Could not store the file: {exc}"
    return filename, None


@uploads_bp.route("/uploads/<path:filename>")
def serve_upload(filename):
    """Canonical URL for every uploaded image, whatever the backend.

    The frontend hardcodes /uploads/<filename> in image tags and CSS
    background-image rules, so this path stays stable and the backend decides
    whether to read from disk, stream from a bucket, or redirect.
    """
    if "/" in filename or "\\" in filename:
        return err("Not found.", 404)
    return get_storage().send(filename)


@uploads_bp.route("/api/upload/avatar", methods=["POST"])
@login_required
@limiter.limit("10 per hour")   # each upload is up to 5 MB of billed storage
def upload_avatar():
    """Set the caller's profile picture."""
    filename, error = _save_upload()
    if error:
        return err(error)
    user = current_user()
    updated = current_app.auth_db.update_profile_picture(user["id"], filename)
    return jsonify({"user": updated, "url": f"/uploads/{filename}"})


@uploads_bp.route("/api/upload/event/<int:event_id>", methods=["POST"])
@roles_required("promoter", "admin")
@subscription_required
def upload_event_photo(event_id):
    """Set an event's banner image."""
    # Check the target exists BEFORE storing, so refused requests leave no
    # orphaned files.
    event = db.session.get(Event, event_id)
    if not event:
        return err("Event not found.", 404)
    filename, error = _save_upload()
    if error:
        return err(error)
    event.photo = filename
    db.session.commit()
    return jsonify({"event": event.to_dict(), "url": f"/uploads/{filename}"})


@uploads_bp.route("/api/upload/gym/<int:gym_id>", methods=["POST"])
@roles_required("coach", "admin")
@subscription_required
def upload_gym_photo(gym_id):
    """Set a gym's photo (owning coach or admin)."""
    # Authorise BEFORE storing, so refused requests leave no orphaned files.
    gym = db.session.get(Gym, gym_id)
    if not gym:
        return err("Gym not found.", 404)
    user = current_user()
    if user["role"] != "admin" and gym.coach_id != user["id"]:
        return err("You can only update your own gym's photo.", 403)

    filename, error = _save_upload()
    if error:
        return err(error)
    gym.photo = filename
    db.session.commit()
    return jsonify({"gym": gym.to_dict(), "url": f"/uploads/{filename}"})
