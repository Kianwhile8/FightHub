"""Upload storage — local disk or Google Cloud Storage.

Cloud Run's filesystem is ephemeral and per-instance: anything written to disk
disappears on the next deploy and is invisible to every other instance. Avatars
and photos therefore go to object storage in production, while local disk stays
the default for development and for a VM with a persistent disk.

Both backends are addressed identically. The database stores a bare filename,
and the app serves it from /uploads/<filename> — the frontend builds that URL in
six places, including CSS background-image rules, so it must not change when the
backend does.
"""

import os
from flask import current_app, send_from_directory, redirect, Response, abort


class LocalStorage:
    """Files on the local filesystem."""

    name = "local"

    def __init__(self, root: str):
        self.root = root
        os.makedirs(self.root, exist_ok=True)

    def save(self, file_obj, filename: str) -> None:
        file_obj.save(os.path.join(self.root, filename))

    def send(self, filename: str):
        return send_from_directory(self.root, filename)

    def delete(self, filename: str) -> None:
        try:
            os.remove(os.path.join(self.root, filename))
        except FileNotFoundError:
            pass

    def describe(self) -> str:
        return f"local disk ({self.root})"


class GCSStorage:
    """Files in a Google Cloud Storage bucket.

    By default the object is streamed back through the app rather than redirected
    to. That needs nothing more than `roles/storage.objectAdmin` on the service
    account — no public bucket, no URL signing, no extra IAM. The cost is that
    image bytes travel through Cloud Run instead of straight from the bucket.

    Set GCS_PUBLIC_URLS=1 once egress matters: the app then 302s to the object's
    public URL, which requires the bucket's objects to be publicly readable.
    Filenames are random UUIDs, but public means public — anyone holding the URL
    can fetch it without logging in.
    """

    name = "gcs"

    def __init__(self, bucket_name: str, prefix: str = "uploads/",
                 public_urls: bool = False, cache_seconds: int = 3600):
        try:
            # Imported lazily: only production needs it, and a local checkout
            # without the package should still run with STORAGE_BACKEND=local.
            from google.cloud import storage as gcs
        except ImportError as exc:
            raise RuntimeError(
                "STORAGE_BACKEND=gcs needs the google-cloud-storage package — "
                "install it with: pip install -r requirements"
            ) from exc
        if not bucket_name:
            raise RuntimeError(
                "STORAGE_BACKEND=gcs requires GCS_BUCKET to be set."
            )
        self._bucket       = gcs.Client().bucket(bucket_name)
        self.bucket_name   = bucket_name
        self.prefix        = prefix or ""
        self.public_urls   = public_urls
        self.cache_seconds = cache_seconds

    def _blob(self, filename: str):
        return self._bucket.blob(f"{self.prefix}{filename}")

    def save(self, file_obj, filename: str) -> None:
        stream = file_obj.stream
        stream.seek(0)
        self._blob(filename).upload_from_file(
            stream, content_type=file_obj.mimetype or "application/octet-stream"
        )

    def send(self, filename: str):
        blob = self._blob(filename)
        if self.public_urls:
            return redirect(blob.public_url, code=302)
        if not blob.exists():
            abort(404)
        blob.reload()
        return Response(
            blob.download_as_bytes(),
            mimetype=blob.content_type or "application/octet-stream",
            headers={"Cache-Control": f"public, max-age={self.cache_seconds}"},
        )

    def delete(self, filename: str) -> None:
        blob = self._blob(filename)
        if blob.exists():
            blob.delete()

    def describe(self) -> str:
        mode = "public URLs" if self.public_urls else "streamed through the app"
        return f"gs://{self.bucket_name}/{self.prefix} ({mode})"


def _build(app):
    backend = (app.config.get("STORAGE_BACKEND") or "local").strip().lower()
    if backend == "gcs":
        return GCSStorage(
            bucket_name=app.config.get("GCS_BUCKET"),
            prefix=app.config.get("GCS_PREFIX", "uploads/"),
            public_urls=app.config.get("GCS_PUBLIC_URLS", False),
        )
    if backend == "local":
        return LocalStorage(app.config["UPLOAD_FOLDER"])
    raise RuntimeError(
        f"Unknown STORAGE_BACKEND '{backend}'. Use 'local' or 'gcs'."
    )


def get_storage():
    """The configured backend, built once per app.

    Built lazily rather than at startup so a misconfigured bucket surfaces on the
    first upload with a clear error, instead of stopping the whole app from
    booting — health checks and every other route stay up.
    """
    store = current_app.extensions.get("fighthub_storage")
    if store is None:
        store = _build(current_app)
        current_app.extensions["fighthub_storage"] = store
    return store
