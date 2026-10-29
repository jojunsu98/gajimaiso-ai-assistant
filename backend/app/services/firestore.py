"""Lazy Firebase Admin client for the default Firestore database."""

from threading import Lock

import firebase_admin
from firebase_admin import credentials, firestore

from app.config import FirebaseError, load_firebase_settings, validate_credentials

_APP_NAME = "gajimaiso-firestore"
_lock = Lock()
_client = None


def get_firestore_client():
    """Initialize once on demand; settings remain fixed for this process lifetime."""
    global _client
    with _lock:
        if _client is not None:
            return _client

        settings = load_firebase_settings()
        info = validate_credentials(settings)
        try:
            # Parse the selected credential; never adopt another app's credentials.
            certificate = credentials.Certificate(info)
            try:
                existing_app = firebase_admin.get_app(_APP_NAME)
            except ValueError:
                app = firebase_admin.initialize_app(
                    certificate,
                    {"projectId": settings.project_id},
                    name=_APP_NAME,
                )
            else:
                if existing_app.project_id != settings.project_id:
                    raise FirebaseError("initialization_project_mismatch")
                raise FirebaseError("initialization_conflict")
            if app.project_id != settings.project_id:
                raise FirebaseError("initialization_project_mismatch")
            client = firestore.client(app=app, database_id="(default)")
        except FirebaseError:
            raise
        except Exception:
            raise FirebaseError("initialization_failed") from None
        finally:
            # Do not retain the parsed private JSON in a module-level cache.
            del info
        _client = client
        return _client
