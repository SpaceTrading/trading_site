import os
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash


# =========================================================
# APP SETUP
# =========================================================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(INSTANCE_DIR, "app.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)


# =========================================================
# MODELS
# =========================================================
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Signal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(32), nullable=False, index=True)
    side = db.Column(db.String(8), nullable=False)  # BUY/SELL
    timeframe = db.Column(db.String(16), nullable=False)  # es: M5, M15, H1
    entry = db.Column(db.Float, nullable=True)
    sl = db.Column(db.Float, nullable=True)
    tp = db.Column(db.Float, nullable=True)
    note = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side,
            "timeframe": self.timeframe,
            "entry": self.entry,
            "sl": self.sl,
            "tp": self.tp,
            "note": self.note,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
        }


# =========================================================
# LOGIN
# =========================================================
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("login"))
        if not current_user.is_admin:
            flash("Accesso negato (admin).", "error")
            return redirect(url_for("dashboard"))
        return fn(*args, **kwargs)
    return wrapper


# =========================================================
# DB INIT + SEED
# =========================================================
def init_db():
    db.create_all()

    # Crea admin di default (solo se non esiste)
    admin_email = "admin@local"
    admin = User.query.filter_by(email=admin_email).first()
    if not admin:
        admin = User(email=admin_email, is_admin=True)
        admin.set_password("admin123")  # cambia subito dopo il primo login
        db.session.add(admin)

    # Seed segnali demo (solo se vuoto)
    if Signal.query.count() == 0:
        demo = [
            Signal(symbol="XAUUSD", side="BUY", timeframe="M15", entry=2045.0, sl=2038.0, tp=2060.0, note="Mean reversion su zona", is_active=True),
            Signal(symbol="EURUSD", side="SELL", timeframe="H1", entry=1.0920, sl=1.0960, tp=1.0840, note="Break + retest", is_active=False),
        ]
        db.session.add_all(demo)

    db.session.commit()


# =========================================================
# ROUTES (PUBLIC)
# =========================================================
@app.route("/")
def home():
    return render_template("home.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        if not email or not password:
            flash("Email e password obbligatori.", "error")
            return render_template("register.html")

        if password != password2:
            flash("Le password non coincidono.", "error")
            return render_template("register.html")

        if User.query.filter_by(email=email).first():
            flash("Email già registrata.", "error")
            return render_template("register.html")

        u = User(email=email, is_admin=False)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()

        flash("Account creato. Ora fai login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        u = User.query.filter_by(email=email).first()
        if not u or not u.check_password(password):
            flash("Credenziali non valide.", "error")
            return render_template("login.html")

        login_user(u)
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# =========================================================
# ROUTES (AUTH)
# =========================================================
@app.route("/dashboard")
@login_required
def dashboard():
    # quick stats
    total = Signal.query.count()
    active = Signal.query.filter_by(is_active=True).count()
    recent = Signal.query.order_by(Signal.created_at.desc()).limit(5).all()

    return render_template(
        "dashboard.html",
        total=total,
        active=active,
        recent=recent,
    )


@app.route("/signals")
@login_required
def signals():
    only_active = request.args.get("active", "1")  # default: attivi
    q = Signal.query
    if only_active == "1":
        q = q.filter_by(is_active=True)
    q = q.order_by(Signal.created_at.desc())
    items = q.all()
    return render_template("signals.html", items=items, only_active=only_active)

@app.route("/expert-advisor")
@login_required
def expert_advisor():
    return render_template("expert_advisor.html")


@app.route("/strumenti")
@login_required
def strumenti():
    return render_template("strumenti.html")


@app.route("/forum")
@login_required
def forum():
    return render_template("forum.html")


@app.route("/news")
@login_required
def news():
    return render_template("news.html")


@app.route("/faq")
@login_required
def faq():
    return render_template("faq.html")


@app.route("/contatti")
@login_required
def contatti():
    return render_template("contatti.html")


# API per grafico/JS (es: ultimi N segnali)
@app.route("/api/signals")
@login_required
def api_signals():
    limit = int(request.args.get("limit", "50"))
    rows = Signal.query.order_by(Signal.created_at.desc()).limit(limit).all()
    return jsonify([r.to_dict() for r in rows])


# =========================================================
# ADMIN CRUD
# =========================================================
@app.route("/admin")
@admin_required
def admin():
    users = User.query.order_by(User.created_at.desc()).all()
    signals_count = Signal.query.count()
    return render_template("admin.html", users=users, signals_count=signals_count)


@app.route("/admin/signals/new", methods=["GET", "POST"])
@admin_required
def signal_new():
    if request.method == "POST":
        symbol = request.form.get("symbol", "").strip().upper()
        side = request.form.get("side", "").strip().upper()
        timeframe = request.form.get("timeframe", "").strip().upper()
        entry = request.form.get("entry", "").strip()
        sl = request.form.get("sl", "").strip()
        tp = request.form.get("tp", "").strip()
        note = request.form.get("note", "").strip()
        is_active = request.form.get("is_active") == "on"

        if side not in ("BUY", "SELL"):
            flash("Side deve essere BUY o SELL.", "error")
            return render_template("signal_new.html")

        def to_float(x):
            if x == "":
                return None
            try:
                return float(x)
            except:
                return None

        s = Signal(
            symbol=symbol or "XAUUSD",
            side=side,
            timeframe=timeframe or "M15",
            entry=to_float(entry),
            sl=to_float(sl),
            tp=to_float(tp),
            note=note or None,
            is_active=is_active,
        )
        db.session.add(s)
        db.session.commit()
        flash("Segnale creato.", "success")
        return redirect(url_for("signals"))

    return render_template("signal_new.html")


@app.route("/admin/signals/<int:sid>/edit", methods=["GET", "POST"])
@admin_required
def signal_edit(sid):
    s = db.session.get(Signal, sid)
    if not s:
        flash("Segnale non trovato.", "error")
        return redirect(url_for("signals"))

    if request.method == "POST":
        s.symbol = request.form.get("symbol", s.symbol).strip().upper()
        s.side = request.form.get("side", s.side).strip().upper()
        s.timeframe = request.form.get("timeframe", s.timeframe).strip().upper()

        def to_float_keep(x, old):
            x = (x or "").strip()
            if x == "":
                return None
            try:
                return float(x)
            except:
                return old

        s.entry = to_float_keep(request.form.get("entry"), s.entry)
        s.sl = to_float_keep(request.form.get("sl"), s.sl)
        s.tp = to_float_keep(request.form.get("tp"), s.tp)
        s.note = request.form.get("note", "").strip() or None
        s.is_active = request.form.get("is_active") == "on"

        if s.side not in ("BUY", "SELL"):
            flash("Side deve essere BUY o SELL.", "error")
            return render_template("signal_edit.html", s=s)

        db.session.commit()
        flash("Segnale aggiornato.", "success")
        return redirect(url_for("signals"))

    return render_template("signal_edit.html", s=s)


@app.route("/admin/signals/<int:sid>/delete", methods=["POST"])
@admin_required
def signal_delete(sid):
    s = db.session.get(Signal, sid)
    if not s:
        flash("Segnale non trovato.", "error")
        return redirect(url_for("signals"))

    db.session.delete(s)
    db.session.commit()
    flash("Segnale eliminato.", "success")
    return redirect(url_for("signals"))


# =========================================================
# MAIN
# =========================================================
if __name__ == "__main__":
    with app.app_context():
        init_db()

    # Avvio server locale
    app.run(host="127.0.0.1", port=5000, debug=True)
