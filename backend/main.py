import os
from datetime import datetime
from urllib.parse import quote

from dotenv import load_dotenv

from fastapi import (
    FastAPI,
    HTTPException,
    Request
)

from fastapi.middleware.cors import CORSMiddleware

from fastapi.responses import (
    RedirectResponse,
    StreamingResponse
)

from sqlalchemy import text

from sqlalchemy.ext.asyncio import (
    create_async_engine
)

from starlette.middleware.sessions import (
    SessionMiddleware
)

from models import (
    User,
    Rule,
    Email,
    Attachment
)

from gmail_auth import create_flow

from gmail_service import (
    get_gmail_messages,
    get_gmail_attachment,
    get_gmail_account_email
)


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL"
)

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is missing from .env"
    )

DATABASE_URL = DATABASE_URL.replace(
    "postgresql://",
    "postgresql+asyncpg://",
    1
)


# =========================================================
# DATABASE
# =========================================================

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True
)


# =========================================================
# FASTAPI
# =========================================================

app = FastAPI(
    title="SmartMail API",
    version="1.0.0",
    description=(
        "Cloud-Based Personalized "
        "Email Prioritization System"
    )
)


# =========================================================
# SESSION
# =========================================================

SESSION_SECRET = os.getenv(
    "SESSION_SECRET"
)

if not SESSION_SECRET:
    SESSION_SECRET = (
        "smartmail-development-secret"
    )

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET
)


# Server-side OAuth state and PKCE verifier storage.
oauth_pending = {}


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=[
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://smartmail-frontend-r0s5.onrender.com"
],
    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"]
)


# =========================================================
# USER
# =========================================================

async def get_default_user_id():

    async with engine.begin() as connection:

        result = await connection.execute(
            text("""
                SELECT id
                FROM users
                WHERE id = 1
                LIMIT 1
            """)
        )

        row = result.first()

        if row is not None:
            return row[0]

        result = await connection.execute(
            text("""
                SELECT id
                FROM users
                ORDER BY id
                LIMIT 1
            """)
        )

        row = result.first()

        if row is not None:
            return row[0]

        result = await connection.execute(
            text("""
                INSERT INTO users
                    (
                        email,
                        name,
                        created_at
                    )
                VALUES
                    (
                        :email,
                        :name,
                        now()
                    )
                RETURNING id
            """),
            {
                "email": "smartmail-local-user",
                "name": "SmartMail User"
            }
        )

        return result.scalar_one()


# =========================================================
# BASIC ROUTES
# =========================================================

@app.get("/")
async def root():

    return {
        "application": "SmartMail",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/api/health")
async def health():

    return {
        "status": "healthy"
    }


@app.get("/api/database-test")
async def database_test():

    async with engine.connect() as connection:

        result = await connection.execute(
            text("SELECT 1")
        )

        value = result.scalar_one()

    return {
        "database": "connected",
        "test_result": value
    }


# =========================================================
# RULES - READ
# =========================================================

@app.get("/api/rules")
async def get_rules():

    user_id = await get_default_user_id()

    async with engine.connect() as connection:

        result = await connection.execute(
            text("""
                SELECT
                    id,
                    user_id,
                    rule_type,
                    rule_value,
                    created_at,
                    updated_at
                FROM rules
                WHERE user_id = :user_id
                ORDER BY id DESC
            """),
            {
                "user_id": user_id
            }
        )

        rows = result.mappings().all()

    return {
        "rules": [
            dict(row)
            for row in rows
        ]
    }


# =========================================================
# RULES - CREATE
# =========================================================

@app.post("/api/rules")
async def create_rule(
    rule_type: str,
    rule_value: str
):

    user_id = await get_default_user_id()

    rule_type = (
        rule_type
        .strip()
        .lower()
    )

    rule_value = (
        rule_value
        .strip()
    )

    if rule_type not in {
        "keyword",
        "sender"
    }:

        raise HTTPException(
            status_code=400,
            detail=(
                "Rule type must be "
                "keyword or sender."
            )
        )

    if not rule_value:

        raise HTTPException(
            status_code=400,
            detail=(
                "Rule value cannot be empty."
            )
        )

    async with engine.begin() as connection:

        result = await connection.execute(
            text("""
                INSERT INTO rules
                    (
                        user_id,
                        rule_type,
                        rule_value,
                        created_at,
                        updated_at
                    )
                VALUES
                    (
                        :user_id,
                        :rule_type,
                        :rule_value,
                        now(),
                        now()
                    )
                RETURNING
                    id,
                    user_id,
                    rule_type,
                    rule_value,
                    created_at,
                    updated_at
            """),
            {
                "user_id": user_id,
                "rule_type": rule_type,
                "rule_value": rule_value
            }
        )

        row = result.mappings().one()

    return dict(row)


# =========================================================
# RULES - UPDATE
# =========================================================

@app.put("/api/rules/{rule_id}")
async def update_rule(
    rule_id: int,
    rule_type: str,
    rule_value: str
):

    user_id = await get_default_user_id()

    rule_type = (
        rule_type
        .strip()
        .lower()
    )

    rule_value = (
        rule_value
        .strip()
    )

    if rule_type not in {
        "keyword",
        "sender"
    }:

        raise HTTPException(
            status_code=400,
            detail=(
                "Rule type must be "
                "keyword or sender."
            )
        )

    if not rule_value:

        raise HTTPException(
            status_code=400,
            detail=(
                "Rule value cannot be empty."
            )
        )

    async with engine.begin() as connection:

        result = await connection.execute(
            text("""
                UPDATE rules
                SET
                    rule_type = :rule_type,
                    rule_value = :rule_value,
                    updated_at = now()
                WHERE
                    id = :rule_id
                    AND user_id = :user_id
                RETURNING
                    id,
                    user_id,
                    rule_type,
                    rule_value,
                    created_at,
                    updated_at
            """),
            {
                "rule_id": rule_id,
                "user_id": user_id,
                "rule_type": rule_type,
                "rule_value": rule_value
            }
        )

        row = result.mappings().first()

    if row is None:

        raise HTTPException(
            status_code=404,
            detail="Rule not found."
        )

    return dict(row)


# =========================================================
# RULES - DELETE
# =========================================================

@app.delete("/api/rules/{rule_id}")
async def delete_rule(
    rule_id: int
):

    user_id = await get_default_user_id()

    async with engine.begin() as connection:

        result = await connection.execute(
            text("""
                DELETE FROM rules
                WHERE
                    id = :rule_id
                    AND user_id = :user_id
                RETURNING id
            """),
            {
                "rule_id": rule_id,
                "user_id": user_id
            }
        )

        row = result.first()

    if row is None:

        raise HTTPException(
            status_code=404,
            detail="Rule not found."
        )

    return {
        "message": (
            "Rule deleted successfully"
        ),
        "id": row[0]
    }


# =========================================================
# EMAILS - READ
# =========================================================

@app.get("/api/emails")
async def get_emails():

    user_id = await get_default_user_id()

    gmail_account_email = (
        get_gmail_account_email()
    )

    async with engine.connect() as connection:

        result = await connection.execute(
            text("""
                SELECT
                    id,
                    user_id,
                    sender,
                    subject,
                    body,
                    received_at,
                    gmail_id,
                    created_at
                FROM emails
                WHERE user_id = :user_id
                ORDER BY received_at DESC
            """),
            {
                "user_id": user_id
            }
        )

        email_rows = (
            result
            .mappings()
            .all()
        )

        attachment_result = await connection.execute(
            text("""
                SELECT
                    a.id,
                    a.email_id,
                    a.filename,
                    a.mime_type,
                    a.file_size,
                    a.gmail_attachment_id
                FROM attachments a
                INNER JOIN emails e
                    ON e.id = a.email_id
                WHERE e.user_id = :user_id
                ORDER BY a.id
            """),
            {
                "user_id": user_id
            }
        )

        attachment_rows = (
            attachment_result
            .mappings()
            .all()
        )

    attachments_by_email = {}

    for attachment in attachment_rows:

        email_id = attachment[
            "email_id"
        ]

        attachments_by_email.setdefault(
            email_id,
            []
        ).append({

            "id": attachment[
                "id"
            ],

            "filename": attachment[
                "filename"
            ],

            "mime_type": attachment[
                "mime_type"
            ],

            "file_size": attachment[
                "file_size"
            ],

            "download_url": (
                "/api/attachments/"
                f"{attachment['id']}"
            )
        })

    emails = []

    for row in email_rows:

        email = dict(row)

        gmail_id = email[
            "gmail_id"
        ]

        email["gmail_url"] = (
            "https://mail.google.com/mail/"
            f"?authuser={quote(gmail_account_email)}"
            f"#all/{gmail_id}"
        )

        email["attachments"] = (
            attachments_by_email.get(
                email["id"],
                []
            )
        )

        emails.append(
            email
        )

    return {
        "emails": emails
    }


# =========================================================
# EMAILS - CREATE
# =========================================================

@app.post("/api/emails")
async def create_email(
    sender: str,
    subject: str,
    body: str,
    received_at: str,
    gmail_id: str
):

    user_id = await get_default_user_id()

    try:

        parsed_received_at = (
            datetime.fromisoformat(
                received_at
            )
        )

    except ValueError:

        raise HTTPException(
            status_code=400,
            detail=(
                "received_at must be a valid "
                "ISO datetime."
            )
        )

    async with engine.begin() as connection:

        result = await connection.execute(
            text("""
                INSERT INTO emails
                    (
                        user_id,
                        sender,
                        subject,
                        body,
                        received_at,
                        gmail_id,
                        created_at
                    )
                VALUES
                    (
                        :user_id,
                        :sender,
                        :subject,
                        :body,
                        :received_at,
                        :gmail_id,
                        now()
                    )
                RETURNING
                    id,
                    user_id,
                    sender,
                    subject,
                    body,
                    received_at,
                    gmail_id,
                    created_at
            """),
            {
                "user_id": user_id,
                "sender": sender,
                "subject": subject,
                "body": body,
                "received_at": parsed_received_at,
                "gmail_id": gmail_id
            }
        )

        row = result.mappings().one()

    return dict(row)


# =========================================================
# ATTACHMENT - OPEN / DOWNLOAD
# =========================================================

@app.get(
    "/api/attachments/{attachment_id}"
)
async def download_attachment(
    attachment_id: int
):

    user_id = await get_default_user_id()

    async with engine.connect() as connection:

        result = await connection.execute(
            text("""
                SELECT
                    a.id,
                    a.email_id,
                    a.filename,
                    a.mime_type,
                    a.gmail_attachment_id,
                    e.gmail_id
                FROM attachments a
                INNER JOIN emails e
                    ON e.id = a.email_id
                WHERE
                    a.id = :attachment_id
                    AND e.user_id = :user_id
            """),
            {
                "attachment_id": attachment_id,
                "user_id": user_id
            }
        )

        attachment = (
            result
            .mappings()
            .first()
        )

    if attachment is None:

        raise HTTPException(
            status_code=404,
            detail="Attachment not found."
        )

    try:

        data = get_gmail_attachment(
            message_id=attachment[
                "gmail_id"
            ],

            attachment_id=attachment[
                "gmail_attachment_id"
            ],

            filename=attachment[
                "filename"
            ]
        )

    except FileNotFoundError as error:

        raise HTTPException(
            status_code=404,
            detail=str(error)
        )

    except Exception as error:

        raise HTTPException(
            status_code=502,
            detail=(
                "Unable to retrieve "
                "the Gmail attachment."
            )
        ) from error

    if not data:

        raise HTTPException(
            status_code=404,
            detail=(
                "Attachment contains no data."
            )
        )

    filename = (
        attachment["filename"]
    )

    safe_filename = (
        filename
        .replace("\\", "_")
        .replace('"', "_")
        .replace("\r", "_")
        .replace("\n", "_")
    )

    mime_type = (
        attachment["mime_type"]
        or "application/octet-stream"
    )

    inline_types = {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/svg+xml",
        "text/plain"
    }

    disposition = (
        "inline"
        if mime_type in inline_types
        else "attachment"
    )

    return StreamingResponse(
        iter([data]),

        media_type=mime_type,

        headers={
            "Content-Disposition": (
                f'{disposition}; '
                f'filename="{safe_filename}"'
            ),

            "Content-Length": str(
                len(data)
            )
        }
    )


# =========================================================
# GMAIL SYNC
# =========================================================

@app.post("/api/gmail/sync")
async def sync_gmail():

    user_id = await get_default_user_id()

    try:

        gmail_emails = get_gmail_messages(
            max_results=20
        )

    except FileNotFoundError as error:

        raise HTTPException(
            status_code=401,
            detail=str(error)
        )

    except Exception as error:

        raise HTTPException(
            status_code=502,
            detail=(
                "Unable to read Gmail."
            )
        ) from error

    saved_count = 0
    updated_count = 0
    attachment_count = 0

    async with engine.begin() as connection:

        for email in gmail_emails:

            received_at = None

            if email.get(
                "received_at"
            ):

                try:

                    received_at = (
                        datetime.fromisoformat(
                            email[
                                "received_at"
                            ]
                        )
                    )

                except ValueError:

                    received_at = None

            existing_result = (
                await connection.execute(
                    text("""
                        SELECT id
                        FROM emails
                        WHERE
                            gmail_id = :gmail_id
                            AND user_id = :user_id
                    """),
                    {
                        "gmail_id": email[
                            "gmail_id"
                        ],

                        "user_id": user_id
                    }
                )
            )

            existing_email = (
                existing_result.first()
            )

            if existing_email is not None:

                email_id = (
                    existing_email[0]
                )

                await connection.execute(
                    text("""
                        UPDATE emails
                        SET
                            sender = :sender,
                            subject = :subject,
                            body = :body,
                            received_at = COALESCE(
                                :received_at,
                                received_at
                            )
                        WHERE id = :email_id
                    """),
                    {
                        "sender": email[
                            "sender"
                        ],

                        "subject": email[
                            "subject"
                        ],

                        "body": email[
                            "body"
                        ],

                        "received_at": (
                            received_at
                        ),

                        "email_id": email_id
                    }
                )

                await connection.execute(
                    text("""
                        DELETE FROM attachments
                        WHERE email_id = :email_id
                    """),
                    {
                        "email_id": email_id
                    }
                )

                updated_count += 1

            else:

                result = await connection.execute(
                    text("""
                        INSERT INTO emails
                            (
                                user_id,
                                sender,
                                subject,
                                body,
                                received_at,
                                gmail_id,
                                created_at
                            )
                        VALUES
                            (
                                :user_id,
                                :sender,
                                :subject,
                                :body,
                                COALESCE(
                                    :received_at,
                                    now()
                                ),
                                :gmail_id,
                                now()
                            )
                        RETURNING id
                    """),
                    {
                        "user_id": user_id,

                        "sender": email[
                            "sender"
                        ],

                        "subject": email[
                            "subject"
                        ],

                        "body": email[
                            "body"
                        ],

                        "received_at": (
                            received_at
                        ),

                        "gmail_id": email[
                            "gmail_id"
                        ]
                    }
                )

                email_id = (
                    result.scalar_one()
                )

                saved_count += 1

            for attachment in email.get(
                "attachments",
                []
            ):

                await connection.execute(
                    text("""
                        INSERT INTO attachments
                            (
                                email_id,
                                gmail_attachment_id,
                                filename,
                                mime_type,
                                file_size,
                                created_at
                            )
                        VALUES
                            (
                                :email_id,
                                :gmail_attachment_id,
                                :filename,
                                :mime_type,
                                :file_size,
                                now()
                            )
                    """),
                    {
                        "email_id": email_id,

                        "gmail_attachment_id": (
                            attachment.get(
                                "gmail_attachment_id"
                            )
                        ),

                        "filename": attachment[
                            "filename"
                        ],

                        "mime_type": attachment[
                            "mime_type"
                        ],

                        "file_size": attachment.get(
                            "file_size",
                            0
                        )
                    }
                )

                attachment_count += 1

    return {
        "message": (
            "Gmail sync completed successfully"
        ),

        "gmail_emails_found": len(
            gmail_emails
        ),

        "new_emails_saved": (
            saved_count
        ),

        "existing_emails_updated": (
            updated_count
        ),

        "attachments_found": (
            attachment_count
        )
    }


# =========================================================
# GMAIL OAUTH LOGIN
# =========================================================

@app.get("/auth/login")
def gmail_login(
    request: Request
):

    flow = create_flow()

    authorization_url, state = (
        flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="select_account consent"
        )
    )

    # Keep OAuth state on the server instead of relying on
    # the browser session cookie during Google's redirect.
    oauth_pending[state] = flow.code_verifier

    return RedirectResponse(
        authorization_url
    )


# =========================================================
# GMAIL OAUTH CALLBACK
# =========================================================

@app.get("/auth/callback")
async def gmail_callback(
    request: Request,
    code: str,
    state: str
):

    # Get and consume the exact state created by /auth/login.
    saved_code_verifier = oauth_pending.pop(
        state,
        None
    )

    if not saved_code_verifier:

        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid or expired OAuth state. "
                "Please click Connect Gmail and try again."
            )
        )

    flow = create_flow()

    flow.code_verifier = (
        saved_code_verifier
    )

    try:

        flow.fetch_token(
            code=code
        )

    except Exception as error:

        raise HTTPException(
            status_code=400,
            detail=(
                "Gmail authorization failed. "
                "Please click Connect Gmail and try again."
            )
        ) from error

    credentials = flow.credentials

    with open(
        "token.json",
        "w",
        encoding="utf-8"
    ) as token_file:

        token_file.write(
            credentials.to_json()
        )

    await sync_gmail()

    return RedirectResponse(
        "https://smartmail-frontend-r0s5.onrender.com"
    )
