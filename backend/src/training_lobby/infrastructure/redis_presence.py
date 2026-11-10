from redis import Redis


class RedisLobbyViewerPresence:
    """Share lobby viewing activity between API workers and the matchmaker."""

    def __init__(self, client: Redis) -> None:
        self._client = client

    def touch(self, lobby_id: str, ttl_seconds: int) -> None:
        self._client.set(f"ai-game:training-lobby:{lobby_id}:viewer", "1", ex=ttl_seconds)

    def is_online(self, lobby_id: str) -> bool:
        return bool(self._client.exists(f"ai-game:training-lobby:{lobby_id}:viewer"))
