from concurrent.futures import ThreadPoolExecutor, TimeoutError
from copy import deepcopy
from threading import Event, Lock

import pytest

from training_lobby.application.service import TrainingLobbyService
from training_lobby.domain.model import LobbyStatus


class DetachedLobbyRepository:
    """Like SQL storage, reads return detached copies rather than shared objects."""
    def __init__(self, lobby):
        self.items = {lobby.lobby_id: deepcopy(lobby)}

    def get(self, lobby_id):
        return deepcopy(self.items.get(lobby_id))

    def save(self, lobby):
        self.items[lobby.lobby_id] = deepcopy(lobby)


class SharedLocks:
    def __init__(self):
        self.locks = {}
        self.guard = Lock()

    def lock(self, name, **_kwargs):
        with self.guard:
            return self.locks.setdefault(name, Lock())


@pytest.mark.parametrize('mutation', ['join', 'ready', 'presence'])
def test_api_mutation_is_not_overwritten_by_separate_matchmaker(client, container, monkeypatch, mutation):
    game = next(g for g in client.get('/api/v1/games').json() if g['slug'] == 'ttt_connect5_v1')
    lobby = client.post('/api/v1/lobbies', json={
        'game_id': game['game_id'], 'title': 'Concurrent changes', 'kind': 'training', 'access': 'public',
    }).json()
    teams = []
    for index in range(3):
        team = client.post('/api/v1/teams', json={
            'game_id': game['game_id'], 'name': f'Player {index}', 'captain_user_id': f'concurrent-{index}',
        }).json()
        client.put(f"/api/v1/teams/{team['team_id']}/slots/bot", json={
            'actor_user_id': team['captain_user_id'], 'code': 'def make_choice(field, role):\n    return 0, 0\n',
        })
        teams.append(team)
    api = container.training_lobby
    api.join_team(lobby['lobby_id'], teams[0]['team_id'], None)
    repository = DetachedLobbyRepository(api.get_lobby(lobby['lobby_id']))
    locks = SharedLocks()
    api._repository = repository
    api._matchmaking_lock_client = locks
    matcher = TrainingLobbyService(repository, container.game_catalog, container.team_workspace,
                                   container.execution, matchmaking_lock_client=locks)
    read, release = Event(), Event()

    def delayed_cycle(*, lobby_id, requested_by):
        stale = repository.get(lobby_id)
        read.set()
        assert release.wait(5)
        stale.status = LobbyStatus.RUNNING
        repository.save(stale)
        return stale

    monkeypatch.setattr(matcher, '_run_matchmaking_cycle_locked', delayed_cycle)

    def change():
        if mutation == 'join':
            api.join_team(lobby['lobby_id'], teams[1]['team_id'], None)
        elif mutation == 'ready':
            api.set_ready(lobby['lobby_id'], teams[0]['team_id'], True)
        else:
            api.mark_viewer_online(lobby['lobby_id'], teams[0]['captain_user_id'])

    with ThreadPoolExecutor(max_workers=2) as pool:
        cycle = pool.submit(matcher.run_matchmaking_cycle, lobby['lobby_id'], 'system')
        assert read.wait(5)
        update = pool.submit(change)
        try:
            update.result(timeout=.1)
        except TimeoutError:
            pass  # A protected mutation waits until the current cycle commits.
        finally:
            release.set()
        cycle.result(timeout=5)
        update.result(timeout=5)

    saved = repository.get(lobby['lobby_id'])
    assert saved.status is LobbyStatus.RUNNING
    if mutation == 'join':
        assert teams[1]['team_id'] in saved.teams
    elif mutation == 'ready':
        assert saved.teams[teams[0]['team_id']].ready
    else:
        assert saved.teams[teams[0]['team_id']].last_seen_at is not None
