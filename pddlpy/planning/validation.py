"""Plan validation and simulation (roadmap step 3).

A plan is a list of :class:`PlanStep` (action name, arguments, and for
temporal plans a start time and a duration), read from the IPC plan format
(:func:`parse_plan`) or from JSON (:func:`plan_from_json`).

:func:`simulate` executes it and returns the state after each happening;
:func:`validate_plan` also checks the goal. On failure both say which step
failed, why, what was unmet, and the state at that point.

The semantics follow VAL, the reference plan validator:

* Untimed steps run at times 1, 2, 3, ...; a durative step starts at its
  time and ends ``duration`` later.
* Happenings no more than ``TOLERANCE / 10`` apart form one happening. Its
  parts are checked against the state before it and must not interfere:
  one may not delete an atom another adds, nor change an atom or fluent
  another reads (a mutex violation).
* A durative step needs a ``[duration]`` within ``TOLERANCE`` of the
  declared one. ``over all`` conditions must hold after every happening
  from its start up to, but not including, its end.
* Reading a fluent that has no value fails the step.

What the object model cannot represent is refused with
:class:`PlanValidationError` rather than judged: syntax errors, goals other
than a conjunction of atoms (#138), durative actions with numeric,
conditional, quantified or inequality parts (#139, #143), and requirements
outside :data:`VALIDATION_CAPABILITIES`.
"""
from __future__ import annotations

import json
import math
import re
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    FrozenSet,
    Iterator,
    List,
    NamedTuple,
    Optional,
    Set,
    Tuple,
)

from pddlpy.pddl import (
    And,
    BinOp,
    Condition,
    DurativeAction,
    Exists,
    Fluent,
    Forall,
    Lit,
    Neg,
    Not,
    NumericCond,
    Operator,
    Or,
)

from .base import PlannerError
from .search import ADL_CAPABILITIES
from .state import GroundAtom, State, apply_numeric, atom_tuple

if TYPE_CHECKING:
    from pddlpy.pddl import DomainProblem, Expr

    from .state import PlanAction

#: VAL's default tolerance (``Validate -t``): the allowed error of a step's
#: duration; happenings closer than a tenth of it are simultaneous.
TOLERANCE = 0.01

#: Requirements whose semantics the validator implements.
VALIDATION_CAPABILITIES: FrozenSet[str] = ADL_CAPABILITIES | {":durative-actions"}


class PlanValidationError(PlannerError):
    """Raised when a plan cannot be judged: unreadable plan input, or a
    domain/problem using what the object model does not represent."""


class PlanStep(NamedTuple):
    """One step of a plan as written: ``(name arg ...)``, with an optional
    start ``time`` and ``duration`` (temporal plans)."""

    name: str
    args: Tuple[str, ...]
    time: Optional[float] = None
    duration: Optional[float] = None

    def __str__(self) -> str:
        return "(%s)" % " ".join((self.name,) + self.args)


# -- plan input ------------------------------------------------------------

_LINE = re.compile(
    r"^\s*(?:(?P<time>[-+0-9.eE]+)\s*:\s*)?\((?P<body>[^()]*)\)"
    r"\s*(?:\[\s*(?P<dur>[-+0-9.eE]+)\s*\])?\s*$"
)


def parse_plan(text: str) -> List[PlanStep]:
    """Read a plan in the IPC format: one ``(action arg ...)`` per line,
    optionally ``time: (action arg ...) [duration]``. Blank lines and ``;``
    comments are skipped. Raises :class:`PlanValidationError` on any other
    line."""
    steps = []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.split(";", 1)[0]
        if not line.strip():
            continue
        m = _LINE.match(line)
        tokens = m.group("body").split() if m else []
        if not tokens:
            raise PlanValidationError("plan line %d is not a step: %r" % (n, raw.strip()))
        time, dur = m.group("time"), m.group("dur")  # type: ignore[union-attr]
        try:
            steps.append(PlanStep(tokens[0], tuple(tokens[1:]),
                                  _number(time), _number(dur)))
        except ValueError:
            raise PlanValidationError("plan line %d has a bad number: %r" % (n, raw.strip()))
    return steps


def plan_from_json(data: Any) -> List[PlanStep]:
    """Read a plan from its JSON form: a list of steps, or an object with a
    ``steps`` list (the ``solve`` output). A step is ``{"action": NAME,
    "args": [...], "start": T, "duration": D}``; ``start`` and ``duration``
    are optional. ``args`` may also be a ``{variable: object}`` object, as
    ``solve`` prints it; :func:`simulate` orders it by the action's
    parameters."""
    if isinstance(data, dict):
        data = data.get("steps")
    if not isinstance(data, list):
        raise PlanValidationError("a JSON plan is a list of steps or an object with 'steps'")
    steps = []
    for i, s in enumerate(data):
        if not isinstance(s, dict) or not isinstance(s.get("action"), str):
            raise PlanValidationError("JSON plan step %d has no 'action' name" % i)
        args = s.get("args", [])
        if isinstance(args, dict):
            args = [_Binding(k, v) for k, v in args.items()]
        if not isinstance(args, list):
            raise PlanValidationError("JSON plan step %d: 'args' is not a list or object" % i)
        try:
            steps.append(PlanStep(s["action"], tuple(args),
                                  _number(s.get("start", s.get("time"))),
                                  _number(s.get("duration"))))
        except (TypeError, ValueError):
            raise PlanValidationError("JSON plan step %d has a bad number" % i)
    return steps


class _Binding(str):
    """A JSON argument given as ``variable: object``; the string is the
    object, ``variable`` places it among the action's parameters."""

    variable: str

    def __new__(cls, variable: str, obj: Any) -> "_Binding":
        b = super().__new__(cls, obj)
        b.variable = variable
        return b


def _number(value: Any) -> Optional[float]:
    """``value`` as a finite float (``None`` stays ``None``); ``ValueError``
    otherwise: a NaN or infinite time would never group into happenings."""
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("not a finite number: %r" % value)
    return number


def load_plan(text: str) -> List[PlanStep]:
    """Read a plan in either form: JSON if it starts with ``[`` or ``{``,
    else the IPC format."""
    if text.lstrip()[:1] in ("[", "{"):
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise PlanValidationError("plan is not valid JSON: %s" % exc)
        return plan_from_json(data)
    return parse_plan(text)


# -- results ---------------------------------------------------------------

class Failure(NamedTuple):
    """Why a plan fails.

    ``kind`` is one of: ``unknown-action``, ``arity``, ``unknown-object``,
    ``type``, ``duration`` (the step is malformed); ``precondition``,
    ``end-condition``, ``invariant``, ``undefined-fluent``, ``mutex`` (the
    step cannot run); ``goal`` (the plan ran but the goal does not hold).
    ``step`` is the 1-based number of the failing step (``None`` for
    ``goal``), ``unmet`` the unmet conditions or goal atoms as PDDL text,
    and ``state`` the state in which they were checked.
    """

    kind: str
    message: str
    step: Optional[int]
    action: Optional[str]
    time: Optional[float]
    unmet: Tuple[str, ...]
    state: State


class TracePoint(NamedTuple):
    """The state after one happening part: ``event`` is ``action`` for an
    instantaneous step, ``start`` / ``end`` for a durative one."""

    time: float
    event: str
    step: int
    action: str
    state: State


class Simulation(NamedTuple):
    """The result of :func:`simulate`: the trace up to the first failure, the
    failure (``None`` if every step ran), and the final state."""

    trace: Tuple[TracePoint, ...]
    failure: Optional[Failure]
    state: State

    @property
    def executed(self) -> bool:
        return self.failure is None


class Validation(NamedTuple):
    """The result of :func:`validate_plan`."""

    valid: bool
    failure: Optional[Failure]
    simulation: Simulation


# -- rendering -------------------------------------------------------------

def _atom_text(atom: GroundAtom) -> str:
    return "(%s)" % " ".join(atom)


def _expr_text(e: "Expr") -> str:
    if isinstance(e, Fluent):
        return _atom_text(e.head)
    if isinstance(e, BinOp):
        return "(%s %s %s)" % (e.op, _expr_text(e.left), _expr_text(e.right))
    if isinstance(e, Neg):
        return "(- %s)" % _expr_text(e.operand)
    return "%g" % e.value({})  # Num


def _cond_text(c: Condition) -> str:
    if isinstance(c, Lit):
        return _atom_text(atom_tuple(c.atom))
    if isinstance(c, Not):
        return "(not %s)" % _cond_text(c.child)
    if isinstance(c, (And, Or)):
        word = "and" if isinstance(c, And) else "or"
        return "(%s %s)" % (word, " ".join(_cond_text(k) for k in c.children))
    if isinstance(c, NumericCond):
        k = c.constraint
        return "(%s %s %s)" % (k.comp, _expr_text(k.lhs), _expr_text(k.rhs))
    return repr(c)  # Equality


def _unmet(c: Condition, state: State) -> List[str]:
    """The parts of ``c`` that fail in ``state``: the failing conjuncts of a
    conjunction, else ``c`` itself."""
    if c.holds(state.atoms, state.fluents):
        return []
    if isinstance(c, And):
        return [t for k in c.children for t in _unmet(k, state)]
    return [_cond_text(c)]


# -- reads and writes, for undefined fluents and mutexes --------------------

def _expr_fluents(e: "Expr") -> Iterator[GroundAtom]:
    if isinstance(e, Fluent):
        yield e.head
    elif isinstance(e, BinOp):
        yield from _expr_fluents(e.left)
        yield from _expr_fluents(e.right)
    elif isinstance(e, Neg):
        yield from _expr_fluents(e.operand)


def _cond_reads(c: Optional[Condition]) -> Tuple[Set[GroundAtom], Set[GroundAtom]]:
    """``(atoms, fluents)`` a grounded condition reads."""
    atoms: Set[GroundAtom] = set()
    fluents: Set[GroundAtom] = set()

    def walk(k: Condition) -> None:
        if isinstance(k, Lit):
            atoms.add(atom_tuple(k.atom))
        elif isinstance(k, Not):
            walk(k.child)
        elif isinstance(k, (And, Or)):
            for child in k.children:
                walk(child)
        elif isinstance(k, NumericCond):
            fluents.update(_expr_fluents(k.constraint.lhs))
            fluents.update(_expr_fluents(k.constraint.rhs))
        elif isinstance(k, (Exists, Forall)):  # pragma: no cover - grounded away
            raise AssertionError("ungrounded quantifier")

    if c is not None:
        walk(c)
    return atoms, fluents


def _evaluated_fluents(c: Optional[Condition], state: State) -> Set[GroundAtom]:
    """The fluents evaluating ``c`` in ``state`` reads. Like VAL, ``and`` /
    ``or`` evaluate left to right and stop once the result is known, so a
    fluent behind a false conjunct or a true disjunct is never read."""
    if isinstance(c, NumericCond):
        return set(_expr_fluents(c.constraint.lhs)) | set(_expr_fluents(c.constraint.rhs))
    if isinstance(c, Not):
        return _evaluated_fluents(c.child, state)
    if isinstance(c, (And, Or)):
        out: Set[GroundAtom] = set()
        for child in c.children:
            out |= _evaluated_fluents(child, state)
            if child.holds(state.atoms, state.fluents) is not isinstance(c, And):
                break  # a false conjunct / true disjunct settles it
        return out
    return set()  # Lit, Equality, or no condition


class _Part:
    """One part of a happening: an instantaneous step, or the start or end
    of a durative one."""

    def __init__(self, time: float, event: str, step: int, text: str,
                 action: "PlanAction") -> None:
        self.time = time
        self.event = event
        self.step = step
        self.text = text
        self.action = action

    # conditions checked against the state before the happening
    def unmet(self, state: State) -> List[str]:
        a = self.action
        if isinstance(a, Operator):
            if a.precondition is not None:
                return _unmet(a.precondition, state)
            missing = [_atom_text(atom_tuple(x)) for x in a.precondition_pos
                       if atom_tuple(x) not in state.atoms]
            present = ["(not %s)" % _atom_text(atom_tuple(x)) for x in a.precondition_neg
                       if atom_tuple(x) in state.atoms]
            return sorted(missing) + sorted(present)
        return _literal_unmet(a, self.event, state)

    # Effects, reads and writes are taken in the state before the happening,
    # as in VAL: a conditional effect counts only when its guard holds there.
    # A guard that holds is a read for the mutex check; one that does not is
    # not. Every guard is evaluated, so the fluents it needs must have values.
    def _fired(self, state: State) -> Tuple[Set[GroundAtom], Set[GroundAtom], List[Any]]:
        """``(adds, deletes, numeric effects)`` that take effect in ``state``."""
        a = self.action
        if isinstance(a, DurativeAction):
            return ({atom_tuple(x) for x in a.effect_pos[self.event]},
                    {atom_tuple(x) for x in a.effect_neg[self.event]}, [])
        adds = {atom_tuple(x) for x in a.effect_pos}
        dels = {atom_tuple(x) for x in a.effect_neg}
        nums = list(a.effect_num)
        for ce in a.conditional_effects:
            if ce.condition.holds(state.atoms, state.fluents):
                adds |= {atom_tuple(x) for x in ce.add}
                dels |= {atom_tuple(x) for x in ce.dele}
                nums.extend(ce.num)
        return adds, dels, nums

    def reads(self, state: State) -> Tuple[Set[GroundAtom], Set[GroundAtom]]:
        """``(atoms, fluents)`` the conditions, the guards that hold and the
        fired effects read."""
        a = self.action
        if isinstance(a, DurativeAction):
            return ({atom_tuple(x) for x in a.condition_pos[self.event]
                     | a.condition_neg[self.event]}, set())
        atoms, fluents = _cond_reads(a.precondition)
        if a.precondition is None:
            atoms |= {atom_tuple(x) for x in a.precondition_pos | a.precondition_neg}
        for ce in a.conditional_effects:
            if ce.condition.holds(state.atoms, state.fluents):
                more, morefl = _cond_reads(ce.condition)
                atoms |= more
                fluents |= morefl
        for eff in self._fired(state)[2]:
            fluents.update(_expr_fluents(eff.expr))
        return atoms, fluents

    def writes(self, state: State) -> Tuple[Set[GroundAtom], Set[GroundAtom], Dict[GroundAtom, str]]:
        """``(adds, deletes, {fluent: op})`` of the fired effects."""
        adds, dels, nums = self._fired(state)
        return adds, dels, {e.head.head: e.op for e in nums}

    def undefined(self, state: State) -> List[str]:
        """Fluents this part evaluates that have no value in ``state``: those
        its precondition and every guard (fired or not) actually read, and
        the right-hand sides of its fired effects."""
        a = self.action
        if isinstance(a, DurativeAction):
            return []
        fluents = _evaluated_fluents(a.precondition, state)
        for ce in a.conditional_effects:
            fluents |= _evaluated_fluents(ce.condition, state)
        for eff in self._fired(state)[2]:
            fluents.update(_expr_fluents(eff.expr))
        return sorted(_atom_text(f) for f in fluents if f not in state.fluents)

    def effects(self, state: State) -> Tuple[Set[GroundAtom], Set[GroundAtom],
                                             List[Tuple[GroundAtom, str, float]]]:
        """``(adds, deletes, numeric updates)``, the updates as
        ``(fluent, op, value)`` for :func:`apply_numeric`."""
        adds, dels, nums = self._fired(state)
        return adds, dels, [(e.head.head, e.op, e.expr.value(state.fluents)) for e in nums]


def _literal_unmet(a: DurativeAction, when: str, state: State) -> List[str]:
    missing = [_atom_text(atom_tuple(x)) for x in a.condition_pos[when]
               if atom_tuple(x) not in state.atoms]
    present = ["(not %s)" % _atom_text(atom_tuple(x)) for x in a.condition_neg[when]
               if atom_tuple(x) in state.atoms]
    return sorted(missing) + sorted(present)


_ADDITIVE = {"increase", "decrease"}


def _mutex(parts: List[_Part], state: State) -> Optional[Tuple[_Part, _Part, str]]:
    """The first interfering pair of parts in one happening, with the atom
    or fluent they contend for. Simultaneous increases / decreases of a
    fluent do not interfere; they accumulate."""
    io = [(p, p.reads(state), p.writes(state)) for p in parts]
    for i, (p, (pr, prf), (pa, pd, pf)) in enumerate(io):
        for q, (qr, qrf), (qa, qd, qf) in io[i + 1:]:
            clash = (pa & qd) | (pd & qa) | ((pa | pd) & qr) | ((qa | qd) & pr)
            if clash:
                return p, q, _atom_text(min(clash))
            fl = (set(pf) & qrf) | (set(qf) & prf) | {
                f for f in set(pf) & set(qf) if not {pf[f], qf[f]} <= _ADDITIVE}
            if fl:
                return p, q, _atom_text(min(fl))
    return None


# -- execution -------------------------------------------------------------

def check_supported(dp: "DomainProblem") -> None:
    """Raise :class:`PlanValidationError` if a plan on ``dp`` cannot be
    judged faithfully (see the module docstring)."""
    if getattr(dp, "syntax_errors", 0):
        raise PlanValidationError(
            "the domain or problem has syntax errors; run `pddlpy validate`")
    unsupported = dp.requirements() - VALIDATION_CAPABILITIES
    if unsupported:
        raise PlanValidationError(
            "plan validation does not support %s" % sorted(unsupported))
    if not dp.problem.simple_goal:
        raise PlanValidationError(
            "plan validation supports only goals that are a conjunction of atoms (#138)")


def _resolve(dp: "DomainProblem", steps: List[PlanStep]) -> Tuple[List[_Part], Optional[Failure]]:
    """Ground every step and lay out its happening parts, or report the
    first malformed step."""
    actions = {n.lower(): n for n in list(dp.operators()) + list(dp.durative_operators())}
    objects = {o.lower(): o for o in dp.worldobjects()}
    initial = State.from_problem(dp)
    parts: List[_Part] = []

    def fail(kind: str, msg: str, i: int, s: PlanStep) -> Tuple[List[_Part], Failure]:
        return parts, Failure(kind, "step %d %s: %s" % (i, s, msg), i, str(s), s.time, (), initial)

    for i, s in enumerate(steps, 1):
        try:
            _number(s.time), _number(s.duration)
        except (TypeError, ValueError):
            raise PlanValidationError(
                "step %d %s: time and duration must be finite numbers" % (i, s))
        name = actions.get(s.name.lower())
        if name is None:
            return fail("unknown-action", "the domain has no action %r" % s.name, i, s)
        is_durative = name in dp.domain.durative_operators
        lifted = (dp.domain.durative_operators if is_durative else dp.domain.operators)[name]
        if is_durative and not lifted.simple:
            raise PlanValidationError(
                "plan validation supports only durative actions with a fixed "
                "duration and literal conditions and effects; %s has more "
                "(#139, #143)" % name)
        params = list(lifted.variable_list.items())
        if len(s.args) != len(params):
            return fail("arity", "%s takes %d arguments, got %d"
                        % (name, len(params), len(s.args)), i, s)
        args = list(s.args)
        if all(isinstance(a, _Binding) for a in args) and args:
            by_var = {a.variable: a for a in args}  # type: ignore[attr-defined]
            if set(by_var) != {v for v, _ in params}:
                return fail("arity", "%s takes parameters %s"
                            % (name, " ".join(v for v, _ in params)), i, s)
            args = [by_var[v] for v, _ in params]
        binding: Dict[str, str] = {}
        for (var, typ), arg in zip(params, args):
            obj = objects.get(str(arg).lower())
            if obj is None:
                return fail("unknown-object", "the problem has no object %r" % str(arg), i, s)
            if obj not in dp.candidate_objects(typ):
                return fail("type", "%s is not of type %s (parameter %s)"
                            % (obj, typ, var), i, s)
            binding[var] = obj
        action = dp.ground(name, binding)
        text = "(%s)" % " ".join([name] + [binding[v] for v, _ in params])
        time = float(i) if s.time is None else s.time
        if not is_durative:
            parts.append(_Part(time, "action", i, text, action))
            continue
        if s.duration is None:
            return fail("duration", "durative action %s needs a [duration] (%g)"
                        % (name, lifted.duration), i, s)
        if not abs(s.duration - lifted.duration) < TOLERANCE:
            return fail("duration", "duration %g, but %s takes %g"
                        % (s.duration, name, lifted.duration), i, s)
        parts.append(_Part(time, "start", i, text, action))
        parts.append(_Part(time + s.duration, "end", i, text, action))
    return parts, None


def _happenings(parts: List[_Part]) -> Iterator[List[_Part]]:
    """Group time-sorted parts into happenings, as VAL does."""
    ordered = sorted(parts, key=lambda p: p.time)  # stable: plan order on ties
    i = 0
    while i < len(ordered):
        t0 = ordered[i].time
        j = i
        while j < len(ordered) and ordered[j].time <= t0 + TOLERANCE / 10:
            j += 1
        yield ordered[i:j]
        i = j


def simulate(dp: "DomainProblem", steps: List[PlanStep]) -> Simulation:
    """Execute ``steps`` from the initial state of ``dp``. Returns the state
    after each happening part, up to the first failure. The goal is not
    checked (see :func:`validate_plan`)."""
    check_supported(dp)
    state = State.from_problem(dp)
    parts, failure = _resolve(dp, steps)
    if failure is not None:
        return Simulation((), failure, state)
    trace: List[TracePoint] = []
    active: Dict[int, _Part] = {}  # step -> its start part, while running

    def fail(kind: str, msg: str, p: _Part, unmet: List[str], at: State) -> Simulation:
        f = Failure(kind, "step %d %s at time %g: %s" % (p.step, p.text, p.time, msg),
                    p.step, p.text, p.time, tuple(unmet), at)
        return Simulation(tuple(trace), f, at)

    for happening in _happenings(parts):
        for p in happening:
            unmet = p.unmet(state)
            undefined = p.undefined(state)
            if unmet:
                kind = "end-condition" if p.event == "end" else "precondition"
                msg = "%s not satisfied" % (
                    "at end conditions" if p.event == "end" else "preconditions")
                if undefined:
                    msg += "; no value for %s" % ", ".join(undefined)
                return fail(kind, msg, p, unmet, state)
            if undefined:
                return fail("undefined-fluent", "reads fluents with no value",
                            p, undefined, state)
        clash = _mutex(happening, state) if len(happening) > 1 else None
        if clash:
            p, q, what = clash
            return fail("mutex", "interferes with step %d %s over %s "
                        "(separate them in time)" % (q.step, q.text, what), p, [what], state)
        adds: Set[GroundAtom] = set()
        dels: Set[GroundAtom] = set()
        updates: List[Tuple[GroundAtom, str, float]] = []
        for p in happening:
            a, d, u = p.effects(state)
            adds |= a
            dels |= d
            updates.extend(u)
        state = State((state.atoms - dels) | adds, apply_numeric(state.fluents, updates))
        for p in happening:
            if p.event == "start":
                active[p.step] = p
            elif p.event == "end":
                del active[p.step]
        for p in sorted(active.values(), key=lambda p: p.step):
            unmet = _literal_unmet(p.action, "over", state)  # type: ignore[arg-type]
            if unmet:
                return fail("invariant", "over all conditions broken", p, unmet, state)
        trace.extend(TracePoint(p.time, p.event, p.step, p.text, state) for p in happening)
    return Simulation(tuple(trace), None, state)


def validate_plan(dp: "DomainProblem", steps: List[PlanStep]) -> Validation:
    """Check that ``steps`` executes from the initial state of ``dp`` and
    reaches its goal. Raises :class:`PlanValidationError` when the plan
    cannot be judged."""
    sim = simulate(dp, steps)
    if sim.failure is not None:
        return Validation(False, sim.failure, sim)
    missing = sorted(_atom_text(atom_tuple(g)) for g in dp.goals()
                     if atom_tuple(g) not in sim.state.atoms)
    if missing:
        f = Failure("goal", "goal not satisfied after %d steps" % len(steps),
                    None, None, None, tuple(missing), sim.state)
        return Validation(False, f, sim)
    return Validation(True, None, sim)
