"""The séance page: static files from web/ and one Server-Sent Events endpoint.

    python -m fly_seance.server            # http://127.0.0.1:8630

GET /api/seance?q=<question> streams the ritual as it happens:
  offering → trial ×k (as each one finishes) → verdict → voice → done
or a single `failure` event. One séance at a time.
"""

from __future__ import annotations

import json
import os
import queue
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fly_seance.brain import PATH_COMP, PATH_CON
from fly_seance.drift import feel
from fly_seance.medium import (MAX_QUESTION, REFUSALS, MediumError, consecrate, plain_line,
                               speak)
from fly_seance.oracle import read_verdict, run_trials, trial_voice, load_thresholds
from fly_seance.seance import TRIALS

WEB = Path(__file__).resolve().parents[2] / "web"
PORT = int(os.environ.get("FLY_SEANCE_PORT", "8630"))
RASTER_MAX = 4000  # spikes sent per trial; enough for the display
_busy = threading.Lock()


def thin_raster(rows: list[str], raster: list, limit: int = RASTER_MAX) -> list:
    """Keep every read-out spike; sample the rest evenly to stay under `limit`."""
    keep = [p for p in raster if rows[p[0]].startswith("readout:")]
    rest = [p for p in raster if not rows[p[0]].startswith("readout:")]
    room = max(limit - len(keep), 0)
    if len(rest) > room:
        step = len(rest) / room if room else float("inf")
        rest = [rest[int(i * step)] for i in range(room)]
    return sorted(keep + rest, key=lambda p: p[1])


def ritual(question: str, emit) -> None:
    """Run one séance, calling emit(event, data) at each step."""
    if not (PATH_COMP.exists() and PATH_CON.exists()):
        emit("failure", {"kind": "connectome", "message":
             "The fly's brain is not here yet: run python scripts/fetch_connectome.py"})
        return
    try:
        offering = consecrate(question)
    except MediumError as e:
        kind = "silent" if "offering" in str(e) else "medium"
        msg = ("The medium heard nothing to offer. Ask a real question."
               if kind == "silent" else "The medium is not here: start Ollama (ollama serve).")
        emit("failure", {"kind": kind, "message": msg, "detail": str(e)})
        return
    if "refused" in offering:
        emit("refusal", {"topic": offering["refused"], "message": REFUSALS[offering["refused"]]})
        emit("done", {})
        return
    emit("offering", offering)

    thresholds = load_thresholds()

    def on_trial(i: int, t: dict) -> None:
        emit("trial", {"i": i, "voice": trial_voice(t, thresholds), "rates_hz": t["rates_hz"],
                       "n_active": t["n_active"], "raster_rows": t["raster_rows"],
                       "raster": thin_raster(t["raster_rows"], t["raster"])})

    trials = run_trials(offering["rates"], TRIALS, silence=["veil"] if offering["veil"] else [],
                        on_trial=on_trial)
    verdict = read_verdict(trials, thresholds)
    emit("verdict", verdict.to_dict())
    try:
        voice = speak(question, offering, verdict)
    except MediumError:
        voice = ""
    emit("voice", {"text": voice, "plain": plain_line(verdict, offering)})
    emit("done", {})


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(WEB), **kw)

    def log_message(self, fmt, *args):  # quiet
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def _drift(self) -> None:
        """One idle trial; skipped while a séance holds the fly."""
        if not (PATH_COMP.exists() and PATH_CON.exists()):
            return self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"skipped": "no connectome"})
        if not _busy.acquire(blocking=False):
            return self._json(HTTPStatus.CONFLICT, {"skipped": "séance under way"})
        try:
            result = feel()
        finally:
            _busy.release()
        self._json(HTTPStatus.OK, result)

    def _json(self, status: HTTPStatus, data: dict) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _trusted(self, api: bool) -> bool:
        """Local use only: the Host must be ours (no DNS rebinding) and, for the
        API, the request must not come from another site (no cross-site trigger)."""
        if self.headers.get("Host", "") not in {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}:
            return False
        if not api:
            return True
        site = self.headers.get("Sec-Fetch-Site")
        if site is not None:
            return site in ("same-origin", "none")
        origin = self.headers.get("Origin")
        return origin is None or origin in {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}

    def do_GET(self):
        url = urlparse(self.path)
        api = url.path in ("/api/seance", "/api/drift")
        if not self._trusted(api):
            return self.send_error(HTTPStatus.FORBIDDEN, "Fly Séance only answers its own page.")
        if url.path == "/api/seance":
            return self._seance(parse_qs(url.query).get("q", [""])[0][:MAX_QUESTION])
        if url.path == "/api/drift":
            return self._drift()
        return super().do_GET()

    def do_HEAD(self):
        if not self._trusted(False):
            return self.send_error(HTTPStatus.FORBIDDEN)
        return super().do_HEAD()

    def _send(self, event: str, data: dict) -> None:
        payload = f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()
        self.wfile.write(payload)
        self.wfile.flush()

    def _seance(self, question: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        if not question.strip():
            return self._send("failure", {"kind": "empty", "message": "Ask the fly a question."})
        if not _busy.acquire(blocking=False):
            return self._send("failure", {"kind": "busy",
                                          "message": "A séance is already under way. Wait for the fly."})
        # Trials report from worker threads; the stream is written from this thread only.
        events: queue.Queue = queue.Queue()
        worker = threading.Thread(target=self._run, args=(question, events), daemon=True)
        try:
            worker.start()
            while True:
                event, data = events.get()
                self._send(event, data)
                if event in ("done", "failure"):
                    break
        except (BrokenPipeError, ConnectionResetError):
            pass  # the sitter left; the ritual finishes and releases the lock
        finally:
            if not worker.is_alive():
                _busy.release()
            else:
                threading.Thread(target=lambda: (worker.join(), _busy.release()), daemon=True).start()

    @staticmethod
    def _run(question: str, events: queue.Queue) -> None:
        try:
            ritual(question, lambda e, d: events.put((e, d)))
        except Exception as e:  # noqa: BLE001 — the page must always get an end event
            events.put(("failure", {"kind": "error", "message": "The séance broke off.",
                                    "detail": f"{type(e).__name__}: {e}"}))


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Fly Séance: http://127.0.0.1:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
