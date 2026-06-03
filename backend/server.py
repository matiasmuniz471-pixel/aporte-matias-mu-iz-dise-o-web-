import hashlib
import hmac
import json
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
PAGES_DIR = FRONTEND_ROOT / "pages"
DB_PATH = PROJECT_ROOT / "data" / "seminario_tech.db"
SESSION_COOKIE = "seminario_session"
SESSION_DURATION = timedelta(days=7)
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def utc_now():
    return datetime.now(timezone.utc)


def format_db_datetime(value):
    return value.astimezone(timezone.utc).isoformat()


def parse_db_datetime(value):
    return datetime.fromisoformat(value)


def today_label():
    return datetime.now().strftime("%d/%m/%Y")


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                correo TEXT NOT NULL UNIQUE,
                tipo TEXT NOT NULL CHECK(tipo IN ('cliente', 'empresa')),
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS company_profiles (
                user_id INTEGER PRIMARY KEY,
                razon_social TEXT NOT NULL,
                identificacion_fiscal TEXT NOT NULL,
                sector TEXT NOT NULL,
                telefono TEXT NOT NULL,
                sitio_web TEXT NOT NULL,
                representante TEXT NOT NULL,
                cargo_representante TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS seminars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                titulo TEXT NOT NULL,
                fecha TEXT NOT NULL,
                categoria TEXT NOT NULL,
                descripcion TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seminar_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                nombre TEXT NOT NULL,
                correo TEXT NOT NULL,
                fecha_union TEXT NOT NULL,
                FOREIGN KEY(seminar_id) REFERENCES seminars(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        200_000,
    )
    return f"{salt}${digest.hex()}"


def verify_password(password, stored_value):
    try:
        salt, expected_hash = stored_value.split("$", 1)
    except ValueError:
        return False

    candidate_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        200_000,
    ).hex()
    return hmac.compare_digest(candidate_hash, expected_hash)


def normalize_user(row):
    if row is None:
        return None

    return {
        "id": row["id"],
        "nombre": row["nombre"],
        "correo": row["correo"],
        "tipo": row["tipo"],
    }


def normalize_company_profile(row):
    if row is None:
        return None

    return {
        "razonSocial": row["razon_social"],
        "identificacionFiscal": row["identificacion_fiscal"],
        "sector": row["sector"],
        "telefono": row["telefono"],
        "sitioWeb": row["sitio_web"],
        "representante": row["representante"],
        "cargoRepresentante": row["cargo_representante"],
    }


def fetch_user(connection, user_id):
    return connection.execute(
        "SELECT id, nombre, correo, tipo FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()


def fetch_company_profile(connection, user_id):
    return connection.execute(
        """
        SELECT razon_social, identificacion_fiscal, sector, telefono, sitio_web,
               representante, cargo_representante
        FROM company_profiles
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()


def build_company_dashboard_payload(connection, user):
    seminars = connection.execute(
        """
        SELECT
            s.id,
            s.titulo,
            s.fecha,
            s.categoria,
            s.descripcion,
            s.created_at,
            SUM(CASE WHEN pu.tipo = 'cliente' THEN 1 ELSE 0 END) AS participantes
        FROM seminars s
        LEFT JOIN participants p ON p.seminar_id = s.id
        LEFT JOIN users pu ON pu.id = p.user_id
        WHERE s.user_id = ?
        GROUP BY s.id
        ORDER BY s.created_at DESC, s.id DESC
        """,
        (user["id"],),
    ).fetchall()

    participants = connection.execute(
        """
        SELECT
            p.id,
            p.nombre,
            p.correo,
            p.fecha_union,
            s.titulo AS seminario
        FROM participants p
        INNER JOIN seminars s ON s.id = p.seminar_id
        INNER JOIN users u ON u.id = p.user_id
        WHERE s.user_id = ? AND u.tipo = 'cliente'
        ORDER BY p.id DESC
        """,
        (user["id"],),
    ).fetchall()

    recent_activity = [
        {"titulo": "Seminario publicado", "detalle": seminar["titulo"]}
        for seminar in seminars[:5]
    ]

    return {
        "dashboardType": "empresa",
        "usuario": normalize_user(user),
        "perfilEmpresa": normalize_company_profile(fetch_company_profile(connection, user["id"])),
        "beneficios": [
            "Crear y publicar seminarios profesionales",
            "Gestionar participantes inscritos",
            "Medir actividad de eventos",
            "Dar mayor visibilidad a la marca",
        ],
        "seminarios": [
            {
                "id": seminar["id"],
                "titulo": seminar["titulo"],
                "fecha": seminar["fecha"],
                "categoria": seminar["categoria"],
                "descripcion": seminar["descripcion"],
                "participantes": seminar["participantes"],
            }
            for seminar in seminars
        ],
        "participantes": [
            {
                "id": participant["id"],
                "nombre": participant["nombre"],
                "correo": participant["correo"],
                "seminario": participant["seminario"],
                "fechaUnion": participant["fecha_union"],
            }
            for participant in participants
        ],
        "actividad": recent_activity,
        "estadisticas": {
            "totalSeminarios": len(seminars),
            "totalParticipantes": len(participants),
        },
    }


def build_client_dashboard_payload(connection, user):
    available_events = connection.execute(
        """
        SELECT
            s.id,
            s.titulo,
            s.fecha,
            s.categoria,
            s.descripcion,
            u.nombre AS empresa,
            cp.razon_social AS razon_social,
            CASE WHEN p.id IS NULL THEN 0 ELSE 1 END AS inscrito
        FROM seminars s
        INNER JOIN users u ON u.id = s.user_id
        LEFT JOIN company_profiles cp ON cp.user_id = u.id
        LEFT JOIN participants p ON p.seminar_id = s.id AND p.user_id = ?
        WHERE u.tipo = 'empresa'
        ORDER BY s.fecha ASC, s.id DESC
        """,
        (user["id"],),
    ).fetchall()

    inscriptions = connection.execute(
        """
        SELECT
            p.id,
            p.fecha_union,
            s.id AS seminar_id,
            s.titulo,
            s.fecha,
            s.categoria,
            u.nombre AS empresa,
            cp.razon_social AS razon_social
        FROM participants p
        INNER JOIN seminars s ON s.id = p.seminar_id
        INNER JOIN users u ON u.id = s.user_id
        LEFT JOIN company_profiles cp ON cp.user_id = u.id
        WHERE p.user_id = ?
        ORDER BY p.id DESC
        """,
        (user["id"],),
    ).fetchall()

    return {
        "dashboardType": "cliente",
        "usuario": normalize_user(user),
        "beneficios": [
            "Acceder a eventos tecnol\u00f3gicos disponibles",
            "Inscribirte en seminarios profesionales",
            "Consultar certificados pendientes",
            "Conectar con empresas organizadoras",
        ],
        "eventosDisponibles": [
            {
                "id": event["id"],
                "titulo": event["titulo"],
                "fecha": event["fecha"],
                "categoria": event["categoria"],
                "descripcion": event["descripcion"],
                "empresa": event["razon_social"] or event["empresa"],
                "inscrito": bool(event["inscrito"]),
            }
            for event in available_events
        ],
        "inscripciones": [
            {
                "id": inscription["id"],
                "seminarId": inscription["seminar_id"],
                "titulo": inscription["titulo"],
                "fecha": inscription["fecha"],
                "categoria": inscription["categoria"],
                "empresa": inscription["razon_social"] or inscription["empresa"],
                "fechaUnion": inscription["fecha_union"],
                "certificado": "Pendiente",
            }
            for inscription in inscriptions
        ],
        "certificados": [
            {
                "titulo": inscription["titulo"],
                "empresa": inscription["razon_social"] or inscription["empresa"],
                "estado": "Pendiente",
            }
            for inscription in inscriptions
        ],
        "estadisticas": {
            "totalEventos": len(available_events),
            "totalInscripciones": len(inscriptions),
            "totalCertificados": len(inscriptions),
        },
    }


def build_dashboard_payload(connection, user_id):
    user = fetch_user(connection, user_id)
    if user is None:
        return None

    if user["tipo"] == "empresa":
        return build_company_dashboard_payload(connection, user)

    return build_client_dashboard_payload(connection, user)


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api("GET", parsed.path)
            return

        if parsed.path == "/":
            self.path = "/frontend/pages/index.html"
        elif parsed.path in {"/index.html", "/login.html", "/dashboard.html"}:
            self.path = f"/frontend/pages{parsed.path}"
        elif parsed.path.startswith("/assets/"):
            self.path = f"/frontend{parsed.path}"

        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api("POST", parsed.path)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Ruta no encontrada")

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api("DELETE", parsed.path)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Ruta no encontrada")

    def log_message(self, format, *args):
        return

    def handle_api(self, method, path):
        try:
            if method == "POST" and path == "/api/register":
                self.api_register()
                return
            if method == "POST" and path == "/api/login":
                self.api_login()
                return
            if method == "POST" and path == "/api/logout":
                self.api_logout()
                return
            if method == "GET" and path == "/api/session":
                self.api_session()
                return
            if method == "GET" and path == "/api/dashboard":
                self.api_dashboard()
                return
            if method == "POST" and path == "/api/seminarios":
                self.api_create_seminar()
                return
            if method == "POST" and path == "/api/inscripciones":
                self.api_create_inscription()
                return
            if method == "DELETE" and path.startswith("/api/seminarios/"):
                seminar_id = path.rsplit("/", 1)[-1]
                self.api_delete_seminar(seminar_id)
                return

            self.send_json(HTTPStatus.NOT_FOUND, {"message": "Ruta API no encontrada"})
        except ValueError as error:
            self.send_json(HTTPStatus.BAD_REQUEST, {"message": str(error)})
        except Exception as error:
            self.send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"message": f"Ocurri\u00f3 un error interno: {error}"},
            )

    def parse_json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("El cuerpo de la solicitud no es JSON v\u00e1lido.") from error

    def send_json(self, status, payload, extra_headers=None):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if extra_headers:
            for header, value in extra_headers.items():
                self.send_header(header, value)
        self.end_headers()
        self.wfile.write(body)

    def get_cookie_value(self, key):
        cookie_header = self.headers.get("Cookie")
        if not cookie_header:
            return None

        cookie = SimpleCookie()
        cookie.load(cookie_header)
        morsel = cookie.get(key)
        return morsel.value if morsel else None

    def build_session_cookie(self, session_id, expires_at=None):
        parts = [f"{SESSION_COOKIE}={session_id}", "HttpOnly", "Path=/", "SameSite=Lax"]
        if expires_at:
            parts.append(f"Expires={expires_at.strftime('%a, %d %b %Y %H:%M:%S GMT')}")
        return "; ".join(parts)

    def clear_session_cookie(self):
        expired = utc_now() - timedelta(days=1)
        return self.build_session_cookie("", expired)

    def get_current_user(self, connection):
        session_id = self.get_cookie_value(SESSION_COOKIE)
        if not session_id:
            return None

        session = connection.execute(
            """
            SELECT s.id, s.user_id, s.expires_at, u.id AS user_id_value,
                   u.nombre, u.correo, u.tipo
            FROM sessions s
            INNER JOIN users u ON u.id = s.user_id
            WHERE s.id = ?
            """,
            (session_id,),
        ).fetchone()

        if session is None:
            return None

        if parse_db_datetime(session["expires_at"]) <= utc_now():
            connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            connection.commit()
            return None

        return {
            "id": session["user_id_value"],
            "nombre": session["nombre"],
            "correo": session["correo"],
            "tipo": session["tipo"],
            "session_id": session["id"],
        }

    def require_user(self, connection):
        user = self.get_current_user(connection)
        if user is None:
            self.send_json(
                HTTPStatus.UNAUTHORIZED,
                {"message": "Debes iniciar sesi\u00f3n para continuar."},
                extra_headers={"Set-Cookie": self.clear_session_cookie()},
            )
            return None
        return user

    def require_role(self, user, expected_role):
        if user["tipo"] != expected_role:
            self.send_json(
                HTTPStatus.FORBIDDEN,
                {"message": "Tu tipo de cuenta no tiene permiso para esta acci\u00f3n."},
            )
            return False
        return True

    def create_session(self, connection, user_id):
        session_id = secrets.token_urlsafe(32)
        expires_at = utc_now() + SESSION_DURATION
        connection.execute(
            """
            INSERT INTO sessions (id, user_id, expires_at, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                session_id,
                user_id,
                format_db_datetime(expires_at),
                format_db_datetime(utc_now()),
            ),
        )
        connection.commit()
        return session_id, expires_at

    def validate_company_payload(self, payload):
        company = payload.get("empresa") or {}
        required = {
            "razonSocial": "Ingresa la raz\u00f3n social de la empresa.",
            "identificacionFiscal": "Ingresa el RUC o ID fiscal.",
            "sector": "Ingresa el sector de la empresa.",
            "telefono": "Ingresa un tel\u00e9fono de contacto.",
            "sitioWeb": "Ingresa el sitio web o perfil digital de la empresa.",
            "representante": "Ingresa el representante o contacto principal.",
            "cargoRepresentante": "Ingresa el cargo del representante.",
        }

        normalized = {}
        for key, message in required.items():
            value = str(company.get(key, "")).strip()
            if not value:
                raise ValueError(message)
            normalized[key] = value

        return normalized

    def api_register(self):
        payload = self.parse_json_body()
        nombre = str(payload.get("nombre", "")).strip()
        correo = str(payload.get("correo", "")).strip().lower()
        tipo = str(payload.get("tipo", "")).strip()
        password = str(payload.get("password", "")).strip()
        company_profile = None

        if len(nombre) < 5:
            raise ValueError("Ingresa un nombre v\u00e1lido.")
        if not EMAIL_PATTERN.match(correo):
            raise ValueError("Ingresa un correo v\u00e1lido.")
        if tipo not in {"cliente", "empresa"}:
            raise ValueError("Selecciona un tipo de cuenta v\u00e1lido.")
        if len(password) < 6:
            raise ValueError("La contrase\u00f1a debe tener m\u00ednimo 6 caracteres.")
        if tipo == "empresa":
            company_profile = self.validate_company_payload(payload)

        created_at = format_db_datetime(utc_now())

        with get_connection() as connection:
            exists = connection.execute(
                "SELECT id FROM users WHERE correo = ?",
                (correo,),
            ).fetchone()
            if exists:
                self.send_json(
                    HTTPStatus.CONFLICT,
                    {"message": "Este correo ya est\u00e1 registrado."},
                )
                return

            cursor = connection.execute(
                """
                INSERT INTO users (nombre, correo, tipo, password_hash, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (nombre, correo, tipo, hash_password(password), created_at),
            )
            user_id = cursor.lastrowid

            if company_profile:
                connection.execute(
                    """
                    INSERT INTO company_profiles (
                        user_id, razon_social, identificacion_fiscal, sector, telefono,
                        sitio_web, representante, cargo_representante, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        company_profile["razonSocial"],
                        company_profile["identificacionFiscal"],
                        company_profile["sector"],
                        company_profile["telefono"],
                        company_profile["sitioWeb"],
                        company_profile["representante"],
                        company_profile["cargoRepresentante"],
                        created_at,
                    ),
                )

            connection.commit()
            session_id, expires_at = self.create_session(connection, user_id)
            user = fetch_user(connection, user_id)

        self.send_json(
            HTTPStatus.CREATED,
            {
                "message": "Cuenta creada correctamente.",
                "usuario": normalize_user(user),
            },
            extra_headers={"Set-Cookie": self.build_session_cookie(session_id, expires_at)},
        )

    def api_login(self):
        payload = self.parse_json_body()
        correo = str(payload.get("correo", "")).strip().lower()
        password = str(payload.get("password", "")).strip()

        if not EMAIL_PATTERN.match(correo):
            raise ValueError("Ingresa un correo v\u00e1lido.")
        if not password:
            raise ValueError("Ingresa tu contrase\u00f1a.")

        with get_connection() as connection:
            user = connection.execute(
                "SELECT * FROM users WHERE correo = ?",
                (correo,),
            ).fetchone()

            if user is None or not verify_password(password, user["password_hash"]):
                self.send_json(
                    HTTPStatus.UNAUTHORIZED,
                    {"message": "Correo o contrase\u00f1a incorrectos."},
                )
                return

            session_id, expires_at = self.create_session(connection, user["id"])

        self.send_json(
            HTTPStatus.OK,
            {
                "message": "Inicio de sesi\u00f3n exitoso.",
                "usuario": normalize_user(user),
            },
            extra_headers={"Set-Cookie": self.build_session_cookie(session_id, expires_at)},
        )

    def api_logout(self):
        with get_connection() as connection:
            user = self.get_current_user(connection)
            if user:
                connection.execute("DELETE FROM sessions WHERE id = ?", (user["session_id"],))
                connection.commit()

        self.send_json(
            HTTPStatus.OK,
            {"message": "Sesi\u00f3n cerrada correctamente."},
            extra_headers={"Set-Cookie": self.clear_session_cookie()},
        )

    def api_session(self):
        with get_connection() as connection:
            user = self.get_current_user(connection)
            if user is None:
                self.send_json(
                    HTTPStatus.UNAUTHORIZED,
                    {"message": "No hay una sesi\u00f3n activa."},
                    extra_headers={"Set-Cookie": self.clear_session_cookie()},
                )
                return

        self.send_json(HTTPStatus.OK, {"usuario": normalize_user(user)})

    def api_dashboard(self):
        with get_connection() as connection:
            user = self.require_user(connection)
            if user is None:
                return

            payload = build_dashboard_payload(connection, user["id"])
            self.send_json(HTTPStatus.OK, payload)

    def api_create_seminar(self):
        payload = self.parse_json_body()
        titulo = str(payload.get("titulo", "")).strip()
        fecha = str(payload.get("fecha", "")).strip()
        categoria = str(payload.get("categoria", "")).strip()
        descripcion = str(payload.get("descripcion", "")).strip()

        if not titulo or not fecha or not categoria or not descripcion:
            raise ValueError("Completa todos los campos del seminario.")

        with get_connection() as connection:
            user = self.require_user(connection)
            if user is None or not self.require_role(user, "empresa"):
                return

            created_at = format_db_datetime(utc_now())
            connection.execute(
                """
                INSERT INTO seminars (user_id, titulo, fecha, categoria, descripcion, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user["id"], titulo, fecha, categoria, descripcion, created_at),
            )
            connection.commit()
            payload = build_dashboard_payload(connection, user["id"])

        self.send_json(
            HTTPStatus.CREATED,
            {
                "message": "Seminario publicado correctamente.",
                **payload,
            },
        )

    def api_create_inscription(self):
        payload = self.parse_json_body()
        seminar_id = str(payload.get("seminarId", "")).strip()
        if not seminar_id.isdigit():
            raise ValueError("Selecciona un seminario v\u00e1lido.")

        with get_connection() as connection:
            user = self.require_user(connection)
            if user is None or not self.require_role(user, "cliente"):
                return

            seminar = connection.execute(
                """
                SELECT s.id, s.titulo, s.user_id, u.tipo AS owner_tipo
                FROM seminars s
                INNER JOIN users u ON u.id = s.user_id
                WHERE s.id = ?
                """,
                (int(seminar_id),),
            ).fetchone()

            if seminar is None or seminar["owner_tipo"] != "empresa":
                self.send_json(HTTPStatus.NOT_FOUND, {"message": "No encontramos ese seminario."})
                return

            exists = connection.execute(
                "SELECT id FROM participants WHERE seminar_id = ? AND user_id = ?",
                (seminar["id"], user["id"]),
            ).fetchone()
            if exists:
                self.send_json(
                    HTTPStatus.CONFLICT,
                    {"message": "Ya est\u00e1s inscrito en este seminario."},
                )
                return

            connection.execute(
                """
                INSERT INTO participants (seminar_id, user_id, nombre, correo, fecha_union)
                VALUES (?, ?, ?, ?, ?)
                """,
                (seminar["id"], user["id"], user["nombre"], user["correo"], today_label()),
            )
            connection.commit()
            payload = build_dashboard_payload(connection, user["id"])

        self.send_json(
            HTTPStatus.CREATED,
            {
                "message": f'Inscripci\u00f3n confirmada para "{seminar["titulo"]}".',
                **payload,
            },
        )

    def api_delete_seminar(self, seminar_id):
        if not seminar_id.isdigit():
            self.send_json(HTTPStatus.BAD_REQUEST, {"message": "ID de seminario inv\u00e1lido."})
            return

        with get_connection() as connection:
            user = self.require_user(connection)
            if user is None or not self.require_role(user, "empresa"):
                return

            seminar = connection.execute(
                "SELECT id, titulo FROM seminars WHERE id = ? AND user_id = ?",
                (int(seminar_id), user["id"]),
            ).fetchone()

            if seminar is None:
                self.send_json(
                    HTTPStatus.NOT_FOUND,
                    {"message": "No encontramos ese seminario en tu cuenta."},
                )
                return

            connection.execute("DELETE FROM participants WHERE seminar_id = ?", (seminar["id"],))
            connection.execute("DELETE FROM seminars WHERE id = ?", (seminar["id"],))
            connection.commit()
            payload = build_dashboard_payload(connection, user["id"])

        self.send_json(
            HTTPStatus.OK,
            {
                "message": f'Seminario "{seminar["titulo"]}" eliminado correctamente.',
                **payload,
            },
        )


def run():
    init_db()
    server = ThreadingHTTPServer(("127.0.0.1", 4173), AppHandler)
    print("Seminario Tech disponible en http://127.0.0.1:4173")
    server.serve_forever()


if __name__ == "__main__":
    run()
