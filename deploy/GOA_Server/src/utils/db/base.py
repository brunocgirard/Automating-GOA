import os
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

# Define database connection path
DB_PATH = os.getenv("DATABASE_PATH") or os.path.join("data", "crm_data.db")

# Define base template paths
HTML_TEMPLATE_PATH = os.path.join("templates", "goa_form.html")
DOCX_TEMPLATE_PATH = os.path.join("templates", "template.docx")
# Legacy constant kept for compatibility
TEMPLATE_FILE_PATH = os.path.join("templates", "template.docx")

# Keep track of database files that have already been initialized in-process.
_INITIALIZED_DB_PATHS: set[str] = set()


def timestamp() -> str:
    """Return a standard DB timestamp string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def owner_scope_clause(
    owner_user_id: int | None = None,
    include_all_for_admin: bool = False,
    table_alias: str = "",
) -> tuple[str, list[int]]:
    """Return a SQL ownership filter fragment and its params."""
    prefix = f"{table_alias}." if table_alias else ""
    if include_all_for_admin:
        return "", []
    if isinstance(owner_user_id, int) and owner_user_id > 0:
        return f" AND {prefix}owner_user_id = ?", [owner_user_id]
    return "", []


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    """Convert a sqlite row to a dict."""
    return dict(row) if row else None


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    """Convert sqlite rows to plain dicts."""
    return [dict(row) for row in rows]


def safe_json_loads(value: str | bytes | bytearray | None, default=None):
    """Best-effort JSON parsing with a caller-provided fallback."""
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def to_text(value) -> str:
    """Normalize values to stripped text."""
    return str(value).strip() if value is not None else ""


def _normalize_db_path(db_path: str) -> str:
    """Return a normalized absolute path for tracking initialized databases."""
    return os.path.abspath(db_path)


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """
    Creates and returns a database connection.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        sqlite3.Connection: Database connection object
    """
    normalized_path = _normalize_db_path(db_path)
    if normalized_path not in _INITIALIZED_DB_PATHS:
        # Ensure schema exists even when startup hooks are skipped.
        init_db(normalized_path)
        _INITIALIZED_DB_PATHS.add(normalized_path)

    conn = sqlite3.connect(normalized_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@contextmanager
def connection_context(db_path: str = DB_PATH):
    """Yield a DB connection and always close it on exit."""
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: str = DB_PATH):
    """
    Initializes the SQLite database. Creates all required tables if they don't exist.

    Tables created:
    - clients: Customer information
    - priced_items: Line items from PDF quotes
    - machines: Identified machines within quotes
    - machine_templates: GOA outputs for specific machines
    - few_shot_examples: High-quality examples for LLM learning
    - few_shot_feedback: User corrections and improvements
    - document_content: Full PDF text for chat functionality
    - goa_modifications: Changes made to GOA templates
    """
    conn = None
    try:
        normalized_path = _normalize_db_path(db_path)

        db_dir = os.path.dirname(normalized_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

        conn = sqlite3.connect(normalized_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_ref TEXT UNIQUE NOT NULL,
            customer_name TEXT,
            machine_model TEXT,
            sold_to_address TEXT,
            ship_to_address TEXT,
            telephone TEXT,
            customer_contact_person TEXT,
            customer_po TEXT,
            processing_date TEXT NOT NULL,
            incoterm TEXT,
            company TEXT,
            serial_number TEXT,
            ax TEXT,
            ox TEXT,
            via TEXT,
            tax_id TEXT,
            hs_code TEXT,
            customer_number TEXT,
            order_date TEXT,
            owner_user_id INTEGER
        )
        """)

        # Schema migration for existing databases
        cursor.execute("PRAGMA table_info(clients)")
        existing_columns = [row[1] for row in cursor.fetchall()]

        new_columns = {
            "company": "TEXT", "serial_number": "TEXT", "ax": "TEXT",
            "ox": "TEXT", "via": "TEXT", "tax_id": "TEXT", "hs_code": "TEXT",
            "customer_number": "TEXT", "order_date": "TEXT", "owner_user_id": "INTEGER"
        }

        for col_name, col_type in new_columns.items():
            if col_name not in existing_columns:
                cursor.execute(f"ALTER TABLE clients ADD COLUMN {col_name} {col_type}")
                print(f"Added column '{col_name}' to 'clients' table.")

        # Auth tables for multi-user support.
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            display_name TEXT,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'standard',
            is_active INTEGER NOT NULL DEFAULT 1,
            gemini_api_key_encrypted TEXT,
            created_date TEXT NOT NULL,
            modified_date TEXT NOT NULL,
            last_login_at TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            last_seen_at TEXT,
            revoked_at TEXT,
            ip_address TEXT,
            user_agent TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS auth_audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            event_type TEXT NOT NULL,
            metadata_json TEXT,
            ip_address TEXT,
            user_agent TEXT,
            occurred_at TEXT NOT NULL
        )
        """)

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_user_id
            ON sessions (user_id)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_token_hash
            ON sessions (token_hash)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_auth_audit_user_time
            ON auth_audit_events (user_id, occurred_at)
            """
        )

        # Create priced_items table with item_quantity
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS priced_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_quote_ref TEXT NOT NULL,
            item_description TEXT,
            item_quantity TEXT,       -- Store as TEXT to handle various formats
            item_price_str TEXT,
            item_price_numeric REAL,
            FOREIGN KEY (client_quote_ref) REFERENCES clients (quote_ref) ON DELETE CASCADE
        )
        """)

        # Create machines table to store identified machines within a quote
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS machines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_quote_ref TEXT NOT NULL,
            machine_name TEXT NOT NULL,
            machine_data_json TEXT NOT NULL,
            processing_date TEXT NOT NULL,
            FOREIGN KEY (client_quote_ref) REFERENCES clients (quote_ref) ON DELETE CASCADE
        )
        """)

        # Create machine_templates table to store GOA outputs for specific machines
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS machine_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id INTEGER NOT NULL,
            template_type TEXT NOT NULL,
            template_data_json TEXT NOT NULL,
            output_preferences_json TEXT,
            generated_file_path TEXT,
            processing_date TEXT NOT NULL,
            FOREIGN KEY (machine_id) REFERENCES machines (id) ON DELETE CASCADE
        )
        """)

        # Schema migration for existing machine_templates tables
        cursor.execute("PRAGMA table_info(machine_templates)")
        machine_template_columns = [row[1] for row in cursor.fetchall()]
        if "output_preferences_json" not in machine_template_columns:
            cursor.execute("ALTER TABLE machine_templates ADD COLUMN output_preferences_json TEXT")
            print("Added column 'output_preferences_json' to 'machine_templates' table.")

        # Create few_shot_examples table to store high-quality examples for LLM learning
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS few_shot_examples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_type TEXT NOT NULL,
            template_type TEXT NOT NULL,
            field_name TEXT NOT NULL,
            input_context TEXT NOT NULL,
            expected_output TEXT NOT NULL,
            confidence_score REAL DEFAULT 1.0,
            usage_count INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            created_date TEXT NOT NULL,
            last_used_date TEXT,
            source_machine_id INTEGER,
            FOREIGN KEY (source_machine_id) REFERENCES machines (id) ON DELETE SET NULL
        )
        """)

        # Create few_shot_feedback table to track user corrections and improvements
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS few_shot_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            example_id INTEGER NOT NULL,
            feedback_type TEXT NOT NULL,
            original_prediction TEXT,
            corrected_value TEXT,
            feedback_date TEXT NOT NULL,
            user_context TEXT,
            FOREIGN KEY (example_id) REFERENCES few_shot_examples (id) ON DELETE CASCADE
        )
        """)

        # Create document_content table to store PDF text for later chat functionality
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_quote_ref TEXT UNIQUE NOT NULL,
            full_pdf_text TEXT,
            pdf_filename TEXT,
            upload_date TEXT NOT NULL,
            FOREIGN KEY (client_quote_ref) REFERENCES clients (quote_ref) ON DELETE CASCADE
        )
        """)

        # Create goa_modifications table to track changes made to GOA templates
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS goa_modifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_template_id INTEGER NOT NULL,
            field_key TEXT NOT NULL,
            original_value TEXT,
            modified_value TEXT NOT NULL,
            modification_reason TEXT,
            modified_by TEXT,
            modification_date TEXT NOT NULL,
            FOREIGN KEY (machine_template_id) REFERENCES machine_templates (id) ON DELETE CASCADE
        )
        """)

        # Store shipping workflow drafts as a full JSON blob keyed by quote.
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS shipping_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_quote_ref TEXT NOT NULL,
            shipping_data_json TEXT NOT NULL,
            created_date TEXT NOT NULL,
            modified_date TEXT NOT NULL,
            FOREIGN KEY (client_quote_ref) REFERENCES clients (quote_ref) ON DELETE CASCADE
        )
        """)

        # Store COR workflow drafts as a full JSON blob keyed by quote.
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS cor_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_quote_ref TEXT NOT NULL,
            cor_no TEXT,
            description TEXT,
            cor_data_json TEXT NOT NULL,
            created_date TEXT NOT NULL,
            modified_date TEXT NOT NULL,
            FOREIGN KEY (client_quote_ref) REFERENCES clients (quote_ref) ON DELETE CASCADE
        )
        """)

        # Store PM projects linked to quote references.
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            quote_ref TEXT,
            machine_summary TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            risk_level TEXT NOT NULL DEFAULT 'on_track',
            start_date TEXT,
            target_end_date TEXT,
            actual_end_date TEXT,
            gantt_data_json TEXT,
            created_date TEXT NOT NULL,
            modified_date TEXT NOT NULL,
            owner_user_id INTEGER,
            FOREIGN KEY (quote_ref) REFERENCES clients (quote_ref) ON DELETE SET NULL
        )
        """)

        cursor.execute("PRAGMA table_info(projects)")
        project_columns = [row[1] for row in cursor.fetchall()]
        if "owner_user_id" not in project_columns:
            cursor.execute("ALTER TABLE projects ADD COLUMN owner_user_id INTEGER")
            print("Added column 'owner_user_id' to 'projects' table.")

        # Independent PM checklist tasks (non-linear execution supported).
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            task_name TEXT NOT NULL,
            task_order INTEGER NOT NULL,
            phase TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            planned_date TEXT,
            actual_date TEXT,
            notes TEXT,
            modified_date TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
        )
        """)

        # Audit trail for task status changes.
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS task_transitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_task_id INTEGER NOT NULL,
            from_status TEXT,
            to_status TEXT NOT NULL,
            transitioned_at TEXT NOT NULL,
            FOREIGN KEY (project_task_id) REFERENCES project_tasks (id) ON DELETE CASCADE
        )
        """)

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_project_tasks_project_phase
            ON project_tasks (project_id, phase, task_order)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_project_tasks_status
            ON project_tasks (status)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_task_transitions_task_time
            ON task_transitions (project_task_id, transitioned_at)
            """
        )

        # Personal PM task board items scoped to a user.
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                client_tag TEXT,
                priority TEXT NOT NULL DEFAULT 'normal',
                status TEXT NOT NULL DEFAULT 'pending',
                due_date TEXT,
                completed_at TEXT,
                created_at TEXT NOT NULL,
                modified_at TEXT NOT NULL,
                FOREIGN KEY (owner_user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_tasks_owner_status
            ON user_tasks (owner_user_id, status)
            """
        )

        cursor.execute("PRAGMA table_info(cor_documents)")
        cor_columns = [row[1] for row in cursor.fetchall()]
        cor_new_columns = {
            "cor_no": "TEXT",
            "description": "TEXT",
        }
        for col_name, col_type in cor_new_columns.items():
            if col_name not in cor_columns:
                cursor.execute(f"ALTER TABLE cor_documents ADD COLUMN {col_name} {col_type}")
                print(f"Added column '{col_name}' to 'cor_documents' table.")

        _INITIALIZED_DB_PATHS.add(normalized_path)
        print(f"Database '{normalized_path}' initialized with all required tables.")
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error initializing database: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during DB init: {e}")
    finally:
        if conn:
            conn.close()
