import type { RunDto } from "./api";
import { record } from "./replayInsights";

export function attemptPresentation(run: RunDto): {
  icon: string;
  tone: string;
  label: string;
  score: string;
} {
  const metrics = record(run.result_payload?.metrics);
  const score = metrics.score ?? run.result_payload?.score;
  const scoreText =
    typeof score === "number" ? String(Math.round(score * 100) / 100) : "—";
  if (metrics.compile_error || Number(metrics.bot_errors) > 0)
    return { icon: "×", tone: "error", label: "Ошибка кода", score: scoreText };
  if (run.status === "failed")
    return {
      icon: "!",
      tone: "error",
      label: "Ошибка запуска",
      score: scoreText,
    };
  if (run.status === "timeout")
    return {
      icon: "!",
      tone: "error",
      label: "Лимит времени",
      score: scoreText,
    };
  if (run.status === "canceled")
    return {
      icon: "Ⅱ",
      tone: "partial",
      label: "Остановлено",
      score: scoreText,
    };
  if (run.status !== "finished")
    return {
      icon: "◌",
      tone: "partial",
      label: run.status === "running" ? "Выполняется" : "В очереди",
      score: scoreText,
    };
  const objective = [
    "solved",
    "success",
    "passed",
    "escaped",
    "reached_goal",
    "completed",
  ].find((key) => typeof metrics[key] === "boolean");
  const solved = objective ? metrics[objective] === true : false;
  return {
    icon: solved ? "✓" : "○",
    tone: solved ? "success" : "partial",
    label: solved ? "Решено" : "Завершено",
    score: scoreText,
  };
}

export function formatTime(value?: string | null): string {
  return value
    ? new Date(value).toLocaleString("ru-RU", {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";
}
