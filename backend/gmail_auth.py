import os

from google_auth_oauthlib.flow import Flow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly"
]

CLIENT_SECRETS_FILE = next(
    file
    for file in os.listdir(".")
    if file.startswith("client_secret_") and file.endswith(".json")
)

REDIRECT_URI = "http://127.0.0.1:8000/auth/callback"


def create_flow():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
    )

    flow.redirect_uri = REDIRECT_URI

    return flow