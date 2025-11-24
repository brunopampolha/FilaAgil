import json
import sqlite3
import string
import random
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, abort
from flask_cors import CORS

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "filaagil.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

app = Flask(__name__, static_folder=str(BASE_DIR / "frontend"), static_url_path="")
CORS(app, resources={r"/api/*": {"origins": "*"}})


def init_db():
    """Create the SQLite database on first run."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        return
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
        conn.executescript(schema_file.read())
    conn.commit()
    conn.close()


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def generate_ticket_code(prefix: str) -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=3))
    return f"{prefix}{suffix}"


def serialize_unit(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "address": row["address"],
        "city": row["city"],
        "state": row["state"],
        "avg_wait_minutes": row["avg_wait_minutes"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
    }


def serialize_service(row, queue_size=0, eta=0):
    return {
        "id": row["id"],
        "unit_id": row["unit_id"],
        "name": row["name"],
        "description": row["description"],
        "avg_service_minutes": row["avg_service_minutes"],
        "queue_size": queue_size,
        "estimated_wait_minutes": eta,
    }


def build_ticket_payload(ticket_row, position=None, queue_length=None):
    return {
        "id": ticket_row["id"],
        "code": ticket_row["code"],
        "unit_id": ticket_row["unit_id"],
        "service_id": ticket_row["service_id"],
        "customer_name": ticket_row["customer_name"],
        "priority_level": ticket_row["priority_level"],
        "status": ticket_row["status"],
        "estimated_wait_minutes": ticket_row["estimated_wait_minutes"],
        "created_at": ticket_row["created_at"],
        "checkin_at": ticket_row["checkin_at"],
        "called_at": ticket_row["called_at"],
        "queue_position": position,
        "queue_length": queue_length,
    }


def get_service(conn, service_id):
    service = conn.execute(
        "SELECT s.*, u.name AS unit_name FROM services s "
        "JOIN units u ON u.id = s.unit_id WHERE s.id = ?",
        (service_id,),
    ).fetchone()
    return service


def calculate_queue_snapshot(conn, service_id, ticket_id=None):
    waiting_rows = conn.execute(
        """
        SELECT id, priority_level
        FROM tickets
        WHERE service_id = ? AND status = 'waiting'
        ORDER BY priority_level DESC, datetime(created_at) ASC
        """,
        (service_id,),
    ).fetchall()

    queue_length = len(waiting_rows)
    position = None
    if ticket_id:
        for idx, row in enumerate(waiting_rows, start=1):
            if row["id"] == ticket_id:
                position = idx
                break
    return position, queue_length


def estimate_wait_minutes(avg_service_minutes, position):
    if not position or position < 1:
        return 0
    return max((position - 1) * avg_service_minutes, 0)


def normalize_ticket_ref(ticket_ref):
    """Return (column, value) pair to fetch tickets by id or code."""
    ref = str(ticket_ref).strip()
    if ref.isdigit():
        return "id", int(ref)
    return "code", ref.upper()


def fetch_ticket_basic(conn, ticket_ref):
    column, value = normalize_ticket_ref(ticket_ref)
    return conn.execute(
        f"SELECT * FROM tickets WHERE {column} = ?",
        (value,),
    ).fetchone()


def fetch_ticket_with_details(conn, ticket_ref):
    column, value = normalize_ticket_ref(ticket_ref)
    return conn.execute(
        f"""
        SELECT t.*, s.name AS service_name, u.name AS unit_name, s.avg_service_minutes
        FROM tickets t
        JOIN services s ON s.id = t.service_id
        JOIN units u ON u.id = t.unit_id
        WHERE t.{column} = ?
        """,
        (value,),
    ).fetchone()


@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/dashboard")
def serve_dashboard():
    return send_from_directory(app.static_folder, "dashboard.html")


@app.route("/api/units", methods=["GET"])
def list_units():
    conn = get_connection()
    units_rows = conn.execute("SELECT * FROM units").fetchall()
    services = conn.execute("SELECT * FROM services").fetchall()
    services_by_unit = {}
    for svc in services:
        services_by_unit.setdefault(svc["unit_id"], []).append(svc)

    payload = []
    for unit in units_rows:
        serialized = serialize_unit(unit)
        serialized_services = []
        for svc in services_by_unit.get(unit["id"], []):
            queue_size = conn.execute(
                "SELECT COUNT(*) as total FROM tickets WHERE service_id = ? AND status = 'waiting'",
                (svc["id"],),
            ).fetchone()["total"]
            eta = queue_size * svc["avg_service_minutes"]
            serialized_services.append(serialize_service(svc, queue_size, eta))
        serialized["services"] = serialized_services
        payload.append(serialized)
    conn.close()
    return jsonify(payload)


@app.route("/api/services/<int:unit_id>", methods=["GET"])
def list_services(unit_id):
    conn = get_connection()
    unit = conn.execute("SELECT * FROM units WHERE id = ?", (unit_id,)).fetchone()
    if not unit:
        conn.close()
        abort(404, description="Unidade não encontrada")

    rows = conn.execute("SELECT * FROM services WHERE unit_id = ?", (unit_id,)).fetchall()
    services_payload = []
    for row in rows:
        queue_size = conn.execute(
            "SELECT COUNT(*) AS total FROM tickets WHERE service_id = ? AND status = 'waiting'",
            (row["id"],),
        ).fetchone()["total"]
        eta = queue_size * row["avg_service_minutes"]
        services_payload.append(serialize_service(row, queue_size, eta))
    conn.close()
    return jsonify({"unit": serialize_unit(unit), "services": services_payload})


@app.route("/api/units/<int:unit_id>/queue", methods=["GET"])
def unit_queue(unit_id):
    conn = get_connection()
    unit = conn.execute("SELECT * FROM units WHERE id = ?", (unit_id,)).fetchone()
    if not unit:
        conn.close()
        abort(404, description="Unidade não encontrada")

    tickets = conn.execute(
        """
        SELECT t.*, s.name AS service_name
        FROM tickets t
        JOIN services s ON s.id = t.service_id
        WHERE t.unit_id = ?
          AND t.status IN ('waiting', 'called')
        ORDER BY s.name ASC, t.priority_level DESC, datetime(t.created_at)
        """,
        (unit_id,),
    ).fetchall()

    service_positions = {}
    queue_payload = []
    for row in tickets:
        position = None
        if row["status"] == "waiting":
            service_positions[row["service_id"]] = service_positions.get(row["service_id"], 0) + 1
            position = service_positions[row["service_id"]]
        queue_payload.append(
            {
                "id": row["id"],
                "code": row["code"],
                "customer_name": row["customer_name"],
                "service_id": row["service_id"],
                "service_name": row["service_name"],
                "priority_level": row["priority_level"],
                "status": row["status"],
                "estimated_wait_minutes": row["estimated_wait_minutes"],
                "queue_position": position,
                "created_at": row["created_at"],
            }
        )
    conn.close()
    return jsonify({"unit": serialize_unit(unit), "queue": queue_payload})


@app.route("/api/tickets", methods=["POST"])
def create_ticket():
    data = request.get_json() or {}
    required = ["unit_id", "service_id", "customer_name"]
    if any(field not in data for field in required):
        abort(400, description="Campos obrigatórios ausentes")

    priority_level = int(data.get("priority_level", 0))
    if priority_level not in (0, 1, 2):
        priority_level = 0

    conn = get_connection()
    service = conn.execute(
        "SELECT s.*, u.name AS unit_name FROM services s "
        "JOIN units u ON u.id = s.unit_id WHERE s.id = ? AND s.unit_id = ?",
        (data["service_id"], data["unit_id"]),
    ).fetchone()

    if not service:
        conn.close()
        abort(404, description="Serviço não encontrado")

    waiting_ahead = conn.execute(
        """
        SELECT COUNT(*) as total
        FROM tickets
        WHERE service_id = ?
          AND status = 'waiting'
          AND (priority_level > ? OR (priority_level = ?))
        """,
        (service["id"], priority_level, priority_level),
    ).fetchone()["total"]

    estimated_wait = waiting_ahead * service["avg_service_minutes"]
    code_prefix = service["name"][0].upper()
    code = generate_ticket_code(code_prefix)
    created_at = datetime.utcnow().isoformat()

    cursor = conn.execute(
        """
        INSERT INTO tickets (unit_id, service_id, code, customer_name, priority_level, status,
                             estimated_wait_minutes, created_at)
        VALUES (?, ?, ?, ?, ?, 'waiting', ?, ?)
        """,
        (
            service["unit_id"],
            service["id"],
            code,
            data["customer_name"].strip(),
            priority_level,
            estimated_wait,
            created_at,
        ),
    )
    ticket_id = cursor.lastrowid
    conn.commit()
    ticket_row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    position, queue_length = calculate_queue_snapshot(conn, service["id"], ticket_id)
    conn.close()

    payload = build_ticket_payload(ticket_row, position, queue_length)
    payload.update(
        {
            "unit_name": service["unit_name"],
            "service_name": service["name"],
            "estimated_wait_minutes": estimated_wait,
        }
    )
    return jsonify(payload), 201


@app.route("/api/tickets/<ticket_ref>", methods=["GET"])
def get_ticket(ticket_ref):
    conn = get_connection()
    ticket = fetch_ticket_with_details(conn, ticket_ref)

    if not ticket:
        conn.close()
        abort(404, description="Senha não encontrada")

    position, queue_length = (None, None)
    if ticket["status"] == "waiting":
        position, queue_length = calculate_queue_snapshot(conn, ticket["service_id"], ticket["id"])
        eta = estimate_wait_minutes(ticket["avg_service_minutes"], position)
    else:
        eta = 0
    conn.close()

    payload = build_ticket_payload(ticket, position, queue_length)
    payload["unit_name"] = ticket["unit_name"]
    payload["service_name"] = ticket["service_name"]
    payload["estimated_wait_minutes"] = eta
    return jsonify(payload)


@app.route("/api/tickets/<ticket_ref>/checkin", methods=["POST"])
def checkin_ticket(ticket_ref):
    conn = get_connection()
    ticket = fetch_ticket_basic(conn, ticket_ref)
    if not ticket:
        conn.close()
        abort(404, description="Senha não encontrada")

    if ticket["status"] not in ("waiting", "called"):
        conn.close()
        abort(400, description="Ticket não pode receber check-in")

    now = datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE tickets SET checkin_at = ?, status = 'waiting' WHERE id = ?",
        (now, ticket["id"]),
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Check-in registrado", "ticket_id": ticket["id"], "checkin_at": now})


@app.route("/api/tickets/<ticket_ref>", methods=["DELETE"])
def delete_ticket(ticket_ref):
    conn = get_connection()
    ticket = fetch_ticket_basic(conn, ticket_ref)
    if not ticket:
        conn.close()
        abort(404, description="Senha não encontrada")

    if ticket["status"] not in ("waiting", "called"):
        conn.close()
        abort(400, description="Apenas senhas na fila podem ser removidas")

    conn.execute("DELETE FROM tickets WHERE id = ?", (ticket["id"],))
    conn.commit()
    conn.close()
    return jsonify({"message": "Senha removida da fila", "ticket_id": ticket["id"]})


@app.route("/api/dashboard", methods=["GET"])
def dashboard():
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT
            u.id,
            u.name,
            COUNT(CASE WHEN t.status = 'waiting' THEN 1 END) AS waiting_count,
            COUNT(CASE WHEN t.status = 'called' THEN 1 END) AS called_count,
            COUNT(CASE WHEN t.status = 'completed' THEN 1 END) AS completed_count,
            AVG(CASE WHEN t.status = 'waiting' THEN t.estimated_wait_minutes END) AS avg_waiting
        FROM units u
        LEFT JOIN tickets t ON t.unit_id = u.id
        GROUP BY u.id
        ORDER BY u.name
        """
    ).fetchall()

    payload = []
    for row in rows:
        payload.append(
            {
                "unit_id": row["id"],
                "unit_name": row["name"],
                "waiting_count": row["waiting_count"],
                "called_count": row["called_count"],
                "completed_count": row["completed_count"],
                "avg_waiting_minutes": round(row["avg_waiting"], 1) if row["avg_waiting"] else 0,
            }
        )
    conn.close()
    return jsonify(payload)


init_db()

if __name__ == "__main__":
    app.run(debug=True)
