import { describe, expect, it } from 'vitest';
import { replayParticipant } from './replayParticipant';

const participants = [
  { team_id: 'team_a', display_name: 'Бот Алёна', captain_user_id: 'a' },
  { team_id: 'team_b', display_name: 'Бот Борис', captain_user_id: 'b' },
];

describe('replay participant identity', () => {
  it('uses the team identity before a legacy label', () => {
    expect(replayParticipant({ teamId: 'team_b', name: 'Бот Алёна' }, participants)).toBe(participants[1]);
  });
  it('recognizes named tanks without team IDs', () => {
    expect(replayParticipant({ teamId: 'tank_1', name: ' бот алена ' }, participants)).toBe(participants[0]);
  });
  it('does not count map towers as participants', () => {
    expect(replayParticipant({ teamId: 'tower', name: 'tower' }, participants)).toBeUndefined();
  });
  it('does not assign scores by an ambiguous display name', () => {
    const sameNames = [participants[0], { ...participants[1], display_name: 'Бот Алёна' }];
    expect(replayParticipant({ teamId: 'unknown', name: 'Бот Алёна' }, sameNames)).toBeUndefined();
  });
});
