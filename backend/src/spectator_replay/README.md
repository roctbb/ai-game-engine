# spectator_replay context

MVP responsibilities:
- store replay artifacts for terminal runs (`finished`, `failed`, `timeout`, `canceled`);
- expose replay read API for Match Watch page and spectator workflows;
- keep replay payload normalized (`frames`, `events`, `summary`) regardless of game mode.
