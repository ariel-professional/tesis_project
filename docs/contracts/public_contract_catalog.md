# Public contract catalog — schema version 1.0.0

Status: **approved**  
Decision class: `APPROVED_NOW`  
Scope: Increment 1 public JSON contracts

`1.0.0` was rebased in place on 2026-08-10 while still pre-release, under
ADR-0019 and ADR-0020. Workspaces produced before that rebaseline have no
compatibility or migration guarantee and must be regenerated; they are never
rewritten automatically.

This document is normative through section 3.8 of
`instructions.agent/increment_1_master.instructions.md`. It is the exhaustive
input for generating `schemas/1.0.0/` on demand; generated CORE schema files are
not stored in this repository (ADR-0053). The source-locked pipeline, lifecycle,
and persistence rules remain in `docs/reference/contracts/IMPLEMENTATION_SPEC_AI.md`.

## 1. Global rules

- Every object is strict: unknown properties are rejected.
- Every persisted document and public message contains `schema_version:
  "1.0.0"`.
- Persisted JSON is UTF-8 without BOM, sorted by key, indented by two spaces,
  and ends with one LF. Hash inputs use the compact source-locked
  canonicalization instead.
- Semantic strings are Unicode NFC, including `RelativePath`, cancellation
  reasons, and system-generated messages. Candidate values and object keys
  inside `InlineSource.edges`, candidate files, echoed candidate diagnostics,
  and opaque `StructuredError.details` are preserved byte-for-byte. Timestamps
  are RFC 3339 UTC with exactly millisecond precision and `Z`.
- Persisted outputs emit every declared property. Unavailable values are
  explicit `null`; omission is allowed only for the input default
  `persistence.persist_events=false`.
- Public integers are strict JSON integers: booleans and floats are never
  coerced. Bounded ordinals, limits, durations in milliseconds, seeds, and
  vertex identifiers remain JSON integers.
- `LargeNonNegativeInteger` is an integer in `0..9007199254740991`, or a
  decimal string for larger values matching `^[1-9][0-9]*$`.
- `Hash` matches `^sha256:[0-9a-f]{64}$`. `RelativePath` uses POSIX `/`, is
  relative, non-empty, contains no `.` or `..` segment, and must remain inside
  the resolved workspace after symlink resolution.
- `RunId` is a canonical lower-case UUID v4. `ExperimentId` matches
  `^[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?$`.
- A CLI `RunReference` is either a canonical `RunId` or a case-insensitive UUID
  prefix with canonical hyphens. Mutating/inspection commands require at least
  eight hexadecimal digits and resolve exactly one current run before invoking
  application services. `list-runs --prefix` accepts one to 32 hexadecimal
  digits after removing canonical hyphens and returns every matching run.
- Human-facing text, CLI help, diagnostics, structured messages, and Markdown
  reports are English.

Unless a model below explicitly says otherwise, every listed property is
required and non-null.

## 2. Experiment configuration

### 2.1 `ExperimentConfig`

Properties, exactly: `schema_version`, `n`, `source`, `methods`,
`integer_limits`, `persistence`, `counting_convention`.

- `n`: integer `1..integer_limits.max_n`.
- `counting_convention`: literal `undirected_paths_reverse_identified`.
- `source`: discriminated by `kind`.
- `methods`: `MethodsConfig`.
- `integer_limits`: `IntegerLimits`.
- `persistence`: `PersistenceConfig`.

`ExperimentConfig` validates its envelope, discriminants, strict primitive
types, generator parameter ranges, path syntax, and numeric limits. It does
not validate edge shape, endpoint type/range, loops, duplicates, cycles, or
degree. The sole exception is that any float anywhere under an inline source
is rejected because `run_config_hash` admits no floats.

### 2.2 Sources

- `InlineSource`: `{kind: "inline", edges: JsonValue[]}`. `JsonValue` is null,
  boolean, integer, string, array, or string-keyed object recursively; floats
  are forbidden. Candidate strings and keys are opaque and are not NFC
  normalized. Edge errors survive unchanged to stage 3.
- `FileSource`: `{kind: "file", path: RelativePath}`. Existence, confinement,
  byte limit, decoding, and JSON parsing occur in stage 2. The file is a direct
  top-level JSON array and never contains `n`.
- `GeneratorSource`: `{kind: "generator", family: GeneratorFamily,
  generator_version: "builtin-v1", seed: integer 0..9223372036854775807,
  parameters: GeneratorParameters}`. `parameters` is discriminated by the
  selected family and contains only the properties listed below.

Input files are checked against `input_max_bytes` before parsing, decoded as
strict UTF-8 without BOM, allow JSON whitespace, and reject NaN/Infinity.

### 2.3 Generator catalog `builtin-v1`

| `family` | exact `parameters` | configuration invariant |
|---|---|---|
| `empty` | `{}` | none |
| `matching` | `{edge_count: int}` | `0 <= edge_count <= floor(n/2)` |
| `single_path` | `{edge_count: int}` | `0 <= edge_count <= n-1` |
| `multiple_paths` | `{component_edge_lengths: int[]}` | each `>=1`; sum of `(length+1)` is `<=n` |
| `invalid_loop` | `{}` | `n>=1` |
| `invalid_duplicate` | `{}` | `n>=2` |
| `invalid_vertex_out_of_range` | `{direction: "below"|"above"}` | `n>=1` |
| `invalid_cycle` | `{cycle_length: int}` | `3 <= cycle_length <= n` |
| `invalid_degree3` | `{}` | `n>=4` |

The generator derives a stable vertex ordering by sorting vertices by
`SHA256(b"builtin-v1\0" + seed-ascii + b"\0" + b"0" + b"\0" +
vertex-ascii)` with vertex as the tie-breaker. For `builtin-v1`,
`counter-ascii` is exactly the one-byte literal `"0"` for every vertex. It never depends on
`random.Random`. Invalid families intentionally materialize a candidate that
fails in stage 3 or 4; malformed JSON is exercised through inline/file input.

### 2.4 Methods, persistence, and limits

- `MethodsConfig`: `{exact: {engine: "auto"}, reference:
  {engine: "bruteforce_python_v1"}}`. Both properties are mandatory; there is
  no `enabled` flag.
- `PersistenceConfig`: `{policy: "normal"|"debug", persist_events: bool}`.
  Only `persist_events` may be omitted on input and then materializes as
  `false`. Debug only adds rotated `runner.log` detail and stack traces.
- `IntegerLimits` contains exactly these mandatory integers:

| property | range | basal value |
|---|---:|---:|
| `max_n` | entero positivo, sin máximo del programa | 12 |
| `reference_max_n` | entero positivo, sin máximo del programa | 10 |
| `exact_timeout_ms` | entero positivo, sin máximo del programa | 30000 |
| `reference_timeout_ms` | entero positivo, sin máximo del programa | 30000 |
| `cancellation_grace_ms` | entero no negativo, sin máximo del programa | 1000 |
| `control_connect_timeout_ms` | entero positivo, sin máximo del programa | 1000 |
| `control_response_timeout_ms` | entero positivo, sin máximo del programa | 1000 |
| `control_max_message_bytes` | entero positivo, sin máximo del programa | 16384 |
| `input_max_bytes` | entero positivo, sin máximo del programa | 1048576 |
| `event_max_payload_bytes` | entero positivo, sin máximo del programa | 65536 |
| `worker_max_message_bytes` | entero positivo, sin máximo del programa | 65536 |
| `runner_log_max_bytes` | entero positivo, sin máximo del programa | 5242880 |
| `runner_log_backup_count` | entero no negativo, sin máximo del programa | 3 |

The basal values are fixture values, not input defaults.
The persisted values are the complete operational policy for the experiment;
the program does not apply additional maxima or silent clamps.

`run_config_hash` is SHA-256 over compact, sorted-key, UTF-8 JSON with all
defaults materialized and no final LF. Semantic fields use their already NFC
normalized representation. The complete inline candidate subtree remains
opaque and byte-sensitive, so invalid candidates differing only by NFD/NFC may
have different hashes. `instance_hash` remains SHA-256 over only `n`,
`vertex_base:1`, and canonical integer edges.

## 3. Common models

- `ArtifactRef`: `{path: RelativePath, sha256: Hash, size_bytes:
  LargeNonNegativeInteger}`.
- `ProducerRef`: `{id: non-empty ASCII token max 64, version: non-empty ASCII
  token max 64}`.
- `Cancellation`: `{requested_at: Timestamp, origin: "cli", reason:
  string|null}`; reason length `0..512` when non-null.
- `StructuredError`: `{schema_version, code: ErrorCode,
  domain_error_code: int|null, message: string, recoverable: bool, details:
  object, stage: StageId|null}`. Message length is `1..512`; details has at
  most 32 keys, depth 4, and a serialized size bounded by the applicable
  message/payload limit. A basal domain symbol must carry its mapped integer;
  a general symbol must carry null.
- `Diagnostic`: `{code: ErrorCode, domain_error_code: int|null, message:
  string, edge_index: int|null, edge: JsonValue|null}`. Diagnostics are sorted
  by error precedence, then edge index, then canonical JSON.
- `AttemptMetrics`: `{duration_ms: int, worker_duration_ms: int|null,
  candidates_examined: LargeNonNegativeInteger|null, peak_memory_bytes:
  LargeNonNegativeInteger|null, producer: ProducerRef|null}`.

## 4. Persisted entities

### 4.1 Candidate and instance

- `InstanceCandidate`: `{schema_version, n: int, edge_data: JsonValue[],
  source_metadata: SourceMetadata}`.
- `Instance`: `{schema_version, n: int, vertex_base: 1, edges: Edge[],
  source_metadata: SourceMetadata, instance_hash: Hash}`.
- `Edge` is a two-item integer array `[u,v]` with `1<=u<v<=n`; the outer list
  is lexicographically sorted and unique.
- `SourceMetadata` is discriminated by `kind`:
  - inline: `{kind:"inline"}`;
  - file: `{kind:"file", path:RelativePath, sha256:Hash,
    size_bytes:LargeNonNegativeInteger}`;
  - generator: `{kind:"generator", family:GeneratorFamily,
    generator_version:"builtin-v1", seed:int, parameters:GeneratorParameters}`.

### 4.2 Run and pipeline

- `Versions`: `{app: ProducerRef, schema: ProducerRef, pipeline: ProducerRef,
  problem: ProducerRef, generator: ProducerRef|null, exact: ProducerRef|null,
  reference: ProducerRef|null}`. IDs are fixed respectively to
  `tesis-proyect@0.1.0`, `public-json@1.0.0`, `increment-1@1.0.0`,
  `undirected-path-extension@1.0.0`, `builtin@builtin-v1`,
  `linear-forest-closed-form@1`, and `bruteforce-python@1`. Generator is null
  unless used; exact identifies the closed-form producer.
- `RunManifest`: `{schema_version, run_id, experiment_id, run_config_hash,
  instance_hash: Hash|null, counting_convention, versions, status,
  created_at, updated_at, cancellation: Cancellation|null}`.
- `PipelineState`: `{schema_version, pipeline_version:"1.0.0",
  ordered_stages: StageState[10]}`.
- `StageState`: `{ordinal:int 1..10, stage:StageId, status:StageStatus,
  attempt_count:int>=0, result:ArtifactRef|null}`. The stage IDs and ordinals
  are the source-locked ten-stage order. Pending/running states have null
  result; terminal states have a reference to their numbered stage document.

### 4.3 Stage results and outcomes

- `StageResult`: `{schema_version, stage, status:StageTerminalStatus,
  attempts:StageAttempt[], started_at:Timestamp, finished_at:Timestamp,
  duration_ms:int>=0, error:StructuredError|null, artifacts:ArtifactRef[],
  outcome:StageOutcome|null}`.
- `StageAttempt`: `{number:int>=1, started_at, finished_at, duration_ms:int>=0,
  status:StageTerminalStatus, error:StructuredError|null, skip:
  SkipCause|null, metrics:AttemptMetrics, termination:
  "not_applicable"|"cooperative"|"forced"}`.
- Attempts are consecutive, ordered, and non-empty. The top-level timestamps
  and status mirror the last attempt. Success has null error/skip; failed has
  error; skipped has skip; cancelled has `RUN_CANCELLED`. An interrupted open
  attempt is closed as failed with `RUNNER_INTERRUPTED`; the interruption
  detection time is its `finished_at`.
- `SkipCause`: `{kind:"own"|"dependency", code:ErrorCode, message:string}`.
  Own skips are only the two allowed omissions; dependency skips name the
  causal stable error and cannot use either own-skip symbol.
- `StageOutcome` is discriminated by `kind` and must match the stage:
  `definition` `{kind, config_hash}`, `candidate` `{kind, candidate}`,
  `edge_validation` `{kind, validation, instance}`, `forest_validation`
  `{kind, validation}`, `structure_analysis` `{kind, analysis}`,
  `exact_counting` `{kind, result}`, `reference_counting` `{kind, result}`,
  `comparison` `{kind, result}`, `metrics_collection` `{kind, stages:
  StageMetricSummary[8]}`, or `report_export` `{kind, json_report, markdown_report}`.
  Nullable references inside an outcome are explicit. A dependency skip may
  use null outcome.
- `StageMetricSummary`: `{stage, attempt_number:int>=1,
  status:StageTerminalStatus, termination, metrics:AttemptMetrics}`. Stage 09
  contains exactly one record for each stage 01–08, in canonical order, from
  the last confirmed attempt. Complete history remains only in each
  `StageResult.attempts`; stages 09 and 10 never receive fictitious metrics.

### 4.4 Domain results

- `ValidationResult`: `{schema_version, valid:bool, errors:Diagnostic[],
  warnings:Diagnostic[]}`. Invalid means at least one error; validation
  collects every deterministically detectable error.
- `PathComponent`: `{vertices:int[], edges:Edge[], edge_length:int>=1}`. Each
  component is oriented toward the lexicographically smaller of its two
  traversals; components are sorted by their vertex arrays.
- `LinearForestAnalysis`: `{schema_version, components:PathComponent[],
  component_lengths:int[], free_vertices:int[], free_vertex_count:int>=0,
  blocks:int>=1, case_type:"empty"|"hamiltonian_path_extreme"|"single_edge"|
  "matching"|"single_path"|"multiple_paths"}`.
  Component lengths mirror components; free vertices are ascending; blocks is
  component count plus free-vertex count. Classification uses that exact order:
  no components; one component spanning all `n` vertices; one length-one
  component; at least two length-one components; one remaining component; or
  multiple remaining components. Thus `K_2` with its edge is Hamiltonian
  extreme, while one edge with free vertices is `single_edge`.
- `CountingResult` is discriminated by `status`:
  - success: `{schema_version,status:"success",value:LargeNonNegativeInteger,
    engine:ProducerRef,formulation:string,counting_convention,metrics:
    AttemptMetrics,instance_hash:Hash,skip:null}`;
  - skipped: `{schema_version,status:"skipped",value:null,engine:ProducerRef,
    formulation:string|null,counting_convention,metrics:AttemptMetrics,
    instance_hash:Hash,skip:SkipCause}`.
  The metrics producer equals the engine. A skipped result contains an own
  skip only.
- `ComparisonResult` is discriminated by `status`:
  - match/mismatch: `{schema_version,status,value_exact,value_reference,
    exact:ProducerRef,reference:ProducerRef,counting_convention,reason:null,
    instance_hash}`;
  - not_applicable: the same keys, with nullable values/producers and
    `reason:SkipCause` non-null.
  A mismatch is a scientifically valid terminal comparison and does not fail
  the run. Before comparing values, stage 08 verifies both `instance_hash`
  values, the configured counting convention, and the expected exact/reference
  producer identities. Unreadable or incompatible evidence makes stage 08
  `failed/INTEGRITY_ERROR`; stages 09 and 10 still produce metrics and a
  diagnostic report without inventing a comparison.
- `ReportSummary`: `{schema_version, run_id, experiment_id, run_status,
  instance:Instance|null, structure:LinearForestAnalysis|null, methods:
  {exact:CountingResult|null,reference:CountingResult|null}, comparison:
  ComparisonResult|null, metrics:StageMetricSummary[8]|null, diagnostics:
  Diagnostic[]}`. It reuses the confirmed stage 09 outcome and never traverses
  attempts to synthesize another metrics history.

## 5. Events, inspection, and command output

The global `--workspace PATH` option is optional. Workspace selection precedence
is the explicit option, non-empty `TESIS_PROYECT_WORKSPACE`, then shallow
discovery from the invocation's current directory. Explicit and environment
paths may be relative to that directory or absolute; an invalid selected path
fails without fallback.

Fallback recognizes a real directory containing real `experiments` and `runs`
directories. It first tests the current directory, then only its immediate real
subdirectories and those two expected children; it does not inspect files,
descend further, or search parents. One candidate is selected. Multiple
candidates fail with usage exit 64 and a deterministic relative-path list. An
inaccessible child is skipped with a stderr warning.

With no candidate, an empty current directory is initialized in place. An
occupied directory uses the lowest reusable or creatable
`tesis_workspace[_n]`: valid workspaces precede empty candidates, which precede
the lowest free name. Files, symlinks, partial layouts, and occupied invalid
candidates are preserved as collisions. Initialization creates empty
`experiments` and `runs` directories; it creates no experiment or run.

`EventEnvelope` has exactly `{schema_version,event,run_id:RunId|null,
timestamp,stage:StageId|null,payload}`. Payload variants are:

| event | exact payload |
|---|---|
| `run_created` | `{status:"created"}` |
| `run_started` | `{status:"running"}` |
| `run_resumed` | `{status:"running",from_stage:StageId}` |
| `run_interruption_detected` | `{status:"running",stage:StageId|null}` |
| `stage_started` | `{status:"running",attempt:int}` |
| `stage_terminal` | `{status:StageTerminalStatus,attempt:int,result:ArtifactRef}` |
| `cancellation_accepted` | `{status:"accepted",requested_at:Timestamp}` |
| `report_exported` | `{status:"success",json_report:ArtifactRef,markdown_report:ArtifactRef}` |
| `run_terminal` | `{status:"completed"|"failed"|"cancelled"}` |
| `diagnostic` | `{error:StructuredError}` |

Events never embed complete manifests, outcomes, or scientific artifacts.
`diagnostic` alone may have null run ID. NDJSON is one object per LF line.

- Successful `save-experiment`: exit 0, no stdout.
- Successful `create-run`: one `run_created` event containing the run ID in
  the envelope. Optional `--copy-run-id` copies that complete ID only after the
  run is durable; clipboard failure warns on stderr but keeps exit 0 and the
  unchanged event.
- `list-runs [--experiment ID] [--prefix PREFIX] [--format human|ndjson]` creates
  or modifies no experiment or run and has no `--status` option. Fallback may
  initialize the empty workspace container before the query. `human` is the default. Results are
  ordered by `created_at` descending and then `run_id` ascending. Filters combine
  with AND. Human output is a table on stdout; NDJSON emits one validated
  `RunManifest` per line. Empty results emit `No runs found.` in human format or
  zero NDJSON lines. Matching invalid run directories are omitted with warnings
  on stderr and exit 0; failure to enumerate the runs root is fatal.
- `run`/`resume`/`cancel`/`export`: their applicable events only.
- `inspect --format ndjson`: exactly one `RunInspection` line without stage,
  or one `StageInspection` line with stage.
- `inspect --format human`: English human text on stdout; all other human
  diagnostics use stderr.
- Human run inspection derives, without mutation, the available instance,
  structure, method results, comparison, diagnostics, pipeline summary,
  conclusion, report paths, and status-dependent actions. Human stage
  inspection shows attempt timing, termination, producer, metrics, error or
  skip, outcome kind, validation summary, and artifact references.
- Human inspection may explain persisted evidence but never invents a result.
  The NDJSON forms remain the exact `RunInspection` and `StageInspection`
  schemas below and do not embed scientific artifact contents.
- `RunInspection`: `{schema_version,view:"run",run:RunManifest,
  pipeline:PipelineState}`.
- `StageInspection`: `{schema_version,view:"stage",run_id,stage,
  result:StageResult}`.
- Cancellation of an active runner is a controlled outcome and the runner
  exits 0. Cancel on a terminal run returns a response/event with terminal
  status, exits 0, and does not mutate files.
- Resume accepts failed runs, completed runs for an integrity check/repair, and
  running runs proven interrupted; it rejects created, cancelled, and active
  runs. It validates config/hash/version, scans numbered StageResults even when
  the pipeline is behind, validates required artifacts and scientific identity,
  repairs manifests, and recomputes from the first non-integral checkpoint.
  Parseable attempt history is preserved; an unreadable StageResult begins a
  new recoverable history and emits a diagnostic. A missing superseded
  candidate is valid while stage 03 remains integral; otherwise recovery rolls
  back to stage 02. Report-only damage recomputes only stage 10. Export accepts completed,
  failed, and cancelled runs and never creates an attempt or mutates pipeline.
- Cancelling a `created` run persists ten `skipped/RUN_CANCELLED` StageResults,
  starts no stage, and creates no reports. Cancel reloads `run.json` after
  acquiring the lock; an abandoned `running` run emits
  `run_interruption_detected` before reconciliation and terminalization.

### 5.1 Interactive execution presentation

- Execution services expose an internal, transport-neutral observer port.
  Public events and terminal presentation are independent adapters.
- When `stderr` is a TTY, the terminal adapter may render English command and
  stage progress, confirmed summaries, and a copyable next command. It is
  silent when `stderr` is not a TTY.
- After `create-run`, interactive output shows the complete UUID, its shortest
  currently unique compact reference with at least eight digits, and a next
  command using that reference. The full UUID remains canonical.
- Stage progress is displayed as `Stage n/10`; there is no overall percentage
  bar. Continuous progress is limited to stages 6 and 7. Percentages require a
  known total; otherwise progress is explicitly indeterminate.
- Interactive durations label elapsed and estimated remaining time explicitly.
  They use adaptive Spanish units: seconds; minutes/seconds; hours/minutes/seconds
  below 24 hours; then the two largest units among days/hours, months/days, or
  years/months. Visual conversion fixes one month at 30 days and one year at 365
  days; zero-valued lower units are omitted and thousands use `.` separators.
  Before an ETA exists, the terminal displays `calculando…`.
- Interactive output is not an automation API, is not persisted, and cannot be
  used as evidence. Public stdout, NDJSON event payloads, schemas, and command
  grammar remain unchanged.

## 6. Worker protocol

Every worker uses multiprocessing `spawn`, writes no persistent files, and
handles one request and one response. A frame is a four-byte unsigned
big-endian length followed by strict UTF-8 JSON. The declared length and
payload must not exceed `worker_max_message_bytes`; EOF, invalid UTF-8/JSON,
extras, version mismatch, request mismatch, invalid result, and unexpected
termination are general stable errors.

- `WorkerRequest`: `{schema_version,request_id:RunId,run_id:RunId,
  stage:"run_exact_method"|"run_reference_method",instance:Instance,
  producer:ProducerRef,limits:{timeout_ms:int,max_message_bytes:int,
  reference_max_n:int},counting_convention}`.
- `WorkerResponse` is discriminated by `status` and always has exactly
  `{schema_version,request_id,run_id,stage,status,result,error,metrics}`:
  success has result and null error; skipped has a skipped counting result and
  null error; failed has null result and non-null error.
- Cancellation uses a separate one-byte channel. Byte `0x01` means cancel;
  EOF also requests cooperative shutdown. After `cancellation_grace_ms` the
  runner force-terminates and records the termination mode.
- Workers may use a separate one-way, fixed-size internal telemetry channel for
  monotonic progress counters. Its counters use canonical decimal fields able
  to preserve finite-float-range totals exactly. When a total exceeds that
  internal presentation range, telemetry becomes indeterminate instead of
  failing the scientific computation. Telemetry is bounded, best-effort, never
  extends a timeout, never changes the single request/response exchange, and is
  never persisted or exposed as a public event.
- A worker may send bounded internal fault diagnostics to the runner through a
  separate one-way channel. The runner records phase and exception type in the
  normal log; debug policy also records the bounded message and traceback. This
  channel is not a public protocol and the worker still performs no persistent
  writes.

## 7. Local control protocol

The control request/response fields and idempotent ordering remain those in
master section 3.5. Endpoint identity is:

```text
SHA256(b"tesis-proyect-control-v1\0"
       + canonical_workspace_utf8
       + b"\0"
       + canonical_run_uuid_ascii)
```

The workspace is `Path.resolve(strict=True)` and Unicode NFC. Windows then
applies `normcase` and converts separators to `/`. Unix uses the resolved NFC
POSIX path. The UUID is canonical lower-case ASCII.

Unix endpoint: `ctl-<digest>.sock` under a safe
`$XDG_RUNTIME_DIR/tesis-proyect`; otherwise under the platform temporary root
in `tesis-proyect-<uid>`. The directory is owned by the user and mode `0700`;
the socket is `0600`. If the resulting native path exceeds the platform Unix
socket limit, control fails with `RUN_CONTROL_UNAVAILABLE` rather than
truncating identity.

Windows endpoint: `\\.\pipe\tesis-proyect-ctl-<digest>`. The conditional
`pywin32` implementation creates and verifies a DACL containing only the
current logon SID and required system/administrator access. A default DACL is
not accepted. Endpoint existence is never proof of activity; the execution
lock remains authoritative.

## 8. Error catalog

Basal mappings are immutable:

1 `MALFORMED_EDGE`; 2 `LOOP_EDGE`; 3 `DUPLICATE_EDGE`; 4
`VERTEX_OUT_OF_RANGE`; 5 `CYCLE_DETECTED`; 6 `MAX_DEGREE_EXCEEDED`; 7
`BRUTE_FORCE_LIMIT_EXCEEDED`; 8 `EXACT_ENGINE_NOT_AVAILABLE`; 9
`STAGE_TIMEOUT`; 10 `RUN_CANCELLED`; 11 `RUN_ALREADY_ACTIVE`; 12
`RUN_LOCK_UNAVAILABLE`; 13 `RUN_CONTROL_UNAVAILABLE`; 14
`RUNNER_INTERRUPTED`.

General stable symbols, all with `domain_error_code=null`:

`USAGE_ERROR`, `CONFIG_INVALID`, `SCHEMA_INVALID`, `VERSION_UNSUPPORTED`,
`NOT_FOUND`, `ID_COLLISION`, `PATH_OUTSIDE_WORKSPACE`, `INPUT_TOO_LARGE`,
`INPUT_BOM_FORBIDDEN`, `INPUT_DECODE_FAILED`, `INPUT_JSON_INVALID`,
`INTEGRITY_ERROR`, `RUN_STATE_INVALID`, `WORKER_MESSAGE_TOO_LARGE`,
`WORKER_PROTOCOL_ERROR`, `WORKER_TERMINATED`, `REPORT_UNAVAILABLE`,
`IO_ERROR`, and `INTERNAL_ERROR`.

## 9. Rejection boundary examples

| input/problem | rejection point |
|---|---|
| missing limit, method, source discriminant, extra key, coercible string integer | save-experiment/config validation |
| float anywhere in inline source | save-experiment/config validation |
| inline malformed edge, non-integer endpoint, loop, duplicate, out of range | stage 3 |
| file missing, escapes workspace, too large, BOM, invalid UTF-8/JSON, non-array top level | stage 2 |
| file array containing floats or other malformed edge values | stage 3 |
| cycle or degree 3 | stage 4 |
| generator parameter impossible for `n` | save-experiment/config validation |
| invalid generator family intentionally emitted | stage 3 or 4 according to family |

A minimal valid inline configuration contains all seven top-level properties,
both methods, all thirteen limits, persistence policy, and counting convention.
An inline `edges:[[1,2,3]]` configuration is valid as configuration and later
produces `MALFORMED_EDGE`; replacing `3` with `3.0` makes the configuration
itself invalid. This distinction is contractual.
