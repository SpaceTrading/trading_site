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

resend.api_key = os.environ.get("re_XmoZNh36_7KGpqnEDDKxH3PwUHKmVC8Ko")

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

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(INSTANCE_DIR, "app.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)


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

# =========================================================
# SIMULATORE MONTE-CARLO
# =========================================================

@app.route("/api/montecarlo/upload", methods=["POST"])
def montecarlo_upload():

    print("AUTH:", current_user.is_authenticated)

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
        all_equities = []
        final_profits = []

        for _ in range(sims):
            shuffled = trades.copy()
            np.random.shuffle(shuffled)

            equity = np.cumsum(shuffled)

            all_equities.append(equity)
            final_profits.append(equity[-1])

        # =========================
        # ORDINA PER PROFITTO
        # =========================
        sorted_indices = np.argsort(final_profits)
        sorted_equities = [all_equities[i] for i in sorted_indices]

        # percentili
        p5_index = int(sims * 0.95)
        p50_index = int(sims * 0.5)
        p95_index = int(sims * 0.05)

        best_5_equity = sorted_equities[p5_index].tolist()
        median_equity = sorted_equities[p50_index].tolist()
        worst_95_equity = sorted_equities[p95_index].tolist()

        # =========================
        # SAMPLE CURVES (50)
        # =========================
        sample_size = min(50, sims)
        sample_indices = np.random.choice(range(sims), size=sample_size, replace=False)
        samples = [all_equities[i].tolist() for i in sample_indices]

        # =========================
        # METRICHE BASE
        # =========================
        median_profit = float(np.median(final_profits))
        avg_profit = float(np.mean(final_profits))
        worst_profit = float(np.min(final_profits))
        best_profit = float(np.max(final_profits))

        # drawdown su curva mediana
        median_dd = float(max_drawdown(median_equity))

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

            "metrics": {
                "avg_profit": avg_profit,
                "median_profit": median_profit,
                "best_profit": best_profit,
                "worst_profit": worst_profit,
                "median_dd": median_dd
            }
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
                values = [normalize(v) for v in row.values]
                row_text = " ".join(values)

                if (
                    "affare" in row_text
                    and "direzione" in row_text
                    and ("profitto" in row_text or "profit" in row_text)
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
            df = pd.read_excel(file, header=None)
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
    email = request.form.get("email", "").strip().lower()

    if not email:
        flash("Inserisci una email valida.", "error")
        return redirect(url_for("home"))

    user = User.query.filter_by(email=email).first()

    # NON riveliamo se email esiste (anti enumeration)
    if user:
        token = secrets.token_urlsafe(32)

        reset = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=datetime.utcnow() + timedelta(minutes=30)
        )

        db.session.add(reset)
        db.session.commit()

        # link reset
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
            print("EMAIL RESET ERROR:", e)

    flash("Presto riceverai un link per il reset della password.", "success")
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
        
        if not token or not verify_turnstile(token, ip):
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
    

