"""API Key Pool manager for multi-account load balancing and quota failover."""

import logging
import time

logger = logging.getLogger(__name__)


class APIKeyPool:
    """Manages a pool of API keys with round-robin rotation and cooldown-based failover.
    
    When an API key encounters HTTP 429 (Resource Exhausted) or HTTP 403 (Quota Exceeded),
    it is temporarily placed in cooldown and the pool automatically switches to the next available key.
    """

    def __init__(self, keys: list[str] | str, default_cooldown: float = 60.0):
        if isinstance(keys, str):
            raw = [k.strip() for k in keys.split(",") if k.strip()]
        elif isinstance(keys, (list, tuple)):
            raw = [k.strip() for k in keys if isinstance(k, str) and k.strip()]
        else:
            raw = []

        # Deduplicate while preserving original order
        self.keys: list[str] = list(dict.fromkeys(raw))
        if not self.keys:
            raise ValueError("At least one valid API key is required in the pool.")

        self.default_cooldown = default_cooldown
        self._index: int = 0
        self._cooldowns: dict[str, float] = {}  # key -> expiry timestamp

    def __len__(self) -> int:
        return len(self.keys)

    def get_current_key(self) -> str:
        """Return the current active key without advancing the round-robin counter."""
        return self.get_next_key(advance=False)

    def get_next_key(self, advance: bool = True) -> str:
        """Return the next available key that is not in cooldown.
        
        If all keys are in cooldown, returns the key that expires earliest.
        If advance=True, advances the round-robin pointer.
        """
        now = time.time()
        n = len(self.keys)

        # Search for the first key starting from self._index that is not in cooldown
        for i in range(n):
            idx = (self._index + i) % n
            key = self.keys[idx]
            expiry = self._cooldowns.get(key, 0.0)
            if now >= expiry:
                if advance:
                    self._index = (idx + 1) % n
                return key

        # If all keys are in cooldown, pick the one that expires earliest
        earliest_key = min(self.keys, key=lambda k: self._cooldowns.get(k, 0.0))
        remaining = max(0.0, self._cooldowns.get(earliest_key, 0.0) - now)
        logger.warning(
            "All %d API keys in pool are in cooldown. Using key with earliest recovery (%s..., ~%.1fs left).",
            n,
            earliest_key[:8],
            remaining,
        )
        if advance:
            self._index = (self.keys.index(earliest_key) + 1) % n
        return earliest_key

    def mark_rate_limited(self, key: str, cooldown: float | None = None) -> str:
        """Mark a key as rate-limited / quota-exhausted for a cooldown duration.
        
        Returns the next available key in the pool.
        """
        duration = cooldown if cooldown is not None else self.default_cooldown
        expiry = time.time() + duration
        self._cooldowns[key] = expiry
        logger.warning(
            "API key '%s...' hit rate limit / quota (429/403). Cooldown set for %.1fs. Rotating to next key.",
            key[:8],
            duration,
        )
        return self.get_next_key(advance=True)

    def mark_success(self, key: str) -> None:
        """Clear any cooldown record on success."""
        if key in self._cooldowns:
            del self._cooldowns[key]

    @property
    def active_keys_count(self) -> int:
        """Number of keys currently not in cooldown."""
        now = time.time()
        return sum(1 for k in self.keys if now >= self._cooldowns.get(k, 0.0))

