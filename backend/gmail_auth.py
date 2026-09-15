import os
import json
from google_auth_oauthlib.flow import Flow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly"
]

LOCAL_REDIRECT_URI = "http://127.0.0.1:8000/auth/callback"

def get_redirect_uri():
    return os.getenv(
        "GOOGLE_REDIRECT_URI",
        LOCAL_REDIRECT_URI
    )

def create_flow():
    client_config = os.getenv("GOOGLE_CLIENT_CONFIG")

    if client_config:
        client_config_dict = json.loads(client_config)

        flow = Flow.from_client_config(
            client_config_dict,
            scopes=SCOPES,
        )
    else:
        client_secrets_file = next(
            file
            for file in os.listdir(".")
            if file.startswith("client_secret_")
            and file.endswith(".json")
        )

        flow = Flow.from_client_secrets_file(
            client_secrets_file,
            scopes=SCOPES,
        )

    flow.redirect_uri = get_redirect_uri()

    return flow