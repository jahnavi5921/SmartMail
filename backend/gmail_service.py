import os
import json
import base64
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly"
]

TOKEN_FILE = "token.json"


# =========================================================
# GMAIL SERVICE
# =========================================================

def get_gmail_service():
    if not os.path.exists(TOKEN_FILE):
        raise FileNotFoundError(
            "Gmail authorization token not found. "
            "Please authorize Gmail first."
        )

    with open(
        TOKEN_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        token_data = json.load(file)

    credentials = Credentials.from_authorized_user_info(
        token_data,
        SCOPES
    )

    return build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False
    )
def get_gmail_account_email():
    service = get_gmail_service()

    profile = (
        service.users()
        .getProfile(userId="me")
        .execute()
    )

    return profile["emailAddress"]

# =========================================================
# BASE64
# =========================================================

def decode_base64_text(data):

    if not data:
        return ""

    try:
        padding = "=" * (-len(data) % 4)

        return base64.urlsafe_b64decode(
            data + padding
        ).decode(
            "utf-8",
            errors="ignore"
        )

    except Exception:
        return ""


def decode_base64_bytes(data):

    if not data:
        return b""

    try:
        padding = "=" * (-len(data) % 4)

        return base64.urlsafe_b64decode(
            data + padding
        )

    except Exception:
        return b""


# =========================================================
# HTML CLEANING
# =========================================================

def clean_html(html):

    if not html:
        return ""

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    # Remove non-visible technical elements.
    for element in soup(
        [
            "script",
            "style",
            "head",
            "noscript"
        ]
    ):
        element.decompose()

    # Remove image elements so Gmail UI images
    # such as "[image: Google]" do not pollute
    # the email text.
    for image in soup.find_all("img"):
        image.decompose()

    # Preserve hyperlinks.
    #
    # Example:
    # <a href="https://example.com">Open</a>
    #
    # becomes:
    # Open (https://example.com)
    for link in soup.find_all("a"):

        href = (
            link.get("href")
            or ""
        ).strip()

        visible_text = link.get_text(
            " ",
            strip=True
        )

        if href and visible_text:

            link.replace_with(
                f"{visible_text} ({href})"
            )

        elif href:

            link.replace_with(href)

    text = soup.get_text(
        separator=" ",
        strip=True
    )

    # Normalize excessive whitespace.
    return " ".join(
        text.split()
    )


# =========================================================
# EMAIL BODY
# =========================================================

def extract_body(payload):

    plain_parts = []
    html_parts = []

    def process_part(part):

        mime_type = part.get(
            "mimeType",
            ""
        )

        filename = (
            part.get(
                "filename",
                ""
            )
            or ""
        ).strip()

        # Files are not body text.
        if filename:
            return

        body = part.get(
            "body",
            {}
        )

        data = body.get(
            "data"
        )

        if data:

            if mime_type == "text/plain":

                text = decode_base64_text(
                    data
                ).strip()

                if text:
                    plain_parts.append(
                        text
                    )

            elif mime_type == "text/html":

                html = decode_base64_text(
                    data
                )

                text = clean_html(
                    html
                )

                if text:
                    html_parts.append(
                        text
                    )

        # Gmail can nest MIME parts.
        for child in part.get(
            "parts",
            []
        ):
            process_part(child)

    process_part(payload)

    # Remove exact duplicates.
    plain_parts = list(
        dict.fromkeys(
            plain_parts
        )
    )

    html_parts = list(
        dict.fromkeys(
            html_parts
        )
    )

    # Prefer the actual plain-text version
    # whenever Gmail provides one.
    if plain_parts:
        return "\n\n".join(
            plain_parts
        )

    if html_parts:
        return "\n\n".join(
            html_parts
        )

    return ""


# =========================================================
# HEADER
# =========================================================

def get_header(
    headers,
    name
):

    for header in headers:

        if (
            header.get(
                "name",
                ""
            ).lower()
            == name.lower()
        ):

            return header.get(
                "value",
                ""
            )

    return ""


# =========================================================
# ATTACHMENT DETECTION
# =========================================================

def extract_attachments(payload):

    attachments = []

    def process_part(part):

        filename = (
            part.get(
                "filename",
                ""
            )
            or ""
        ).strip()

        mime_type = part.get(
            "mimeType",
            "application/octet-stream"
        )

        body = part.get(
            "body",
            {}
        )

        attachment_id = body.get(
            "attachmentId"
        )

        file_size = body.get(
            "size",
            0
        )

        direct_data = body.get(
            "data"
        )

        if filename:

            attachments.append({

                "filename": filename,

                "mime_type": mime_type,

                "gmail_attachment_id": (
                    attachment_id
                ),

                "file_size": (
                    file_size or 0
                ),

                "has_direct_data": (
                    bool(direct_data)
                )
            })

        for child in part.get(
            "parts",
            []
        ):
            process_part(child)

    process_part(payload)

    # Remove duplicate attachment entries.
    unique = []

    seen = set()

    for attachment in attachments:

        key = (
            attachment["filename"],
            attachment[
                "gmail_attachment_id"
            ]
        )

        if key not in seen:

            seen.add(key)

            unique.append(
                attachment
            )

    return unique


# =========================================================
# FIND ATTACHMENT PART
# =========================================================

def find_attachment_part(
    payload,
    filename,
    gmail_attachment_id=None
):

    found = None

    def process_part(part):

        nonlocal found

        if found is not None:
            return

        part_filename = (
            part.get(
                "filename",
                ""
            )
            or ""
        )

        body = part.get(
            "body",
            {}
        )

        part_attachment_id = body.get(
            "attachmentId"
        )

        if (
            part_filename == filename
            and (
                gmail_attachment_id is None
                or part_attachment_id
                == gmail_attachment_id
            )
        ):

            found = part
            return

        for child in part.get(
            "parts",
            []
        ):

            process_part(child)

    process_part(payload)

    return found


# =========================================================
# GET REAL ATTACHMENT DATA FROM GMAIL
# =========================================================

def get_gmail_attachment(
    message_id,
    attachment_id,
    filename
):

    service = get_gmail_service()

    message = service.users().messages().get(
        userId="me",
        id=message_id,
        format="full"
    ).execute()

    payload = message.get(
        "payload",
        {}
    )

    part = find_attachment_part(
        payload,
        filename,
        attachment_id
    )

    if part is None:

        raise FileNotFoundError(
            "Attachment was not found "
            "inside the Gmail message."
        )

    body = part.get(
        "body",
        {}
    )

    actual_attachment_id = body.get(
        "attachmentId"
    )

    # -----------------------------------------------------
    # NORMAL GMAIL ATTACHMENT
    # -----------------------------------------------------

    if actual_attachment_id:

        response = (
            service.users()
            .messages()
            .attachments()
            .get(
                userId="me",
                messageId=message_id,
                id=actual_attachment_id
            )
            .execute()
        )

        data = response.get(
            "data",
            ""
        )

        return decode_base64_bytes(
            data
        )

    # -----------------------------------------------------
    # DIRECT MIME DATA
    # -----------------------------------------------------

    direct_data = body.get(
        "data"
    )

    if direct_data:

        return decode_base64_bytes(
            direct_data
        )

    raise FileNotFoundError(
        "Attachment data is not available."
    )


# =========================================================
# GET GMAIL MESSAGES
# =========================================================

def get_gmail_messages(
    max_results=20
):

    service = get_gmail_service()

    response = service.users().messages().list(
        userId="me",
        maxResults=max_results
    ).execute()

    message_items = response.get(
        "messages",
        []
    )

    emails = []

    for item in message_items:

        message_id = item["id"]

        message = service.users().messages().get(
            userId="me",
            id=message_id,
            format="full"
        ).execute()

        payload = message.get(
            "payload",
            {}
        )

        headers = payload.get(
            "headers",
            []
        )

        sender = get_header(
            headers,
            "From"
        )

        subject = get_header(
            headers,
            "Subject"
        )

        date_header = get_header(
            headers,
            "Date"
        )

        # -------------------------------------------------
        # DATE
        # -------------------------------------------------

        try:

            received_at = (
                parsedate_to_datetime(
                    date_header
                ).isoformat()
            )

        except Exception:

            received_at = None

        # -------------------------------------------------
        # BODY
        # -------------------------------------------------

        body = extract_body(
            payload
        )

        if not body:

            body = "(No message body)"

        # -------------------------------------------------
        # ATTACHMENTS
        # -------------------------------------------------

        attachments = extract_attachments(
            payload
        )

        # -------------------------------------------------
        # GMAIL URL
        # -------------------------------------------------

        gmail_url = (
            "https://mail.google.com/mail/u/0/#all/"
            + message_id
        )

        emails.append({

            "gmail_id": message_id,

            "gmail_url": gmail_url,

            "sender": sender,

            "subject": (
                subject
                if subject
                else "(No subject)"
            ),

            "body": body,

            "received_at": received_at,

            "attachments": attachments
        })

    return emails