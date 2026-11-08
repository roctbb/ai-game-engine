import { describe, expect, it } from 'vitest';
import { runOutcomeReason, runOutcomeTitle } from './runOutcome';

describe('run outcome distinguishes service failures from student errors', () => {
  it('describes an execution-context HTTP 500 without blaming the bot', () => {
    expect(runOutcomeTitle('failed', {})).toBe('Не удалось запустить игру');
    const reason = runOutcomeReason('failed', {}, "Server error '500 Internal Server Error' for url 'http://backend-api/internal/runs/id/execution-context'");
    expect(reason).toContain('Код сохранён');
    expect(reason).not.toContain('backend-api');
  });
  it('keeps real Python diagnostics actionable', () => {
    const compile = { compile_error: 'SyntaxError: expected colon' };
    expect(runOutcomeTitle('finished', compile)).toBe('В коде есть ошибка');
    expect(runOutcomeReason('finished', compile)).toContain('SyntaxError');
    expect(runOutcomeTitle('finished', { bot_errors: 2 })).toBe('В коде есть ошибка');
  });
  it('keeps cancellation and execution deadlines distinct', () => {
    expect(runOutcomeTitle('canceled', {})).toBe('Запуск остановлен');
    expect(runOutcomeTitle('timeout', {})).toBe('Превышено время выполнения');
  });
  it('does not classify an unsuccessful strategy as a Python error', () => {
    expect(runOutcomeTitle('finished', { solved: false })).toBe('Цель пока не выполнена');
    expect(runOutcomeTitle('finished', { solved: true })).toBe('Задача решена');
  });
});
