import type { RunDto } from './api';

type Metrics = Record<string, unknown>;

export function runOutcomeTitle(status: RunDto['status'] | undefined, metrics: Metrics): string {
  if (status === 'canceled') return 'Запуск остановлен';
  if (status === 'timeout') return 'Превышено время выполнения';
  if (metrics.compile_error || Number(metrics.bot_errors) > 0) return 'В коде есть ошибка';
  if (status === 'failed') return 'Не удалось запустить игру';
  const objective = ['solved', 'success', 'passed', 'win', 'won', 'escaped', 'reached_exit', 'reached_goal', 'completed']
    .find(key => typeof metrics[key] === 'boolean');
  if (objective) return metrics[objective] === true ? 'Задача решена' : 'Цель пока не выполнена';
  return 'Попытка завершена';
}

export function runOutcomeReason(status: RunDto['status'] | undefined, metrics: Metrics, error?: string | null): string {
  if (metrics.compile_error) return String(metrics.compile_error);
  if (Number(metrics.bot_errors) > 0) return 'Бот завершал ход с ошибкой Python. Откройте событие ошибки, чтобы перейти к строке кода.';
  if (status === 'failed') return 'Сервис запуска не смог выполнить попытку. Код сохранён; попробуйте запустить игру ещё раз.';
  if (error) return error;
  if (metrics.escaped === false) return 'Выход не достигнут. Посмотрите последние ходы и заблокированные перемещения.';
  if (metrics.solved === false) return 'Цель задачи пока не выполнена. События и состояние поля помогут проверить стратегию.';
  return '';
}
