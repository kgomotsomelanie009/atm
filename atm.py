from __future__ import annotations

import hmac
import json
import secrets
import threading
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from urllib.parse import urlparse


PIN = "1234"
MAX_PIN_ATTEMPTS = 3
HOST = "127.0.0.1"
PORT = 8000


@dataclass
class Session:
    authenticated: bool = False
    attempts: int = 0
    locked: bool = False


class ATMState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.balance = Decimal("0.00")
        self.sessions: dict[str, Session] = {}
        self.transactions: list[dict[str, str]] = []


STATE = ATMState()


PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#101b2d">
  <title>Northstar ATM</title>
  <style>
    :root {
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #17243a;
      background: #f3f6fa;
      font-synthesis: none;
    }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; }
    button, input { font: inherit; }
    .topbar {
      height: 76px; padding: 0 max(24px, calc((100% - 1120px) / 2));
      display: flex; align-items: center; justify-content: space-between;
      background: #101b2d; color: white;
    }
    .brand { display: flex; gap: 12px; align-items: center; font-weight: 700; letter-spacing: .2px; }
    .brand-mark {
      width: 38px; height: 38px; display: grid; place-items: center; border-radius: 12px;
      color: #10233c; background: #89e0c0; font-size: 19px;
    }
    .demo-badge { color: #b7c5d8; font-size: 12px; letter-spacing: 1.2px; text-transform: uppercase; }
    main { width: min(100% - 40px, 1000px); margin: 54px auto; }
    .intro { margin-bottom: 30px; }
    .eyebrow { color: #16856d; font-size: 12px; font-weight: 750; letter-spacing: 1.4px; text-transform: uppercase; }
    h1 { margin: 9px 0 8px; font-size: clamp(29px, 4vw, 40px); letter-spacing: -1.5px; }
    .subheading { margin: 0; color: #68768a; line-height: 1.6; }
    .panel {
      background: white; border: 1px solid #e3e9f0; border-radius: 20px;
      box-shadow: 0 15px 40px #182b4410;
    }
    .login-panel { max-width: 470px; padding: 34px; }
    .panel h2 { margin: 0 0 8px; font-size: 21px; }
    .muted { color: #738096; font-size: 14px; line-height: 1.55; }
    label { display: block; margin: 24px 0 8px; font-size: 13px; font-weight: 700; }
    input {
      width: 100%; height: 50px; border: 1px solid #d5deea; border-radius: 10px;
      padding: 0 14px; outline: none; background: #fbfcfe;
    }
    input:focus { border-color: #178b70; box-shadow: 0 0 0 3px #178b701a; }
    .pin-input { letter-spacing: 8px; font-size: 20px; }
    .button {
      min-height: 46px; border: 0; border-radius: 10px; padding: 0 18px;
      background: #147c66; color: white; font-weight: 700; cursor: pointer;
      transition: background .15s, transform .15s;
    }
    .button:hover { background: #106751; transform: translateY(-1px); }
    .button:disabled { opacity: .6; cursor: wait; transform: none; }
    .button.full { width: 100%; margin-top: 16px; }
    .button.secondary { background: #edf3f5; color: #24554c; }
    .button.secondary:hover { background: #e0ece9; }
    .notice { min-height: 21px; margin: 12px 0 0; color: #b74747; font-size: 13px; }
    .dashboard { display: none; }
    .dashboard-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 22px; }
    .dashboard-head h2 { margin: 0; }
    .balance-card {
      position: relative; overflow: hidden; min-height: 205px; padding: 30px;
      border-radius: 18px; color: white;
      background: linear-gradient(120deg, #132741, #1d5c58);
    }
    .balance-card:after {
      content: ""; position: absolute; width: 240px; height: 240px; right: -45px; top: -118px;
      border: 1px solid #ffffff24; border-radius: 50%;
      box-shadow: 0 0 0 25px #ffffff08, 0 0 0 52px #ffffff06;
    }
    .balance-label { color: #c0d2df; font-size: 14px; }
    .balance-amount { margin: 12px 0 23px; font-size: clamp(36px, 6vw, 50px); font-weight: 700; letter-spacing: -1.8px; }
    .account-label { color: #c0d2df; font-size: 12px; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-top: 20px; }
    .action-card, .activity-card { padding: 24px; }
    .action-card h3, .activity-card h3 { margin: 0 0 5px; font-size: 17px; }
    .action-card .muted { margin: 0 0 17px; }
    .amount-field { height: 46px; }
    .action-card .button { margin-top: 12px; }
    .activity-card { grid-column: 1 / -1; }
    .transaction { display: flex; justify-content: space-between; gap: 15px; padding: 15px 0; border-bottom: 1px solid #edf0f4; }
    .transaction:last-child { border-bottom: 0; padding-bottom: 0; }
    .transaction-name { font-size: 14px; font-weight: 650; }
    .transaction-time { margin-top: 4px; color: #8390a2; font-size: 12px; }
    .transaction-amount { font-size: 14px; font-weight: 700; white-space: nowrap; }
    .credit { color: #16856d; }
    .debit { color: #253751; }
    .empty-state { padding: 19px 0 2px; color: #8390a2; font-size: 14px; }
    footer { padding: 26px 20px 34px; text-align: center; color: #8995a5; font-size: 12px; }
    @media (max-width: 640px) {
      .topbar { height: 66px; padding: 0 20px; }
      main { margin-top: 36px; }
      .login-panel { padding: 25px; }
      .grid { grid-template-columns: 1fr; }
      .activity-card { grid-column: auto; }
      .dashboard-head { align-items: flex-start; }
      .balance-card { padding: 25px; }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="brand"><span class="brand-mark">N</span><span>Northstar ATM</span></div>
    <span class="demo-badge">Local demo</span>
  </header>
  <main>
    <section class="intro">
      <div class="eyebrow">Everyday banking, made simple</div>
      <h1 id="page-title">Welcome back</h1>
      <p class="subheading">A straightforward, secure way to manage your cash.</p>
    </section>
    <section class="panel login-panel" id="login-panel">
      <h2>Sign in to your account</h2>
      <p class="muted">Enter your four-digit PIN to continue.</p>
      <form id="login-form">
        <label for="pin">ATM PIN</label>
        <input id="pin" name="pin" class="pin-input" type="password" inputmode="numeric"
          autocomplete="current-password" maxlength="4" pattern="[0-9]{4}" required>
        <button class="button full" type="submit">Continue</button>
        <p class="notice" id="login-notice" role="status" aria-live="polite"></p>
      </form>
    </section>
    <section class="dashboard" id="dashboard">
      <div class="dashboard-head">
        <div><h2>Your account</h2><span class="muted">Manage your balance and recent activity.</span></div>
        <button class="button secondary" id="logout" type="button">Sign out</button>
      </div>
      <article class="balance-card">
        <div class="balance-label">Available balance</div>
        <div class="balance-amount" id="balance">$0.00</div>
        <div class="account-label">CHECKING ACCOUNT &nbsp; •••• 2048</div>
      </article>
      <div class="grid">
        <form class="panel action-card" id="deposit-form">
          <h3>Add money</h3><p class="muted">Deposit funds into your account.</p>
          <label for="deposit-amount">Amount</label>
          <input class="amount-field" id="deposit-amount" name="amount" type="number" min="0.01" step="0.01" placeholder="$ 0.00" required>
          <button class="button" type="submit">Deposit money</button>
          <p class="notice" id="deposit-notice" role="status" aria-live="polite"></p>
        </form>
        <form class="panel action-card" id="withdraw-form">
          <h3>Take out cash</h3><p class="muted">Withdraw from your available balance.</p>
          <label for="withdraw-amount">Amount</label>
          <input class="amount-field" id="withdraw-amount" name="amount" type="number" min="0.01" step="0.01" placeholder="$ 0.00" required>
          <button class="button secondary" type="submit">Withdraw cash</button>
          <p class="notice" id="withdraw-notice" role="status" aria-live="polite"></p>
        </form>
        <section class="panel activity-card">
          <h3>Recent activity</h3><p class="muted">Your latest account transactions.</p>
          <div id="transactions"></div>
        </section>
      </div>
    </section>
  </main>
  <footer>Northstar ATM · Demonstration app · All data resets when the server stops</footer>
  <script>
    const loginPanel = document.querySelector("#login-panel");
    const dashboard = document.querySelector("#dashboard");
    const pageTitle = document.querySelector("#page-title");

    async function request(path, body) {
      const options = { headers: { "Content-Type": "application/json" } };
      if (body !== undefined) {
        options.method = "POST";
        options.body = JSON.stringify(body);
      }
      const response = await fetch(path, options);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Something went wrong.");
      return data;
    }

    function showDashboard(data) {
      loginPanel.style.display = "none";
      dashboard.style.display = "block";
      pageTitle.textContent = "Good to see you";
      document.querySelector("#balance").textContent =
        new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(data.balance);
      const transactions = document.querySelector("#transactions");
      transactions.replaceChildren();
      if (data.transactions.length === 0) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent = "No transactions yet. Your activity will appear here.";
        transactions.append(empty);
        return;
      }
      for (const transaction of data.transactions) {
        const row = document.createElement("div");
        row.className = "transaction";
        const detail = document.createElement("div");
        const name = document.createElement("div");
        name.className = "transaction-name";
        name.textContent = transaction.type;
        const time = document.createElement("div");
        time.className = "transaction-time";
        time.textContent = transaction.time;
        detail.append(name, time);
        const amount = document.createElement("div");
        amount.className = `transaction-amount ${transaction.type === "Deposit" ? "credit" : "debit"}`;
        amount.textContent = `${transaction.type === "Deposit" ? "+" : "−"}$${transaction.amount}`;
        row.append(detail, amount);
        transactions.append(row);
      }
    }

    document.querySelector("#login-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const notice = document.querySelector("#login-notice");
      const button = event.currentTarget.querySelector("button");
      notice.textContent = "";
      button.disabled = true;
      try {
        await request("/api/login", { pin: document.querySelector("#pin").value });
        showDashboard(await request("/api/state"));
      } catch (error) {
        notice.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    });

    for (const type of ["deposit", "withdraw"]) {
      document.querySelector(`#${type}-form`).addEventListener("submit", async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const notice = document.querySelector(`#${type}-notice`);
        const button = form.querySelector("button");
        notice.textContent = "";
        button.disabled = true;
        try {
          const amount = form.elements.amount.value;
          const data = await request(`/api/${type}`, { amount });
          form.reset();
          notice.style.color = "#16856d";
          notice.textContent = data.message;
          showDashboard(await request("/api/state"));
          notice.textContent = data.message;
        } catch (error) {
          notice.style.color = "";
          notice.textContent = error.message;
        } finally {
          button.disabled = false;
        }
      });
    }

    document.querySelector("#logout").addEventListener("click", async () => {
      await request("/api/logout", {});
      dashboard.style.display = "none";
      loginPanel.style.display = "block";
      pageTitle.textContent = "Welcome back";
      document.querySelector("#pin").value = "";
      document.querySelector("#login-notice").textContent = "";
    });

    request("/api/state").then((data) => {
      if (data.authenticated) showDashboard(data);
    }).catch((error) => {
      document.querySelector("#login-notice").textContent = error.message;
    });
  </script>
</body>
</html>
"""


class ATMRequestHandler(BaseHTTPRequestHandler):
    server_version = "NorthstarATM/1.0"

    def log_message(self, format: str, *args: object) -> None:
        return

    def _session(self) -> tuple[Session, str | None]:
        cookies = SimpleCookie()
        cookies.load(self.headers.get("Cookie", ""))
        morsel = cookies.get("atm_session")
        session_id = morsel.value if morsel else ""
        with STATE.lock:
            session = STATE.sessions.get(session_id)
            if session is not None:
                return session, None
            session_id = secrets.token_urlsafe(32)
            session = Session()
            STATE.sessions[session_id] = session
            return session, session_id

    def _send_json(
        self,
        data: dict[str, object],
        status: int = 200,
        new_session_id: str | None = None,
    ) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if new_session_id:
            self.send_header(
                "Set-Cookie",
                f"atm_session={new_session_id}; HttpOnly; SameSite=Strict; Path=/",
            )
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, object] | None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length < 0 or content_length > 4096:
                return None
            data = json.loads(self.rfile.read(content_length))
            return data if isinstance(data, dict) else None
        except (ValueError, json.JSONDecodeError):
            return None

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path != "/api/state":
            self._send_json({"error": "Not found."}, 404)
            return

        session, new_session_id = self._session()
        with STATE.lock:
            data: dict[str, object] = {"authenticated": session.authenticated}
            if session.authenticated:
                data.update(
                    balance=str(STATE.balance),
                    transactions=list(STATE.transactions),
                )
        self._send_json(data, new_session_id=new_session_id)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        data = self._read_json()
        if data is None:
            self._send_json({"error": "Send a valid JSON request."}, 400)
            return

        session, new_session_id = self._session()
        if path == "/api/login":
            self._login(data, session, new_session_id)
        elif path == "/api/logout":
            with STATE.lock:
                session.authenticated = False
            self._send_json({"ok": True}, new_session_id=new_session_id)
        elif path in ("/api/deposit", "/api/withdraw"):
            self._transact(path, data, session, new_session_id)
        else:
            self._send_json({"error": "Not found."}, 404, new_session_id)

    def _login(
        self,
        data: dict[str, object],
        session: Session,
        new_session_id: str | None,
    ) -> None:
        with STATE.lock:
            if session.locked:
                self._send_json(
                    {"error": "Too many incorrect attempts. Access denied."},
                    423,
                    new_session_id,
                )
                return
            pin = data.get("pin")
            if isinstance(pin, str) and hmac.compare_digest(pin, PIN):
                session.authenticated = True
                session.attempts = 0
                self._send_json({"ok": True}, new_session_id=new_session_id)
                return
            session.attempts += 1
            attempts_left = MAX_PIN_ATTEMPTS - session.attempts
            if attempts_left <= 0:
                session.locked = True
                message = "Too many incorrect attempts. Access denied."
            else:
                message = f"Incorrect PIN. {attempts_left} attempt(s) remaining."
        self._send_json(
            {"error": message, "attempts_left": max(0, attempts_left)},
            401,
            new_session_id,
        )

    def _transact(
        self,
        path: str,
        data: dict[str, object],
        session: Session,
        new_session_id: str | None,
    ) -> None:
        if not session.authenticated:
            self._send_json({"error": "Please sign in first."}, 401, new_session_id)
            return
        try:
            amount = Decimal(str(data.get("amount", "")).strip())
            if (
                not amount.is_finite()
                or amount <= 0
                or amount != amount.quantize(Decimal("0.01"))
            ):
                raise ValueError
        except (InvalidOperation, ValueError):
            self._send_json(
                {"error": "Enter a valid amount with no more than two decimal places."},
                400,
                new_session_id,
            )
            return

        is_deposit = path == "/api/deposit"
        with STATE.lock:
            if not is_deposit and amount > STATE.balance:
                self._send_json({"error": "Insufficient funds."}, 409, new_session_id)
                return
            STATE.balance += amount if is_deposit else -amount
            transaction_type = "Deposit" if is_deposit else "Withdrawal"
            STATE.transactions.insert(
                0,
                {
                    "type": transaction_type,
                    "amount": f"{amount:.2f}",
                    "time": datetime.now().strftime("%b %d, %Y · %I:%M %p"),
                },
            )
            del STATE.transactions[8:]
            balance = f"{STATE.balance:.2f}"
        self._send_json(
            {
                "message": f"${amount:.2f} {transaction_type.lower()} complete. Balance: ${balance}.",
                "balance": balance,
            },
            new_session_id=new_session_id,
        )


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), ATMRequestHandler)
    address = f"http://{HOST}:{PORT}"
    threading.Timer(0.5, webbrowser.open, args=(address,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
