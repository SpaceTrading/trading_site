import os
from datetime import datetime, timedelta
from functools import wraps
import requests
import time
import yfinance as yf
import pandas as pd
import numpy as np
import re
import resend
import secrets
from sicurezza.firewall import check_request
from sicurezza.ip_tracker import register_failure, register_success
from sicurezza.turnstile import verify_turnstile
from flask_babel import Babel, gettext as _

resend.api_key = os.environ.get("RESEND_API_KEY")

from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, session
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

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(INSTANCE_DIR, "app.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# Limite massimo upload file: 20 MB
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

if os.environ.get("RENDER"):
    app.config["SESSION_COOKIE_SECURE"] = True

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

# =========================================================
# I18N / MULTILINGUA
# =========================================================
SUPPORTED_LANGUAGES = {
    "it": "Italiano",
    "en": "English",
    "fr": "Français",
    "es": "Español",
    "de": "Deutsch",
    "pt": "Português",
}

app.config["BABEL_DEFAULT_LOCALE"] = "it"
app.config["BABEL_TRANSLATION_DIRECTORIES"] = "translations"


def get_locale():
    lang = session.get("lang")

    if lang in SUPPORTED_LANGUAGES:
        return lang

    best = request.accept_languages.best_match(list(SUPPORTED_LANGUAGES.keys()))
    return best or "it"


babel = Babel(app, locale_selector=get_locale)

@app.context_processor
def inject_i18n():
    return {
        "supported_languages": SUPPORTED_LANGUAGES,
        "current_language": get_locale(),
    }


# =========================================================
# CONTATTI
# =========================================================
@app.route('/contatti', methods=['GET', 'POST'])
def contatti():
    print("ROUTE CONTATTI ATTIVA!!!")

    if request.method == 'POST':
        oggetto = request.form.get('oggetto')
        email = request.form.get('email')
        messaggio = request.form.get('messaggio')

        print("NUOVO MESSAGGIO:")
        print(email, oggetto, messaggio)
        
        send_email(email, oggetto, messaggio)

        return render_template('contatti.html', success=True), 200

    return render_template('contatti.html')

def send_email(email, oggetto, messaggio):

    try:
        resend.Emails.send({
            "from": "onboarding@resend.dev",
            "to": ["andrea.pic2018@libero.it"],
            "subject": f"[Contatti] {oggetto}",
            "html": f"""
                <h3>Nuovo messaggio dal sito</h3>
                <p><strong>Email:</strong> {email}</p>
                <p><strong>Oggetto:</strong> {oggetto}</p>
                <p><strong>Messaggio:</strong><br>{messaggio}</p>
            """
        })

        print("EMAIL INVIATA")

    except Exception as e:
        print("ERRORE EMAIL:", e)

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


class PasswordResetToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    token = db.Column(db.String(255), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref="password_reset_tokens")
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
    
class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(180), unique=True, nullable=False, index=True)
    ticker = db.Column(db.String(32), unique=True, nullable=True, index=True)
    sector = db.Column(db.String(80), index=True)
    market_cap = db.Column(db.Float)
    last_updated = db.Column(db.DateTime)
    
class MarketCapHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False, index=True)
    market_cap = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
class Ownership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False, index=True)
    target_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False, index=True)
    percentage = db.Column(db.Float, nullable=False)

    source = db.relationship("Company", foreign_keys=[source_id])
    target = db.relationship("Company", foreign_keys=[target_id])

    def to_dict(self):
        return {
            "source": self.source_id,
            "target": self.target_id,
            "value": self.percentage
        }

# =========================================================
# PRODUCT / LICENSING MODELS
# =========================================================

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Esempio: "Strategy Pegasus"
    name = db.Column(db.String(180), nullable=False)

    # Esempio: "strategy_pegasus"
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)

    # Esempio: "mql5", "python_tool", "web_tool"
    platform = db.Column(db.String(50), nullable=False, default="mql5")

    description = db.Column(db.Text, nullable=True)

    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    versions = db.relationship(
        "ProductVersion",
        backref="product",
        lazy=True,
        cascade="all, delete-orphan"
    )


class ProductVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("product.id"),
        nullable=False,
        index=True
    )

    # Esempio: "1.0"
    version = db.Column(db.String(40), nullable=False)

    # Percorso relativo privato:
    # strategy_pegasus/v1.0/StrategyPegasus.ex5
    file_path = db.Column(db.String(255), nullable=False)

    # File opzionali
    set_file_path = db.Column(db.String(255), nullable=True)
    manual_path = db.Column(db.String(255), nullable=True)
    changelog_path = db.Column(db.String(255), nullable=True)

    is_latest = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class License(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True,
        index=True
    )

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("product.id"),
        nullable=False,
        index=True
    )

    # Chiave che l'utente inserirà nell'EA
    license_key = db.Column(db.String(255), unique=True, nullable=False, index=True)

    # Account MT5 autorizzato
    mt5_account = db.Column(db.String(80), nullable=True, index=True)

    # Broker/server opzionale
    mt5_server = db.Column(db.String(180), nullable=True)

    # active / expired / revoked / pending
    status = db.Column(db.String(40), default="active", nullable=False, index=True)

    starts_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)

    last_check_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref="licenses")
    product = db.relationship("Product", backref="licenses")


class LicenseCheckLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    license_id = db.Column(
        db.Integer,
        db.ForeignKey("license.id"),
        nullable=True,
        index=True
    )

    product_slug = db.Column(db.String(120), nullable=True, index=True)
    license_key = db.Column(db.String(255), nullable=True, index=True)

    mt5_account = db.Column(db.String(80), nullable=True)
    mt5_server = db.Column(db.String(180), nullable=True)

    ip_address = db.Column(db.String(80), nullable=True)

    # OK / BLOCK
    result = db.Column(db.String(40), nullable=False)

    # LICENSE_OK / LICENSE_EXPIRED / ACCOUNT_MISMATCH / ecc.
    reason = db.Column(db.String(120), nullable=False)

    checked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    license = db.relationship("License", backref="check_logs")
    
# =========================================================
# BLUEPRINTS
# =========================================================
from licensing.routes import licensing_bp
app.register_blueprint(licensing_bp)

@app.route("/lab/converter")
@login_required
def converter():
    return render_template("forex_converter.html")

# =========================================================
# API-LIVE
# =========================================================

@app.route("/api/convert")
@login_required
def api_convert():

    try:
        from_currency = request.args.get("from")
        to_currency = request.args.get("to")
        amount = float(request.args.get("amount", 1))

        url = f"https://open.er-api.com/v6/latest/{from_currency}"

        response = requests.get(url, timeout=5)
        data = response.json()

        rate = data.get("rates", {}).get(to_currency)

        if not rate:
            return jsonify({"error": "Valuta non valida"})

        result = amount * rate

        return jsonify({
            "result": round(result, 5)
        })

    except Exception as e:
        print("API ERROR:", e)
        return jsonify({"error": "Errore API"})
    
    
@app.route("/api/version")
def version():
    return {"version": "MC_FIX_2026_04_30_V3"}

@app.route("/lab/rolling-analysis")
@login_required
def rolling_analysis_page():
    return render_template("rolling_analysis.html")

# =========================================================
# SIMULATORE MONTE-CARLO
# =========================================================

@app.route("/api/montecarlo/upload", methods=["POST"])
@login_required
def montecarlo_upload():

    print("AUTH:", current_user.is_authenticated)
    print("VERSION MONTECARLO V2 - LIVE CHECK")

    try:
        # =========================
        # FILE CHECK
        # =========================
        if "file" not in request.files:
            print("DEBUG: no file in request")
            return jsonify({"error": "no file"}), 400

        file = request.files["file"]

        if file.filename == "":
            print("DEBUG: empty filename")
            return jsonify({"error": "empty filename"}), 400

        print("DEBUG filename:", file.filename)

        # =========================
        # PARSING
        # =========================
        file.seek(0)
        trades = extract_trades_from_file(file)

        print("DEBUG extracted trades:", len(trades) if trades else 0)

        if not trades or len(trades) == 0:
            return jsonify({"error": "no trades found"}), 200

        # =========================
        # SUCCESS
        # =========================
        return jsonify({
            "status": "success",
            "trades": trades
        }), 200

    except Exception as e:
        print("UPLOAD ERROR:", str(e))
        return jsonify({"error": "upload error"}), 500

    
    
@app.route("/api/montecarlo/run", methods=["POST"])
#@login_required
def montecarlo_run():
    if not current_user.is_authenticated:
        return jsonify({"error": "not authenticated"}), 401    

    try:
        data = request.json
        trades = data.get("trades", [])

        if not isinstance(trades, list):
            return jsonify({"error": "invalid trades"})
        
        try:
            trades = [float(x) for x in trades]
        except:
            return jsonify({"error": "trades must be numbers"})
        
        if len(trades) < 2:
            return jsonify({"error": "not enough trades"})

        sims = int(data.get("simulations", 1000))
        sims = max(10, min(sims, 10000))

        # =========================
        # ORIGINAL EQUITY
        # =========================
        original_equity = np.cumsum(trades).tolist()

        # =========================
        # MONTE CARLO
        # =========================
        # =========================
        # MONTE CARLO - SHUFFLE
        # Sequence Risk / Drawdown Risk
        # =========================
        all_equities = []
        drawdowns = []
        recovery_times = []
    
        def time_to_recovery(eq):
            peak = eq[0]
            current_duration = 0
            max_duration = 0
    
            for x in eq:
                if x >= peak:
                    peak = x
                    current_duration = 0
                else:
                    current_duration += 1
                    max_duration = max(max_duration, current_duration)
    
            return max_duration
    
        def ulcer_index_from_equity(eq):
            peak = eq[0]
            dd_points = []
    
            for x in eq:
                if x > peak:
                    peak = x
    
                dd = peak - x
                dd_points.append(dd)
    
            return float(np.sqrt(np.mean(np.square(dd_points))))
    
        ulcer_values = []
    
        for _ in range(sims):
            shuffled = trades.copy()
            np.random.shuffle(shuffled)
    
            equity = np.cumsum(shuffled)
    
            all_equities.append(equity)
            drawdowns.append(float(max_drawdown(equity)))
            recovery_times.append(int(time_to_recovery(equity)))
            ulcer_values.append(ulcer_index_from_equity(equity))
    
        # Ordine corretto: per drawdown, NON per profitto finale
        sorted_by_dd_indices = np.argsort(drawdowns)
    
        best_5_equity = all_equities[sorted_by_dd_indices[int(sims * 0.05)]].tolist()
        median_equity = all_equities[sorted_by_dd_indices[int(sims * 0.50)]].tolist()
        worst_95_equity = all_equities[sorted_by_dd_indices[int(sims * 0.95)]].tolist()
    
        # =========================
        # BOOTSTRAP - Outcome Risk
        # =========================
        bootstrap_equities = []
        bootstrap_profits = []
    
        for _ in range(sims):
            resampled = np.random.choice(trades, size=len(trades), replace=True)
            equity = np.cumsum(resampled)
    
            bootstrap_equities.append(equity)
            bootstrap_profits.append(float(equity[-1]))
    
        # =========================
        # SAMPLE CURVES (50)
        # =========================
        sample_size = min(50, sims)
        sample_indices = np.random.choice(range(sims), size=sample_size, replace=False)
        samples = [all_equities[i].tolist() for i in sample_indices]
    
        # =========================
        # METRICHE BASE
        # =========================
        median_profit = float(np.median(bootstrap_profits))
        avg_profit = float(np.mean(bootstrap_profits))
        worst_profit = float(np.min(bootstrap_profits))
        best_profit = float(np.max(bootstrap_profits))
    
        median_dd = float(max_drawdown(median_equity))
    
        # =========================
        # ADVANCED METRICS
        # =========================
        returns = np.array(trades, dtype=float)
    
        mean_ret = float(np.mean(returns))
        std_ret = float(np.std(returns))
    
        downside = returns[returns < 0]
        down_std = float(np.std(downside)) if len(downside) > 0 else 0.0
    
        # Nota: sono PnL Sharpe-like / Sortino-like, non Sharpe accademici su rendimenti %
        sharpe = mean_ret / std_ret if std_ret != 0 else 0.0
        sortino = mean_ret / down_std if down_std != 0 else 0.0
    
        max_dd = float(np.max(drawdowns)) if drawdowns else 0.0
        total_profit = float(np.sum(trades))
    
        calmar = total_profit / max_dd if max_dd != 0 else 0.0
        ulcer_index = float(np.mean(ulcer_values)) if ulcer_values else 0.0
    
        # CDaR = media del peggior 5% dei drawdown simulati
        dd_array = np.array(drawdowns, dtype=float)
        threshold = np.percentile(dd_array, 95)
        cdar = float(np.mean(dd_array[dd_array >= threshold])) if len(dd_array) else 0.0
    
        # Probability of Ruin corretta: rovina se la curva tocca la soglia in qualunque punto
        ruin_threshold = -abs(total_profit) * 0.5
        ruin_count = sum(1 for eq in bootstrap_equities if np.any(eq <= ruin_threshold))
        por = ruin_count / sims if sims > 0 else 0.0
        
        # =========================
        # ADDITIONAL RISK METRICS (SAFE)
        # =========================
        bootstrap_array = np.array(bootstrap_profits)
        
        twv = float(np.std(bootstrap_array)) if len(bootstrap_array) else 0.0
        var_95 = float(np.percentile(bootstrap_array, 5)) if len(bootstrap_array) else 0.0
        
        cvar = float(np.mean(bootstrap_array[bootstrap_array <= var_95])) if len(bootstrap_array) else 0.0        
        
        # =========================
        # OVERFITTING METRICS (SAFE)
        # =========================
        
        # 1. Noise Sensitivity Test
        noise_level = std_ret * 0.1  # 10% rumore rispetto volatilità
        
        noisy_returns = returns + np.random.normal(0, noise_level, size=len(returns))
        
        mean_noisy = float(np.mean(noisy_returns))
        std_noisy = float(np.std(noisy_returns))
        
        sharpe_noisy = mean_noisy / std_noisy if std_noisy != 0 else 0.0
        
        epsilon = 1e-6
        noise_sensitivity = sharpe_noisy / (sharpe + epsilon)
        
        
        # 2. Sharpe Haircut (prudenziale)
        haircut_factor = 0.5
        sharpe_haircut = sharpe * haircut_factor
        
        
        # 3. Robustness Ratio (trade vs parametri)
        estimated_params = 10  # default prudenziale
        robustness_ratio = len(trades) / estimated_params if estimated_params > 0 else 0.0        

        # =========================
        # OUTPUT
        # =========================
        return jsonify({
            "status": "success",
        
            "original_equity": original_equity,
            "median_equity": median_equity,
            "worst_95_equity": worst_95_equity,
            "best_5_equity": best_5_equity,
        
            "samples": samples,
        
            # QUESTI DEVONO STARE QUI (TOP LEVEL)
            "bootstrap_samples": [b.tolist() for b in bootstrap_equities[:50]],
            "drawdowns": drawdowns,
            "recovery_times": recovery_times,
        
            "advanced_metrics": {
                "sharpe": float(sharpe),
                "sortino": float(sortino),
                "calmar": float(calmar),
                "ulcer_index": float(ulcer_index),
                "cdar": float(cdar),
                "probability_of_ruin": float(por),
            
                "twv": twv,
                "var_95": var_95,
                "cvar": cvar,
                
                # OVERFITTING
                "noise_sensitivity": float(noise_sensitivity),
                "sharpe_haircut": float(sharpe_haircut),
                "robustness_ratio": float(robustness_ratio)                
            },
        
            # METRICHE BASE RESTANO QUI
            "metrics": {
                "avg_profit": avg_profit,
                "median_profit": median_profit,
                "best_profit": best_profit,
                "worst_profit": worst_profit,
                "median_dd": median_dd,
                
            },
        })

    except Exception as e:
        print("MC ERROR:", e)
        return jsonify({"error": "simulation error"})
    
    

def max_drawdown(equity):
    peak = equity[0]
    max_dd = 0

    for x in equity:
        if x > peak:
            peak = x

        dd = peak - x
        if dd > max_dd:
            max_dd = dd

    return max_dd

def extract_trades_from_file(file):
    file.seek(0)
    filename = file.filename.lower()

    try:
        import pandas as pd
        from io import StringIO

        def normalize(x):
            import pandas as pd
            if pd.isna(x):
                return ""
            return str(x).strip().lower()

        def clean_number(x):
            if x is None:
                return None
            s = str(x).strip()
            s = s.replace("\xa0", " ")
            s = s.replace(" ", "")
            s = s.replace(",", ".")
            return pd.to_numeric(s, errors="coerce")

        def extract_affari_from_df(df):
            header_row = None

            for i, row in df.iterrows():
                values = [normalize(v) for v in row.values if normalize(v)]
                row_text = " ".join(values)
                
                # DEBUG HARD
                if i < 20:
                    print(f"ROW {i}:", row_text)

                if (
                    any("direzione" in v for v in values)
                    and any("profit" in v for v in values)
                ):
                    header_row = i
                    break

            if header_row is None:
                return []

            columns = [normalize(v) for v in df.iloc[header_row].values]
            data = df.iloc[header_row + 1:].copy()
            data.columns = columns

            print("DEBUG AFFARI columns:", data.columns)

            direction_col = None
            profit_col = None

            for c in data.columns:
                c_norm = normalize(c)

                if "direzione" in c_norm:
                    direction_col = c

                if "profitto" in c_norm or "profit" in c_norm:
                    profit_col = c

            if not direction_col or not profit_col:
                print("DEBUG: colonne affari insufficienti")
                return []

            data[direction_col] = data[direction_col].astype(str).str.lower().str.strip()

            # Prendiamo SOLO i deal chiusi: direction = out
            closed = data[data[direction_col] == "out"].copy()

            profits = closed[profit_col].apply(clean_number).dropna()

            print("DEBUG AFFARI trades OUT trovati:", len(profits))

            return profits.tolist()

        # =========================
        # HTML MT5
        # =========================
        if filename.endswith(".html"):
            file.seek(0)
            content = file.read()

            try:
                html = content.decode("utf-16le")
                print("DEBUG: letto come UTF-16LE")
            except Exception as e:
                print("DEBUG UTF-16 fallito:", e)
                html = content.decode("utf-8", errors="ignore")
                print("DEBUG: letto come UTF-8")

            tables = pd.read_html(StringIO(html))
            print("DEBUG: tabelle trovate =", len(tables))

            for i, df in enumerate(tables):
                print(f"DEBUG tabella {i} RAW shape:", df.shape)

                try:
                    trades = extract_affari_from_df(df)

                    if trades:
                        print(f"DEBUG tabella {i} AFFARI trades trovati:", len(trades))
                        return trades

                except Exception as e:
                    print(f"DEBUG tabella {i} skip:", e)
                    continue

            print("DEBUG: nessuna tabella AFFARI valida trovata")
            return []

        # =========================
        # XLSX
        # =========================
        elif filename.endswith(".xlsx"):
            file.seek(0)
            df = pd.read_excel(file, header=None, engine="openpyxl")

            # FIX cross-platform (Windows vs Linux)
            df = df.fillna("")
            df = df.astype(str)
            print("DEBUG XLSX RAW shape:", df.shape)
            return extract_affari_from_df(df)

        # =========================
        # CSV
        # =========================
        elif filename.endswith(".csv"):
            file.seek(0)
            df = pd.read_csv(file, header=None)
            print("DEBUG CSV RAW shape:", df.shape)
            return extract_affari_from_df(df)

        else:
            return []

    except Exception as e:
        print("PARSING ERROR:", e)
        return []
    
    
@app.route("/api/rolling/run", methods=["POST"])
def rolling_analysis_run():

    if not current_user.is_authenticated:
        return jsonify({"error": "not authenticated"}), 401

    try:
        data = request.json or {}

        trades = data.get("trades", [])
        window_size = int(data.get("window", 50))
        step = int(data.get("step", 10))

        # =========================
        # VALIDAZIONE
        # =========================
        if not isinstance(trades, list):
            return jsonify({"error": "invalid trades"})

        try:
            trades = [float(x) for x in trades]
        except:
            return jsonify({"error": "trades must be numbers"})

        if window_size < 5:
            return jsonify({"error": "window too small"})

        if step < 1:
            return jsonify({"error": "step must be >= 1"})

        if len(trades) < window_size:
            return jsonify({"error": "not enough trades for selected window"})

        # =========================
        # HELPERS
        # =========================
        def safe_float(x):
            try:
                if x is None:
                    return None
                x = float(x)
                if np.isnan(x) or np.isinf(x):
                    return None
                return x
            except:
                return None

        def local_equity_curve(chunk):
            # parte da 0 per misurare correttamente drawdown anche se il primo trade è negativo
            return np.concatenate([[0.0], np.cumsum(chunk)])

        def local_max_drawdown(eq):
            peak = eq[0]
            max_dd = 0.0

            for x in eq:
                if x > peak:
                    peak = x

                dd = peak - x
                if dd > max_dd:
                    max_dd = dd

            return float(max_dd)

        def local_ulcer_index(eq):
            peak = eq[0]
            dd_points = []

            for x in eq:
                if x > peak:
                    peak = x

                dd = peak - x
                dd_points.append(dd)

            return float(np.sqrt(np.mean(np.square(dd_points)))) if dd_points else 0.0

        # =========================
        # ROLLING WINDOWS
        # =========================
        windows = []

        rolling_profit = []
        rolling_drawdown = []
        rolling_winrate = []
        rolling_profit_factor = []
        rolling_ulcer = []

        for start in range(0, len(trades) - window_size + 1, step):

            end = start + window_size
            chunk = np.array(trades[start:end], dtype=float)

            eq = local_equity_curve(chunk)

            profit = float(np.sum(chunk))
            dd = local_max_drawdown(eq)
            ulcer = local_ulcer_index(eq)

            wins = chunk[chunk > 0]
            losses = chunk[chunk < 0]

            winrate = float(len(wins) / len(chunk) * 100) if len(chunk) else 0.0

            gross_profit = float(np.sum(wins)) if len(wins) else 0.0
            gross_loss = float(np.sum(losses)) if len(losses) else 0.0

            if gross_loss < 0:
                profit_factor = gross_profit / abs(gross_loss)
            else:
                profit_factor = None

            item = {
                "index": len(windows),
                "start_trade": start + 1,
                "end_trade": end,
                "profit": safe_float(profit),
                "drawdown": safe_float(dd),
                "winrate": safe_float(winrate),
                "profit_factor": safe_float(profit_factor),
                "ulcer_index": safe_float(ulcer),
            }

            windows.append(item)

            rolling_profit.append(safe_float(profit))
            rolling_drawdown.append(safe_float(dd))
            rolling_winrate.append(safe_float(winrate))
            rolling_profit_factor.append(safe_float(profit_factor))
            rolling_ulcer.append(safe_float(ulcer))

        if not windows:
            return jsonify({"error": "no rolling windows generated"})

        # =========================
        # SUMMARY
        # =========================
        profit_array = np.array([x for x in rolling_profit if x is not None], dtype=float)
        dd_array = np.array([x for x in rolling_drawdown if x is not None], dtype=float)

        avg_rolling_profit = float(np.mean(profit_array)) if len(profit_array) else 0.0
        worst_rolling_profit = float(np.min(profit_array)) if len(profit_array) else 0.0
        best_rolling_profit = float(np.max(profit_array)) if len(profit_array) else 0.0
        rolling_profit_volatility = float(np.std(profit_array)) if len(profit_array) else 0.0

        negative_windows_pct = float(np.mean(profit_array < 0) * 100) if len(profit_array) else 0.0

        worst_rolling_drawdown = float(np.max(dd_array)) if len(dd_array) else 0.0
        avg_rolling_drawdown = float(np.mean(dd_array)) if len(dd_array) else 0.0

        stability_ratio = (
            avg_rolling_profit / rolling_profit_volatility
            if rolling_profit_volatility != 0
            else 0.0
        )

        # Profit concentration:
        # quota del profitto positivo totale spiegata dal top 10% delle finestre migliori
        positive_profits = profit_array[profit_array > 0]
        if len(positive_profits) > 0:
            top_n = max(1, int(np.ceil(len(positive_profits) * 0.10)))
            sorted_pos = np.sort(positive_profits)[::-1]
            top_profit = float(np.sum(sorted_pos[:top_n]))
            total_positive_profit = float(np.sum(positive_profits))
            profit_concentration = (
                top_profit / total_positive_profit * 100
                if total_positive_profit > 0
                else 0.0
            )
        else:
            profit_concentration = 0.0

        # Degradation score:
        # confronto tra primo 30% e ultimo 30% delle finestre.
        n = len(profit_array)
        k = max(1, int(np.ceil(n * 0.30)))

        first_avg = float(np.mean(profit_array[:k])) if n else 0.0
        last_avg = float(np.mean(profit_array[-k:])) if n else 0.0

        if abs(first_avg) > 1e-9:
            degradation_score = ((last_avg - first_avg) / abs(first_avg)) * 100
        else:
            degradation_score = 0.0

        # =========================
        # INTERPRETAZIONE
        # =========================
        flags = []

        if negative_windows_pct > 30:
            flags.append("alta percentuale di finestre negative")

        if profit_concentration > 55:
            flags.append("profitto molto concentrato in poche finestre")

        if degradation_score < -30:
            flags.append("possibile deterioramento nella parte finale")

        if stability_ratio < 0.5:
            flags.append("bassa stabilità dei profitti rolling")

        if worst_rolling_drawdown > abs(avg_rolling_profit) * 2 and avg_rolling_profit > 0:
            flags.append("drawdown rolling elevato rispetto al profitto medio")

        if not flags:
            interpretation = (
                "La strategia appare relativamente stabile sulle finestre analizzate. "
                "I profitti rolling risultano distribuiti in modo accettabile e non emergono segnali forti di deterioramento."
            )
            regime_label = "STABILE"
        else:
            interpretation = (
                "La strategia mostra potenziali fragilità temporali: "
                + ", ".join(flags)
                + ". Conviene confrontare questa analisi con Monte Carlo, drawdown e distribuzione dei trade."
            )

            if profit_concentration > 55:
                regime_label = "CONCENTRATA / REGIME-DEPENDENT"
            elif degradation_score < -30:
                regime_label = "IN DETERIORAMENTO"
            else:
                regime_label = "INSTABILE"

        summary = {
            "avg_rolling_profit": safe_float(avg_rolling_profit),
            "worst_rolling_profit": safe_float(worst_rolling_profit),
            "best_rolling_profit": safe_float(best_rolling_profit),
            "negative_windows_pct": safe_float(negative_windows_pct),
            "rolling_profit_volatility": safe_float(rolling_profit_volatility),
            "worst_rolling_drawdown": safe_float(worst_rolling_drawdown),
            "avg_rolling_drawdown": safe_float(avg_rolling_drawdown),
            "stability_ratio": safe_float(stability_ratio),
            "profit_concentration": safe_float(profit_concentration),
            "degradation_score": safe_float(degradation_score),
        }

        return jsonify({
            "status": "success",
            "window_size": window_size,
            "step": step,
            "total_trades": len(trades),
            "windows": windows,

            "series": {
                "rolling_profit": rolling_profit,
                "rolling_drawdown": rolling_drawdown,
                "rolling_winrate": rolling_winrate,
                "rolling_profit_factor": rolling_profit_factor,
                "rolling_ulcer": rolling_ulcer,
            },

            "summary": summary,

            "interpretation": {
                "label": regime_label,
                "text": interpretation,
                "flags": flags,
            }
        })

    except Exception as e:
        print("ROLLING ERROR:", e)
        return jsonify({"error": "rolling error"})

@app.route("/api/correlations")
@login_required
def api_correlations():

    try:
        base_pair = request.args.get("pair", "EURUSD").upper()
        tf = request.args.get("tf", "1h")
        periods = int(request.args.get("periods", 50))
        # clamp sicurezza
        periods = max(1, min(periods, 500))        

        # ===== ASSET COMPLETI =====
        yahoo_symbols = {
            # FOREX MAJOR
            "EURUSD": "EURUSD=X",
            "GBPUSD": "GBPUSD=X",
            "USDJPY": "USDJPY=X",
            "USDCHF": "USDCHF=X",
            "AUDUSD": "AUDUSD=X",
            "USDCAD": "USDCAD=X",
            "NZDUSD": "NZDUSD=X",

            # FOREX MINOR / CROSS
            "EURJPY": "EURJPY=X",
            "GBPJPY": "GBPJPY=X",
            "EURGBP": "EURGBP=X",
            "AUDJPY": "AUDJPY=X",
            "CHFJPY": "CHFJPY=X",
            "EURAUD": "EURAUD=X",
            "GBPAUD": "GBPAUD=X",

            # COMMODITIES / FUTURES
            "XAUUSD": "GC=F",
            "XAGUSD": "SI=F",
            "WTI": "CL=F",
            "BRENT": "BZ=F",

            # CRYPTO
            "BTCUSD": "BTC-USD",
            "ETHUSD": "ETH-USD",
            "SOLUSD": "SOL-USD",
            "XRPUSD": "XRP-USD",
            "ADAUSD": "ADA-USD",
        }

        base_symbol = yahoo_symbols.get(base_pair)

        if not base_symbol:
            return jsonify({"error": "invalid base pair"})

        interval_map = {
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",  
            "1h": "60m",
            "4h": "60m",
            "1d": "1d",
            "1wk": "1wk",   
            "1mo": "1mo"    
        }

        interval = interval_map.get(tf, "60m")

        # ===== PERIODO STORICO IN BASE AL TIMEFRAME =====
        if tf in ["5m", "15m", "30m"]:
            history_period = "60d"
        elif tf in ["1h", "4h"]:
            history_period = "730d"
        elif tf == "1d":
            history_period = "5y"
        elif tf == "1wk":
            history_period = "10y"
        elif tf == "1mo":
            history_period = "max"
        else:
            history_period = "1y"
        
        raw = yf.download(
            list(yahoo_symbols.values()),
            period=history_period,
            interval=interval,
            progress=False,
            auto_adjust=False
        )

        if raw.empty:
            return jsonify({"error": "no raw data"})

        if "Close" not in raw:
            return jsonify({"error": "no close data"})

        data = raw["Close"].dropna(how="all")

        if data.empty:
            return jsonify({"error": "no data"})

        if base_symbol not in data.columns:
            return jsonify({"error": "base not found"})

        base_series = data[base_symbol].pct_change(fill_method=None).dropna()

        results = []

        for pair, symbol in yahoo_symbols.items():

            if symbol not in data.columns:
                continue

            series = data[symbol].pct_change(fill_method=None).dropna()
            combined = pd.concat([base_series, series], axis=1).dropna()

            if len(combined) < periods:
                continue

            slice_data = combined.iloc[-periods:]
            
            # evita serie costanti o vuote
            if slice_data.iloc[:, 0].std() == 0 or slice_data.iloc[:, 1].std() == 0:
                continue
            
            corr = slice_data.iloc[:, 0].corr(slice_data.iloc[:, 1])
            
            if pd.isna(corr):
                continue

            results.append({
                "pair": pair,
                "value": float(corr)
            })

        results.sort(key=lambda x: x["value"], reverse=True)

        return jsonify(results)

    except Exception as e:
        print("CORRELATION ERROR:", e)
        return jsonify({"error": "calculation error"})
    
@app.route("/api/crypto")
@login_required
def api_crypto():

    try:
        # ===== MAPPING CRYPTO =====
        crypto_map = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
            "XRP": "ripple",
            "ADA": "cardano"
        }

        coin_input = request.args.get("coin", "BTC").upper()
        if coin_input not in crypto_map:
            return jsonify({"error": "Crypto non supportata"})
        
        coin = crypto_map[coin_input]

        vs = request.args.get("vs", "usd").lower()

        # ===== API CALL =====
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies={vs}"

        # ===== CACHE SEMPLICE =====
        
        if not hasattr(api_crypto, "cache"):
            api_crypto.cache = {}
        
        CACHE_TTL = 10  # secondi
        
        def get_cached(key):
            entry = api_crypto.cache.get(key)
            if entry and time.time() - entry["ts"] < CACHE_TTL:
                return entry["value"]
            return None
        
        def set_cache(key, value):
            api_crypto.cache[key] = {"value": value, "ts": time.time()}
        
        
        cache_key = f"{coin}_{vs}"
        
        # ===== 1. USA CACHE =====
        cached_price = get_cached(cache_key)
        if cached_price:
            return jsonify({"result": cached_price, "cached": True})
        
        
        # ===== 2. COINGECKO =====
        try:
            res = requests.get(url, timeout=3)
            data = res.json()
        
            price = data.get(coin, {}).get(vs)
        
            if price is not None:
                price = float(price)
                set_cache(cache_key, price)
                return jsonify({"result": price, "source": "coingecko"})
        
        except Exception as e:
            print("COINGECKO ERROR:", e)
        
        
        # ===== 3. FALLBACK (BINANCE) =====
        try:
            symbol_map = {
                "BTC": "BTCUSDT",
                "ETH": "ETHUSDT",
                "SOL": "SOLUSDT",
                "XRP": "XRPUSDT",
                "ADA": "ADAUSDT"
            }
        
            symbol = symbol_map.get(coin_input)
        
            if not symbol:
                raise Exception("No symbol mapping")
        
            binance_url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
            
            res = requests.get(binance_url, timeout=3)
        
            if res.status_code != 200:
                raise Exception("Binance HTTP error")
        
            data = res.json()
        
            if "price" not in data:
                raise Exception("Invalid Binance response")
        
            price = float(data["price"])
        
            set_cache(cache_key, price)
        
            print("BINANCE OK:", symbol, price)
        
            return jsonify({"result": price, "source": "binance"})
        
        except Exception as e:
            print("BINANCE ERROR:", e)
        
        
        # ===== 4. FALLIMENTO TOTALE =====
        return jsonify({"error": "all providers failed"})

    except Exception as e:
        print("CRYPTO ERROR:", e)
        return jsonify({"error": "crypto error"})

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

def calculate_trade(balance, lot, entry, target, sl, trade_type, pair):

    pair = pair.upper()
    
    # ===== VALIDAZIONE =====
    if balance <= 0 or lot <= 0:
        return {"error": "Valori non validi"}    

    # ===== JPY PAIRS =====
    jpy_pairs = ["USDJPY","EURJPY","GBPJPY","CADJPY","CHFJPY", "AUDJPY", "NZDJPY"]

    if pair in jpy_pairs:
        pip_size = 0.01
        pip_value = lot * 10

    # ===== GOLD =====
    elif pair == "XAUUSD":
        pip_size = 0.1
        pip_value = lot * 10

    # ===== SILVER =====
    elif pair == "XAGUSD":
        pip_size = 0.01
        pip_value = lot * 50

    # ===== OIL =====
    elif pair in ["WTI", "BRENT"]:
        pip_size = 0.01
        pip_value = lot * 10

    # ===== FOREX STANDARD =====
    else:
        pip_size = 0.0001
        pip_value = lot * 10

    # ===== CALCOLO =====
    if trade_type == "buy":
        pips_profit = (target - entry) / pip_size
        pips_loss = (entry - sl) / pip_size
    else:
        pips_profit = (entry - target) / pip_size
        pips_loss = (sl - entry) / pip_size

    if pips_loss <= 0:
        return {
            "error": "Stop loss non valido"
        }

    profit = pips_profit * pip_value
    loss = pips_loss * pip_value
    rr = profit / loss if loss != 0 else 0
    risk = (loss / balance) * 100 if balance != 0 else 0
    ret = (profit / balance) * 100 if balance != 0 else 0    
    
    return {
        "profit": round(profit, 2),
        "loss": round(loss, 2),
        "risk": round(risk, 2),
        "return": round(ret, 2),
        "rr": round(rr, 2)
    }

@app.route("/lab/correlazioni")
@login_required
def correlation():
    return render_template("correlazioni.html")


@app.route("/lab/montecarlo")
@login_required
def montecarlo_page():
    return render_template("montecarlo.html")

@app.route("/api/market-history/<int:company_id>")
def market_history(company_id):

    rows = (
        MarketCapHistory.query
        .filter_by(company_id=company_id)
        .order_by(MarketCapHistory.timestamp.asc())
        .all()
    )

    data = [
        {
            "timestamp": r.timestamp.isoformat(),
            "market_cap": r.market_cap
        }
        for r in rows
    ]

    return jsonify(data)


@app.route("/market-map")
def market_map():
    return render_template("market_map.html")

@app.route("/api/market-map")
def api_market_map():

    # =========================
    # NODES (companies)
    # =========================
    companies = Company.query.all()

    nodes = []
    for c in companies:
        nodes.append({
            "id": c.id,
            "label": c.name,
            "sector": c.sector,
            "market_cap": c.market_cap or 1
        })

    # =========================
    # LINKS (ownerships)
    # =========================
    ownerships = Ownership.query.all()

    links = []
    for o in ownerships:
        links.append({
            "source": o.source_id,
            "target": o.target_id,
            "value": o.percentage
        })

    return jsonify({
        "nodes": nodes,
        "links": links
    })

@app.route("/api/insider-flow")
def insider_flow():

    import requests

    API_KEY = os.environ.get("FINNHUB_API_KEY", "")
    if not API_KEY:
        return jsonify({"error": "missing api key"}), 500  # tua key finhub

    tickers = ["AAPL", "TSLA", "MSFT", "NVDA", "AMZN"]

    results = []

    for t in tickers:

        try:
            url = f"https://finnhub.io/api/v1/stock/insider-transactions?symbol={t}&token={API_KEY}"
            r = requests.get(url, timeout=5)

            if r.status_code != 200:
                print("HTTP ERROR:", t, r.status_code)
                continue

            data = r.json()

            if "data" not in data or not data["data"]:
                print("NO DATA:", t)
                continue

            # prendiamo più eventi (non solo 5)
            for item in data["data"][:20]:

                code = item.get("transactionCode")

                change = item.get("change") or 0
                price = item.get("transactionPrice") or 0
                value = change * price

                # DEBUG (puoi lasciarlo per ora)
                print("ITEM:", t, code, value)

                # filtro minimo SOLO per evitare spazzatura totale
                if value == 0:
                    continue

                results.append({
                    "ticker": t,
                    "name": item.get("name") or "Unknown",
                    "position": item.get("shareholder") or "Insider",
                    "type": code,
                    "change": change,
                    "price": price,
                    "date": item.get("transactionDate")
                })

        except Exception as e:
            print("ERROR:", t, e)
            continue

    # ordina per valore transazione    
    # 1. ordina per DATA (più recente prima)
    results.sort(
        key=lambda x: datetime.strptime(x["date"], "%Y-%m-%d") if x["date"] else datetime.min,
        reverse=True
    )
    
    # 2. limita output (più recente)
    return jsonify(results[:15])

@app.route("/api/sector-ranking")
def sector_ranking():

    from collections import defaultdict

    # =========================
    # QUERY DB
    # =========================
    companies = Company.query.filter(
        Company.market_cap.isnot(None),
        Company.sector.isnot(None)
    ).all()

    # =========================
    # GROUP BY SECTOR
    # =========================
    sector_map = defaultdict(list)

    for c in companies:

        # safety: evita dati sporchi
        if not c.market_cap or c.market_cap <= 0:
            continue

        sector_map[c.sector].append({
            "name": c.name,
            "ticker": c.ticker,
            "market_cap": float(c.market_cap)
        })

    # =========================
    # SORT + TOP 15
    # =========================
    result = {}

    for sector, comps in sector_map.items():

        # ordina per market cap DESC
        sorted_comps = sorted(
            comps,
            key=lambda x: x["market_cap"],
            reverse=True
        )

        # prendi top 15
        result[sector] = sorted_comps[:15]

    # =========================
    # RETURN JSON
    # =========================
    return jsonify(result)

@app.route("/set-language/<lang_code>")
def set_language(lang_code):
    if lang_code in SUPPORTED_LANGUAGES:
        session["lang"] = lang_code

    return redirect(request.referrer or url_for("home"))

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
        ip = request.remote_addr
        status = check_request(ip)
        
        if status == "blocked":
            flash("Troppi tentativi. Riprova più tardi.", "error")
            return redirect(url_for("home"))        

        # =========================
        # TURNSTILE VERIFICA (PRO)
        # =========================
        token = request.form.get("cf-turnstile-response")
        
        if not token:
            register_failure(ip)
            flash("Verifica anti-bot mancante.", "error")
            return redirect(url_for("home"))
        
        if not verify_turnstile(token, ip):
            register_failure(ip)
            flash("Verifica anti-bot fallita.", "error")
            return redirect(url_for("home"))

        # =========================
        # DATI UTENTE
        # =========================
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        if "@" not in email:
            register_failure(ip)
            flash("Email e password obbligatori.", "error")
            return redirect(url_for("home"))

        if password != password2:
            flash("Le password non coincidono.", "error")
            return redirect(url_for("home"))

        if User.query.filter_by(email=email).first():
            register_failure(ip)
            flash("Email già registrata.", "error")
            return redirect(url_for("home"))

        # =========================
        # CREA UTENTE
        # =========================
        register_success(ip)
        
        u = User(email=email, is_admin=False)
        u.set_password(password)

        db.session.add(u)
        db.session.commit()

        flash("Account creato con successo.", "success")
        return redirect(url_for("home"))

    return render_template("register.html")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    # GET: mostra solo la pagina dove inserire l'email
    if request.method == "GET":
        return render_template("forgot_password.html")

    ip = request.remote_addr
    status = check_request(ip)

    if status == "blocked":
        flash("Troppi tentativi. Riprova più tardi.", "error")
        return redirect(url_for("forgot_password"))

    # POST: processa l'email inserita dall'utente
    email = request.form.get("email", "").strip().lower()

    if not email or "@" not in email or "." not in email:
        register_failure(ip)
        flash("Inserisci una email valida.", "error")
        return redirect(url_for("forgot_password"))

    # Conta ogni richiesta reset valida come tentativo sensibile.
    # Non usiamo register_success qui, altrimenti un bot potrebbe inviare richieste illimitate.
    register_failure(ip)

    user = User.query.filter_by(email=email).first()

    # NON riveliamo se l'email esiste davvero, per evitare enumerazione account
    if user:
        token = secrets.token_urlsafe(32)

        reset = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=datetime.utcnow() + timedelta(minutes=30)
        )

        db.session.add(reset)
        db.session.commit()

        reset_link = url_for("reset_password", token=token, _external=True)

        try:
            resend.Emails.send({
                "from": "onboarding@resend.dev",
                "to": [user.email],
                "subject": "Reset Password",
                "html": f"""
                    <h3>Reset Password</h3>
                    <p>Clicca il link per reimpostare la password:</p>
                    <a href="{reset_link}">{reset_link}</a>
                    <p>Valido per 30 minuti.</p>
                """
            })
        except Exception as e:
            print("EMAIL RESET ERROR:", repr(e))

    flash("Se l'email è registrata, riceverai un link per il reset della password.", "success")
    return redirect(url_for("home"))

@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):

    reset = PasswordResetToken.query.filter_by(token=token).first()

    # ===== VALIDAZIONE TOKEN =====
    if not reset:
        flash("Link non valido.", "error")
        return redirect(url_for("home"))

    if reset.used:
        flash("Link già utilizzato.", "error")
        return redirect(url_for("home"))

    if reset.expires_at < datetime.utcnow():
        flash("Link scaduto.", "error")
        return redirect(url_for("home"))

    user = reset.user
      

    # ===== POST (CAMBIO PASSWORD) =====
    if request.method == "POST":
        ip = request.remote_addr
        
        captcha_token = request.form.get("cf-turnstile-response")
        
        if not captcha_token or not verify_turnstile(captcha_token, ip):
            register_failure(ip)
            flash("Verifica anti-bot fallita.", "error")
            return render_template("login.html")  
        
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        if not password:
            flash("Password obbligatoria.", "error")
            return redirect(request.url)

        if password != password2:
            flash("Le password non coincidono.", "error")
            return redirect(request.url)

        # aggiorna password
        user.set_password(password)

        # invalida token
        reset.used = True

        db.session.commit()

        flash("Password aggiornata. Ora puoi fare login.", "success")
        return redirect(url_for("home"))

    # ===== GET (MOSTRA FORM) =====
    return render_template("reset_password.html", token=token)

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
    return redirect(url_for("home"))


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

@app.route("/api/sectors")
def api_sectors():

    from sqlalchemy import func

    data = (
        db.session.query(
            Company.sector,
            func.count(Company.id),
            func.sum(Company.market_cap)
        )
        .group_by(Company.sector)
        .all()
    )

    return jsonify([
        {
            "id": sector,
            "label": sector,
            "count": count,
            "market_cap": float(total_cap or 0)
        }
        for sector, count, total_cap in data
    ])

@app.route("/api/companies")
def api_companies():
    sector = request.args.get("sector")

    if not sector:
        return jsonify({"error": "sector required"}), 400

    sector_companies = Company.query.filter_by(sector=sector).all()

    if not sector_companies:
        return jsonify({"nodes": [], "links": []})

    sector_ids = set(c.id for c in sector_companies)

    ownerships = Ownership.query.filter(
        Ownership.source_id.in_(sector_ids) |
        Ownership.target_id.in_(sector_ids)
    ).all()

    all_node_ids = set(sector_ids)

    for o in ownerships:
        all_node_ids.add(o.source_id)
        all_node_ids.add(o.target_id)

    companies = Company.query.filter(Company.id.in_(all_node_ids)).all()

    nodes = [
        {
            "id": c.id,
            "label": c.name,
            "sector": c.sector,
            "market_cap": c.market_cap or 0
        }
        for c in companies
    ]

    links = [
        {
            "source": o.source_id,
            "target": o.target_id,
            "value": o.percentage
        }
        for o in ownerships
    ]

    return jsonify({
        "nodes": nodes,
        "links": links
    })

@app.route("/debug-click")
def debug_click():
    return render_template("debug_click.html")

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
def expert_advisor():
    return render_template("expert_advisor.html")


@app.route("/strumenti")
def strumenti():
    return render_template("laboratorio.html")

@app.route("/lab/risk", methods=["GET", "POST"])
@login_required
def risk_manager():

    result = None

    if request.method == "POST":
        try:
            balance = float(request.form.get("balance", 0))
            lot = float(request.form.get("lot", 0))
            entry = float(request.form.get("entry", 0))
            target = float(request.form.get("target", 0))
            sl = float(request.form.get("sl", 0))
            pair = request.form.get("pair", "EURUSD")
            trade_type = request.form.get("type", "buy")

            if balance > 0 and lot > 0:
                result = calculate_trade(balance, lot, entry, target, sl, trade_type, pair)

        except Exception as e:
            print("ERRORE:", e)
            result = None

    return render_template("risk_manager.html", result=result)


@app.route("/forum")
def forum():
    return render_template("forum.html")


@app.route("/news")
def news():
    return render_template("news.html")


@app.route("/faq")
def faq():
    return render_template("faq.html")




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
# serve per gunicorn
application = app    

if __name__ == "__main__":
    with app.app_context():
        init_db()

    # Avvio server locale
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    

