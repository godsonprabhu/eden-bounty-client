"""In-memory sign-in and password-reset throttles (CR-C4; reworked in security remediation, finding 2).

Brute-force protection for administrator, customer and investor sign-in has three layers:

1. **Per account + client address** (this module): after ``LOCKOUT_MAX_ATTEMPTS`` failures for one
   email from one client address, that address gets the generic "invalid email or password" answer
   for that email for ``LOGIN_FAILURE_WINDOW_SECONDS``, even with the right password. This is the
   old 5-attempt lockout, but it no longer locks the real account holder out from *their* network.
2. **Per client address** (this module): ``LOGIN_FAILURE_LIMIT_PER_IP`` failures across any accounts
   in the window → HTTP 429. Stops password spraying from one source. Only failures count, so an
   office of users behind one address is unaffected by ordinary sign-ins.
3. **Per account, any address** (database columns ``failed_login_attempts`` / ``locked_until``):
   ``ACCOUNT_LOCKOUT_MAX_ATTEMPTS`` consecutive failures lock the account for
   ``LOCKOUT_DURATION_MINUTES``. Stops distributed guessing. Because layer 1 caps each address at
   five tries, locking an account this way needs several distinct addresses, and the holder can
   always recover with a password-reset link (completing a reset clears the lock).

Layers 1 and 2 are keyed by the *submitted* email (SHA-256, so no addresses are held in memory),
whether or not an account exists, so they reveal nothing about which accounts exist.

LIMITATION: state lives in this process. It is lost on restart and is not shared between
processes, which is why production is pinned to one API worker (``WORKERS=1``, enforced at
startup). Running more workers or instances requires moving these counters to a shared store
(e.g. Redis) or to the edge proxy first.
"""

import asyncio
import hashlib
import time
from collections import deque

from fastapi import HTTPException, Request, status

from app.core.config import settings
from app.core.rate_limit import get_client_ip

_MAX_KEYS = 50_000


def _email_key(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:32]


class SlidingWindowCounter:
    """Timestamps per key inside a sliding window. Not thread-safe; callers hold the lock."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = {}

    def _prune(self, key: str, now: float, window: float) -> deque[float] | None:
        events = self._events.get(key)
        if events is None:
            return None
        cutoff = now - window
        while events and events[0] <= cutoff:
            events.popleft()
        if not events:
            del self._events[key]
            return None
        return events

    def count(self, key: str, now: float, window: float) -> int:
        events = self._prune(key, now, window)
        return len(events) if events else 0

    def add(self, key: str, now: float, window: float) -> None:
        if len(self._events) >= _MAX_KEYS:
            self.sweep(now, window)
        self._events.setdefault(key, deque()).append(now)

    def discard(self, key: str) -> None:
        self._events.pop(key, None)

    def sweep(self, now: float, window: float) -> None:
        for key in list(self._events):
            self._prune(key, now, window)
        # Still full: every key is active. Drop the oldest half rather than grow without bound.
        if len(self._events) >= _MAX_KEYS:
            oldest = sorted(self._events, key=lambda k: self._events[k][-1])[: len(self._events) // 2]
            for key in oldest:
                del self._events[key]

    def clear(self) -> None:
        self._events.clear()

    def __len__(self) -> int:
        return len(self._events)


class LoginFailureThrottle:
    def __init__(self) -> None:
        self._by_ip = SlidingWindowCounter()
        self._by_account_ip = SlidingWindowCounter()
        self._lock = asyncio.Lock()

    @staticmethod
    def _pair(email: str, ip: str) -> str:
        return f"{_email_key(email)}|{ip}"

    async def ensure_allowed(self, request: Request) -> None:
        """Raises HTTP 429 when this client address has exhausted its failed-attempt allowance."""
        ip = get_client_ip(request)
        async with self._lock:
            if self._by_ip.count(ip, time.time(), settings.LOGIN_FAILURE_WINDOW_SECONDS) >= settings.LOGIN_FAILURE_LIMIT_PER_IP:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many failed sign-in attempts. Please wait before trying again.",
                )

    async def is_blocked_for_account(self, request: Request, email: str) -> bool:
        """True when this client address has used up its attempts for this email."""
        key = self._pair(email, get_client_ip(request))
        async with self._lock:
            return self._by_account_ip.count(key, time.time(), settings.LOGIN_FAILURE_WINDOW_SECONDS) >= settings.LOCKOUT_MAX_ATTEMPTS

    async def record_failure(self, request: Request, email: str | None = None) -> None:
        ip = get_client_ip(request)
        now = time.time()
        window = settings.LOGIN_FAILURE_WINDOW_SECONDS
        async with self._lock:
            self._by_ip.add(ip, now, window)
            if email:
                self._by_account_ip.add(self._pair(email, ip), now, window)

    async def record_success(self, request: Request, email: str) -> None:
        """A correct password from this address clears its per-account counter (never the per-IP one)."""
        async with self._lock:
            self._by_account_ip.discard(self._pair(email, get_client_ip(request)))

    async def reset(self) -> None:
        async with self._lock:
            self._by_ip.clear()
            self._by_account_ip.clear()


class PasswordResetRequestThrottle:
    """Caps forgot-password requests per email and per client address (stops reset-email flooding)."""

    WINDOW = 3600.0

    def __init__(self) -> None:
        self._by_email = SlidingWindowCounter()
        self._by_ip = SlidingWindowCounter()
        self._lock = asyncio.Lock()

    async def check_ip(self, request: Request) -> None:
        ip = get_client_ip(request)
        now = time.time()
        async with self._lock:
            if self._by_ip.count(ip, now, self.WINDOW) >= settings.PASSWORD_RESET_REQUESTS_PER_IP_HOUR:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please wait before trying again.",
                )
            self._by_ip.add(ip, now, self.WINDOW)

    async def allow_email(self, email: str) -> bool:
        """Counts one request for this email; False once the hourly allowance is used (caller stays silent)."""
        key = _email_key(email)
        now = time.time()
        async with self._lock:
            if self._by_email.count(key, now, self.WINDOW) >= settings.PASSWORD_RESET_REQUESTS_PER_HOUR:
                return False
            self._by_email.add(key, now, self.WINDOW)
            return True

    async def reset(self) -> None:
        async with self._lock:
            self._by_email.clear()
            self._by_ip.clear()


login_failure_throttle = LoginFailureThrottle()
password_reset_throttle = PasswordResetRequestThrottle()
