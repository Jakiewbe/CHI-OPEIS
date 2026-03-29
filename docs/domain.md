# Domain Design

`opeis_master.domain` is the stable typed domain surface for OPEIS Master.
It exists to give the UI, application, renderer, and tests a shared contract
without embedding calculation logic in the GUI layer.

## Scope

The domain layer currently owns:

- current input normalization
- C-rate and current conversion helpers
- segmented cumulative timepoint planning
- cumulative-time to delta-time conversion
- normalized `ScriptStep` structures for later rendering
- lightweight validation/result contracts shared by higher layers

The domain layer does not directly render CHI macro text.

## Current Input Modes

The canonical current API is:

- `CurrentInputConfig`
- `RateCurrentReference`
- `NormalizedCurrent`

Supported input paths:

1. `CurrentInputMode.DIRECT_1C`
2. `CurrentInputMode.INFERRED_FROM_RATE`

Both paths normalize into a single `NormalizedCurrent` model so downstream code
does not need separate branches.

## Timepoint Planning

Segment planning uses:

- `TimeSegment`
- `TimepointPlan`
- `expand_uniform_segment()`
- `expand_timepoint_plan()`
- `cumulative_timepoints_to_deltas()`
- `timepoint_plan_to_deltas()`

Rules:

- timepoints must be strictly increasing
- generated deltas must be strictly positive
- the first delta is measured from `initial_time` to the first cumulative point

## Normalized Steps

The normalized step contract is:

- `ScriptStep`
- `RestStepParameters`
- `ConstantCurrentStepParameters`
- `ImpedanceStepParameters`
- `OcvStepParameters`

These are intermediate typed records, not final CHI command text.

## Public API

Recommended imports:

- `from opeis_master.domain import CurrentInputConfig`
- `from opeis_master.domain import normalize_current_input`
- `from opeis_master.domain import TimeSegment, TimepointPlan`
- `from opeis_master.domain import expand_timepoint_plan, timepoint_plan_to_deltas`
- `from opeis_master.domain import ScriptStep`

## Compatibility Note

The repository still contains a `chi_generator` package used by the current GUI
compatibility path. New domain-first code should target `opeis_master.domain`
and `opeis_master.models` as the preferred contracts.
