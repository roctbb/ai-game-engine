from __future__ import annotations

import ast
from io import StringIO
import tokenize
from dataclasses import dataclass, field

from shared.kernel import ForbiddenError, InvariantViolationError, new_id, utc_now


@dataclass(slots=True)
class TeamSlotCode:
    slot_key: str
    code: str
    revision: int
    updated_at: object


@dataclass(frozen=True, slots=True)
class TeamSnapshot:
    snapshot_id: str
    team_id: str
    game_id: str
    version_id: str
    codes_by_slot: dict[str, str]
    revisions_by_slot: dict[str, int]
    created_at: object


@dataclass(frozen=True, slots=True)
class TeamCompatibility:
    compatible: bool
    missing_required_slots: tuple[str, ...]


@dataclass(slots=True)
class Team:
    team_id: str
    game_id: str
    name: str
    captain_user_id: str
    slots: dict[str, TeamSlotCode] = field(default_factory=dict)

    @staticmethod
    def create(game_id: str, name: str, captain_user_id: str) -> "Team":
        return Team(
            team_id=new_id("team"),
            game_id=game_id,
            name=name,
            captain_user_id=captain_user_id,
        )

    def update_slot_code(self, actor_user_id: str, slot_key: str, code: str) -> TeamSlotCode:
        if actor_user_id != self.captain_user_id:
            raise ForbiddenError("Редактировать код может только капитан")
        if _contains_forbidden_input_call(code):
            raise InvariantViolationError(
                "В пользовательском коде запрещено использовать input(); "
                "используйте API игры/SDK для получения состояния."
            )
        normalized = code.rstrip() + "\n"
        previous = self.slots.get(slot_key)
        revision = 1 if previous is None else previous.revision + 1
        slot = TeamSlotCode(
            slot_key=slot_key,
            code=normalized,
            revision=revision,
            updated_at=utc_now(),
        )
        self.slots[slot_key] = slot
        return slot

    def compatibility(self, required_slot_keys: tuple[str, ...]) -> TeamCompatibility:
        missing = [key for key in required_slot_keys if key not in self.slots or not self.slots[key].code.strip()]
        return TeamCompatibility(
            compatible=len(missing) == 0,
            missing_required_slots=tuple(sorted(missing)),
        )

    def create_snapshot(self, version_id: str, required_slot_keys: tuple[str, ...]) -> TeamSnapshot:
        compatibility = self.compatibility(required_slot_keys)
        if not compatibility.compatible:
            missing = ", ".join(compatibility.missing_required_slots)
            raise InvariantViolationError(f"Команда не заполнила обязательные слоты: {missing}")

        selected_slots = {key: self.slots[key] for key in required_slot_keys}
        return TeamSnapshot(
            snapshot_id=new_id("snap"),
            team_id=self.team_id,
            game_id=self.game_id,
            version_id=version_id,
            codes_by_slot={key: slot.code for key, slot in selected_slots.items()},
            revisions_by_slot={key: slot.revision for key, slot in selected_slots.items()},
            created_at=utc_now(),
        )


def _contains_forbidden_input_call(source: str) -> bool:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return _contains_forbidden_input_call_tokenized(source)

    forbidden_call_aliases, builtins_module_aliases = _collect_forbidden_aliases(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _is_forbidden_call(
            node.func,
            forbidden_call_aliases=forbidden_call_aliases,
            builtins_module_aliases=builtins_module_aliases,
        ):
            return True
    return False


def _collect_forbidden_aliases(tree: ast.AST) -> tuple[set[str], set[str]]:
    forbidden_call_aliases: set[str] = {"input"}
    builtins_module_aliases: set[str] = {"builtins", "__builtins__"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "builtins":
                    builtins_module_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "builtins":
                for alias in node.names:
                    alias_name = alias.asname or alias.name
                    if alias.name == "input":
                        forbidden_call_aliases.add(alias_name)
                    if alias.name == "builtins":
                        builtins_module_aliases.add(alias_name)

    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                if isinstance(node.value, ast.Name) and node.value.id in forbidden_call_aliases:
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id not in forbidden_call_aliases:
                            forbidden_call_aliases.add(target.id)
                            changed = True
            elif isinstance(node, ast.AnnAssign):
                if (
                    isinstance(node.target, ast.Name)
                    and isinstance(node.value, ast.Name)
                    and node.value.id in forbidden_call_aliases
                    and node.target.id not in forbidden_call_aliases
                ):
                    forbidden_call_aliases.add(node.target.id)
                    changed = True

    return forbidden_call_aliases, builtins_module_aliases


def _is_forbidden_call(
    func: ast.expr,
    *,
    forbidden_call_aliases: set[str],
    builtins_module_aliases: set[str],
) -> bool:
    if isinstance(func, ast.Name):
        return func.id in forbidden_call_aliases
    if (
        isinstance(func, ast.Attribute)
        and func.attr == "input"
        and _is_builtins_loader_expr(func.value, builtins_module_aliases)
    ):
        return True
    return False


def _is_builtins_loader_expr(expr: ast.expr, builtins_module_aliases: set[str]) -> bool:
    if isinstance(expr, ast.Name):
        return expr.id in builtins_module_aliases
    if (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Name)
        and expr.func.id == "__import__"
        and len(expr.args) >= 1
        and isinstance(expr.args[0], ast.Constant)
        and expr.args[0].value == "builtins"
    ):
        return True
    return False


def _contains_forbidden_input_call_tokenized(source: str) -> bool:
    try:
        tokens = list(tokenize.generate_tokens(StringIO(source).readline))
    except (tokenize.TokenError, IndentationError):
        return "input(" in source

    skip_types = {tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.COMMENT}
    for index, token in enumerate(tokens):
        if token.type != tokenize.NAME or token.string != "input":
            continue
        next_index = index + 1
        while next_index < len(tokens) and tokens[next_index].type in skip_types:
            next_index += 1
        if next_index < len(tokens) and tokens[next_index].string == "(":
            return True
    return False
