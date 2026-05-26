# Power module — session resume notes

Living document; updated at the end of each session so the next session
can pick up from a cold start (after Claude Code context compaction).

## PLAN: PCB restart (agreed 2026-05-16, end of session 8)

User and assistant agreed to clear the PCB and start the layout
fresh. The schematic stays — it's the source of truth. Reasons:
the current board has 8 sessions of accumulated routing
decisions, autoroute artifacts, abandoned routes (CHG_OUT
stub south), under-sized power traces that can't be widened
in place (CELL_TOP B.Cu chain), and tight QFN areas (U3) that
would benefit from re-placement with breakout room.

**Pre-restart state**: 5 baseline unconnects, 8 under-sized
POWER_4A traces (now flagged by DRC custom rule), tooling
mature (find_via_lane A-H, route_trace checkObstacles,
dedupe_traces, place_near, decoupling_audit, get_component_pads
with layers, modify_trace fixed).

**Restart workflow** (next session):

  1. Read NOTES.md (this file), the project_power_module memory,
     and projects/power_module/INSTRUCTIONS.md for design intent.
  2. Snapshot current PCB state (`snapshot_project` MCP tool, or
     just `git tag pre-restart-2026-05-16`).
  3. Strip all tracks + vias from PCB (keep components for now —
     placement reset is step 4).
  4. Re-place components from scratch, organized by functional
     group:
       - Power input (USB-C J1, ESD/TVS, USB-VBUS caps)
       - Charge path (U3 BQ24xxx + decoupling + inductor L1 +
         charge-output caps)
       - BMS (U-something + cell-sense network + balance FETs)
       - Buck-boost converter (U4 + L + diode + caps)
       - Cell holder BAT1 (fixed location — board edge)
       - Output (V12_OUT + protection + connector)
     Use place_near for decoupling caps after main IC placement.
     Render with get_board_2d_view after each functional group
     for visual confirmation before continuing.
  5. **User adjustment pass** — pause here, user makes manual
     placement tweaks in pcbnew GUI.
  6. Routing pass:
       - Start with high-current trunk: BAT+/BAT-/V12_OUT
         (POWER_4A, 1.5mm). Route on F.Cu / B.Cu, avoid inner
         layers (those are pours).
       - Then cell-series chain (CELL1_TOP, CELL2_TOP — also
         POWER_4A now thanks to today's netclass fix).
       - Then medium-current (USB_VBUS, CHG_OUT, BQ_PH — POWER_2A
         0.8mm).
       - Then signals (default 0.2mm).
       - Use route_pad_to_pad with checkObstacles=true so bad
         routes are caught at the source.
       - For dense areas, use find_via_lane with minimumStubLength
         and minClearance set appropriately.
       - Run run_drc after each functional group to catch
         regressions early.
  7. **Validation pass**:
       - 0 shorts/clearance/dangling.
       - 0 unconnected (close every ratsnest).
       - 0 track_width violations (DRC custom rule).
       - decoupling_audit for IC bypass coverage.

**Things to do BEFORE restart (in this session, before compact)**:

  - All commits in place ✓
  - NOTES.md updated ✓
  - This plan section saved ✓
  - Memory updated with all feedback ✓

**Open questions for the user to weigh in on after the placement
pass**:

  - C26 BB_VCC: should we re-route around the inner-layer power
    traces (BB_SW1, BB_COMP), or accept a longer F.Cu detour?
  - Cell-sense routing topology: in the old board, the BMS IC's
    cell-sense pins tapped off the B.Cu power chain via F.Cu
    branches. Reasonable; keep that pattern?
  - Stitching vias on GND/PWR planes: how aggressive? (Current
    board had so many that 1.5mm power traces couldn't fit.)

## State at end of 2026-05-19 session (placement tooling sprint)

User and assistant spent the session building placement-quality
tooling and applying it to the board. Placement is improved but
NOT yet routable in the dense U4 / U1 areas per user assessment.
Routing did not start.

**Tooling shipped (KiCAD-MCP-Server `develop`):**

  - `#174` Auto-save fix (e48b9f7) — `_BOARD_MUTATING_COMMANDS`
    extended with `place_near` + 8 others. SWIG mutations now
    persist without explicit `save_project`.
  - `#179` `analyze_congestion` (6435207) — grid pad×ratsnest
    density hotspots with member-component rollup.
  - `#182` `get_ratsnest` (d4590c7) — per-segment ratsnest with
    pad-ref endpoints + pairwise crossing detection.
  - `#183` `relax_placement` v1 (bd9569e) — force-directed mover
    (springs along ratsnest, bbox repulsion, default anchors
    J*/SW*/BAT*/PTH).

**Board state (power_module main, commits 14a143a..307fe75):**

  - User compressed board to 95.1×66.1mm (down from 95×110mm).
  - User repositioned components to fit inside BAT1 body envelope
    (~87.5×57mm centered at (46, 31) on B.Cu).
  - I made a north-spread attempt (commit 7db712f) that moved
    components OUTSIDE BAT1 body — user reverted (b65af94).
  - I made a Q3/L2/Q4 cascade-collision mess; reverted.
  - `relax_placement` pass with ICs locked: ratsnest 1369 mm →
    1216 mm (-11%), crossings 60 → 51 (-15%), 0 errors, 21 tiny
    courtyard touches. Commit 307fe75.

**User assessment of result (2026-05-19, end-of-session):** U3 area
plausibly decluttered. U1 routing looks circuitous. U4 area
"potentially impossible" — R27 packed between two components on
wrong side of U4, R22 trace has to snake around to reach BB_FB
pin. Confirms that `relax_placement` v1's center-to-center spring
forces are insufficient — caps end up clumped at wrong fan-out
direction relative to IC pin rows.

**Agreed plan for 2026-05-20:**

  - Unify schematic + PCB autoplacers into one parameterized
    force-directed engine (task #186, plan in memory
    `project_autoplacer_unification.md`).
  - PCB-specific cost terms to add: per-net-class spring strength,
    layer-aware repulsion, skip-springs for pour-handled nets
    (GND, BAT+), pad-position springs (not component-center),
    per-pin fan-out torques.
  - Existing PCB v1 (`python/commands/pcb_autoplacer.py`) gets
    replaced. Rolls up tasks #181, #184, #185.

**Open / not-yet-routed:** Same as restart plan — POWER_4A trunk,
POWER_2A, signals, validation. Tasks #169–172 still pending.

**Routing tool gaps observed this session (#177, #178):**

  - `route_trace.checkObstacles` checks path-crossing-foreign-net
    but NOT trace-half-width vs foreign-pad clearance. My 1.5 mm
    V12_OUT trace exiting U4.13 shorted to U4.14 because the check
    passed (centerline didn't cross U4.14) even though the trace
    edge did.
  - `route_pad_to_pad` doesn't auto-narrow for IC pin escape.
    1.5 mm POWER_4A trace cannot physically exit a 0.65 mm-pitch
    HTSSOP-28 pin row — needs taper-out behavior to 0.3 mm at the
    pad, widening to 1.5 mm in open area.

**Open issues backlog:**

  - `#176` Promote stitch_pour_vias from throwaway script to MCP tool
  - `#177` route_trace trace-vs-pad clearance check
  - `#178` route_pad_to_pad pin-escape (narrow at IC, widen)
  - `#181` analyze_congestion layer-aware pad density
  - `#184` relax_placement pad-position-aware crossing metric (v2)
  - `#185` relax_placement repulsion convergence (v2)
  - `#186` Unify schematic + PCB autoplacers (the big one for tomorrow)

## 2026-05-20 — autoplacer unification shipped

Task #186 done.  Schematic + PCB autoplacers now share one
force-directed engine; PCB-specific physics opt-in via Params
flags (`use_obb_repulsion`, `use_spring_classes`,
`rotation_snap_strength`, etc.).  See memory
[project_autoplacer_unification.md][unif] for the full design.

Key v2 shipped:
  - Spring classes with 5-level hierarchy
    (connection > pad-general > net > component > default).
    Defaults DECOUPLING / LOCAL_SIGNAL / INTER_GROUP / PLANE.
  - OBB-via-SAT body repulsion with cubic-ramp force shape.
  - Lever-arm torque on pin-wise spring forces (PCB rotation).
  - Auto-classify power-net rails as PLANE (no spring force).
  - 4-phase schedule: cluster → spread → snap → relax.
  - `PCBAutoplacerViz` — async-window matplotlib viz with
    spring-class-colored ratsnest, OBB-rotated bbox, etc.

Initial real-board run on power_module produced a layout with
*shorter* MST length (-2.4%) but *more* crossings (+58%) and the
charger / buck-boost groups swapping sides of the board.  User
identified missing piece: pin classes for decoupling caps not yet
wired up (engine reads from `sess.spring_classes` but no parser
for `Pin_Spring_Class:N` properties yet — see deferred items in
the unification memory).

## 2026-05-21 — tuning session, 6 fixes landed

Six bug fixes from running v2 on the real power_module board and
inspecting the dynamics in Jupyter Lab.  Commits on
KiCAD-MCP-Server `develop` branch:

  - `784b5f4` — five fixes: rotated-bbox computation (was using
    world-AABB at current rotation; now uses local-frame bbox),
    cross-layer springs flag, lever-arm torque on pin-wise
    springs, geometric repulsion ramp (was linear → first
    increment slammed components apart), OBB axis tie-break
    stability (fixes intermittent "components jump and snap back
    in unison" symptom).
  - `76e6dbd` — pinwise lever-arm torque sign error (used math
    Y-up cross product, needed screen-Y-down CCW-visual).  R23
    case study converged to the wrong stable equilibrium.
  - `2e2bbed` — schematic torque functions skip PCB components
    (relied on per-pin outward angles that pads don't have).
  - `70ffd3b` — force-step damping prevents period-2 oscillation
    near equilibrium when force_mag < temperature.
  - `313f100` — normalize spring force by component degree;
    bounds K_eff regardless of pin count.  Was: 28-pin TSSOP had
    14× the restoring stiffness of a 2-pin resistor.

After all that, user reports the autoplacer is improved but
**still oscillates in many cases** (worse in dense clusters).
Filed task #196 to investigate further; task #195 plans a global
force-scale knob to simplify tuning.  Routing work (tasks
#169–172) remains blocked on landing a stable placement.

**Open issues + tasks added today:**
  - `#194` Unify torque mechanism (lever-arm for schematic too)
  - `#195` Global force-scale factor (planned for next session)
  - `#196` Investigate remaining PCB autoplacer oscillation

**Useful artefacts for next session:**
  - `power_module_v2test.kicad_pcb` — copy of the board used for
    relax tuning.  Independent of the original, safe to mess with.
  - `/tmp/claude-1000/work_kicad/pcb_relax_tune.py` — Jupyter
    tuning script.  Cells: load → open viz → manual step → save.
    Has all the new knobs (`force_step_damping`,
    `normalize_spring_force_by_degree`) exposed.

[unif]: ../../../.claude/projects/-home-vagrant-projects-kicad-agent/memory/project_autoplacer_unification.md

## 2026-05-27 — re-route after U4 move: 0 shorts, 0 clearance

User moved U4 south (from (89, 44) → (65, 70)) onto an extended board,
swapped TH1 to a THT thermistor on B.Cu (body threading into cell gap),
and locked TH1 + BAT1. The board grew from ~95×60 to 95.1×77 mm.

Note: U4 was always LM5176PWPR — earlier task #200's description
mistakenly said "TPS63810". Corrected.

**Workflow:**
1. `delete_trace net="*"` (strip leftover B.Cu fragments from old U4)
2. `relax_placement lockedRefs=["U4","TH1","BAT1","J1","J2","J3","SW1"]`
   → 64 of 71 components moved to follow U4 south. Notable migrations:
   C21 (-25mm), R26 (-25mm), C31 (-25mm), C24 (-23mm), D2 (-21mm).
3. Pre-route 4 BAT1 trunks on B.Cu (same as previous session).
4. `autoroute` (maxPasses=30, timeout=600) — 489 tracks, 35 vias.
5. `refill_zones`, `run_drc`.

**Result (best of the day):**
  - 61 errors, 106 warnings.
  - **0 shorts** ← U4 move resolved the recurring BAT1.2 issue.
  - **0 clearance violations**.
  - 9 track_width (pin-escape stubs — bridge_same_net_pins candidates).
  - 51 unconnected_items.
  - 4 lib_footprint_mismatch (cosmetic, pre-existing).

**Discovered MCP bug: stitch_pour_vias outline check**
  - Ran `stitch_pour_vias net=GND gridPitch=3 apply=true`. Tool added 57
    vias — all of them along x=0 or y=0 (board edge), `skippedOutside=775`.
  - Zone.HitTest is matching only points on the zone outline polygon
    boundary, not points inside it. Needs a point-in-polygon check.
  - Tracked as task #212.

**Second autoroute pass (after deleting the 57 spurious GND vias):**
  - Triggered a fresh routing pass since the GND fragments went too.
  - 714 tracks, 37 vias.
  - 65 errors, 53 unconnects. Slight regression. The fresh autoroute
    didn't materially improve on the first pass.

**Remaining unconnect categories:**
  - ~25 GND inter-pad gaps (need pour vias — blocked by #212).
  - ~5 BAT+ gaps in the U4 cap cluster (same).
  - CELL_TOP B.Cu trunk → F.Cu R2/R3 (cell balance resistors) —
    need a single via to drop from trunk to F.Cu near R2 and R3.
  - BAT- B.Cu trunk → F.Cu BMS area — need a via near (29, 36).
  - U3 charger pin gaps: BQ_LODRV, BQ_HIDRV, BQ_PH, BQ_BTST, BQ_VFB,
    BQ_STAT1. Freerouting partial; another pass might close some.
  - U4 internal: BB_RT, BB_SS, BB_SW2 — same.

**Resumption hooks:**
  - Task #212: fix stitch_pour_vias polygon containment.
  - Task #210: close BAT- east-end (now west-end) gap.
  - Tasks #169-172: still in_progress / pending.

## 2026-05-27 — re-route attempt with fixed tooling

Picked up the re-route plan from yesterday's wrap. Three autoroute
attempts, each providing more diagnostic clarity:

**Setup state at start:**
  - 0 tracks/vias on the board (yesterday's autoroute output had been
    committed but we stripped before this session's run).
  - `verify_netclass_patterns` bootstrapped 8 patterns into
    `mcp_expected_netclass_patterns` (first-call seed; no drift).

**Attempt #1 — DSN plane fix in action:**
  - `autoroute` ran clean. `planeLayersFlippedToPower: [In1.Cu, In2.Cu]`
    confirmed. 448 tracks, 28 vias.
  - DRC: 95 errors. Critically: BAT+ and BAT- traces all on F.Cu
    (not inner planes) — the #203 fix works as designed. ✓
  - BUT: CELL1_TOP, CELL2_TOP had **zero** traces, and BAT+ was
    only 7 short stubs near components, never reaching BAT1's far end.
  - Trade-off discovered: with inner layers locked, freerouting can't
    bridge the 82mm cell-holder span on F.Cu congestion; it just
    gives up rather than dropping to B.Cu.

**Attempt #2 — pre-route the BAT1 trunks on B.Cu:**
  - 4 pre-route traces added on B.Cu, 1.5mm POWER_4A:
      - CELL1_TOP: BAT1.5 (4.85, 12.45) → BAT1.4 (87.15, 30.95)
      - CELL2_TOP: BAT1.3 (4.85, 30.95) → BAT1.2 (87.15, 49.45)
      - BAT+: BAT1.1 (4.85, 49.45) → (27, 49.45)
      - BAT-: BAT1.6 (87.15, 12.45) → (60, 12.45)
  - `autoroute` (maxPasses=30, timeout=600). 442 tracks, 12 vias.
  - **BAT+ now has 28 trace segments**: the 22mm B.Cu trunk + a
    full freerouting-extended F.Cu network through U3 and the
    decoupling caps.
  - DRC: 103 errors. Improvement on unconnects (65 → 61) but
    9 new shorts.

**The recurring BAT1.2 problem:**
  All 9 shorts involve BAT1 pad 2 (CELL2_TOP @ 87.15, 49.45) being
  crossed by U4's B.Cu-side signals. This session it was BB_SW1,
  BB_SW2, BB_PGOOD. Last session (2026-05-26) it was BB_COMPMID,
  BB_SLOPE. The pattern: every autoroute puts U4's local signals
  through BAT1.2 because the pad sits inside U4's footprint
  envelope on B.Cu. Same structural issue, different victim nets.

  Possible permanent fixes (deferred for user review):
   - Same-net B.Cu pour patch around BAT1.2 (and BAT1.4 for
     CELL1_TOP) — effectively a fat pad, forces freerouting away.
     Could be a new MCP tool `pour_around_pad`.
   - Move U4 east/north to clear BAT1's east edge (placement change,
     would invalidate routing).
   - Convert BAT1's east-side pads to F.Cu-only (footprint mod) —
     but the holder is THT.

**Other observations:**
  - 10 `track_width` violations remain — pin-escape stubs
    (0.4–0.9mm) where 1.0mm minimum required. These are
    `bridge_same_net_pins` candidates.
  - BAT- east trunk ends at (60, 12.45) but BMS is at (16, 24);
    freerouting didn't bridge — need a manual route_pad_to_pad or
    longer pre-route trunk.
  - 2 lib_footprint_mismatch warnings (pre-existing).

**Committed state for user review:**
  - `power_module.kicad_pcb` with attempt-#2 routing
  - `power_module.kicad_pro` with bootstrapped
    `mcp_expected_netclass_patterns`
  - Note: this is NOT a clean board. Specifically problematic:
      - 9 B.Cu shorts at BAT1.2 area (delete those traces; don't
        commit them as good)
      - BAT+/BAT- pin-escape stubs at 0.4mm (track_width violations)
      - Several caps in the cap cluster have unconnects between
        them (GND mostly)

**Resumption hooks:**
  - Task #209: Fix BAT1.2 shorts (structural, recurring)
  - Task #210: Close BAT- east → BMS gap
  - Task #169: Route POWER_4A trunk (in_progress, partial)
  - Task #170-172: still pending

## 2026-05-26 — routing-prep tooling complete; ready for re-route

Closes the day's work. After the post-mortem identified 4 root causes
(#1.1 plane-layer DSN bug, #1.2 stripped CELL_TOP patterns, #1.2.1
narrow IC bridges, #1.3 missing paired-via tooling), all four got
shipped as MCP commits on the KiCAD-MCP-Server `develop` branch:

  - `3579223` (#203) — DSN plane-layer type=power fix.
  - `2457804` (power_module main) — CELL_TOP patterns re-added.
  - `0a8e8ab` (#207) — `verify_netclass_patterns` MCP tool + autoroute
    pre-flight check. Stores expected patterns in
    `mcp_expected_netclass_patterns` (KiCAD won't strip it). Drift
    surfaced in `netclassPatternDrift` on autoroute response.
  - `a2674a3` (#206) — `pair_via` MCP tool. Default `netClass=POWER_4A`,
    `offset=1mm`, tries 4 offsets, dedups against existing same-net
    vias. Default preview.
  - `816ef0d` (#205) — `bridge_same_net_pins` MCP tool. Replaces a
    too-narrow IC-bridge trace with a small filled zone (solid
    connection mode by default — current actually flows). Default
    preview.

**State of the board at the wrap:**
  - 50 DRC errors / 121 warnings (almost all silk, pre-existing).
  - 16 unconnected_items still to close.
  - 16 track_width violations (intentional narrow IC connections —
    candidates for `bridge_same_net_pins`).
  - 6 BAT1 stitch vias added (4 west-side BAT1 done; 2 east-side
    rolled back due to conflicts with freerouting traces).
  - User has manually moved many of the BAT1 traces from In1.Cu →
    B.Cu, addressing the symptom of the plane-layer DSN bug.

**Suggested workflow for the next session's re-route:**

  1. `verify_netclass_patterns` — bootstraps expected section (this
     should be the only "bootstrap" call; later calls report drift).
  2. Strip current tracks + vias (`delete_trace net="*"
     includeVias=true`) — clean slate to exercise the fixed
     autoroute.
  3. `autoroute` — should now keep BAT1 nets on B.Cu/F.Cu (not inner
     planes) and route CELL_TOP at 1.5 mm. Confirm via the
     `planeLayersFlippedToPower` and `netclassPatternDrift` fields
     on the response.
  4. `refill_zones` to absorb the spurious clearance errors.
  5. `pair_via netClass=POWER_4A apply=true` to double the
     high-current vias.
  6. For any remaining narrow-IC-bridge `track_width` violations:
     `bridge_same_net_pins` per pair.
  7. Hand-fixups for whatever unconnects remain.
  8. `run_drc` — target 0 errors.

**Outstanding follow-ups:**

  - `#169–172` — actually getting the board fully routed + clean DRC.
  - `#194` — schematic lever-arm torque (autoplacer follow-up,
    deferred since 2026-05-22).
  - The KiCAD-strip-patterns recurrence has only been observed once
    (commit 14a143a, 2026-05-18) over 8 days. `verify_netclass_patterns`
    is the safety net.

## 2026-05-26 — autoroute post-mortem: 4 root causes diagnosed

User pushed back on the autoroute output with specific issues. Each
one traced to a concrete cause:

### 1.1 — All BAT1 nets routed on In1.Cu (GND) instead of B.Cu

**Root cause:** pcbnew's `ExportSpecctraDSN` writes every copper layer
as `(type signal)` in the DSN, even when the layer carries a
continuous `(plane …)` declaration for GND or BAT+. Freerouting then
treats the inner pour layers as routable and prefers them for
long-distance nets (because outer layers are crowded with shorter
connections).

Aggregate evidence: post-autoroute layer breakdown was
`F.Cu 509 / B.Cu 36 / In2.Cu 30 / In1.Cu 18` segments — so the
GND-last layer-order hint *did* bias the bulk routing toward F.Cu,
but long-haul nets like CELL_TOP got pushed to inner layers anyway
because they're "uncluttered."

**Fix shipped:** `KiCAD-MCP-Server` commit `3579223` (#203) adds a
DSN post-process that flips every layer hosting a `(plane …)`
declaration from `(type signal)` to `(type power)`. Freerouting
respects `(type power)` and leaves those layers alone — so the next
autoroute should keep BAT1 nets on B.Cu (or F.Cu via vias).

### 1.2 — BAT1 traces too thin (0.2 mm instead of 1.5 mm POWER_4A)

**Root cause:** `CELL1_TOP` / `CELL2_TOP` netclass patterns were
silently dropped from `power_module.kicad_pro` in commit `14a143a`
("Moved footprints around a little") — KiCAD GUI re-saved the file
and stripped them.  The DSN's `(class POWER_4A …)` block then only
listed `BAT+ BAT- V12_OUT`, so CELL_TOP fell to Default (0.2 mm).
The session-8 addition (#157) genuinely shipped but didn't survive
a later GUI save.

**Fix shipped:** power_module commit `2457804` re-adds both
patterns. The DSN's POWER_4A class will now include CELL_TOP on
the next export.

### 1.2.1 — Track-width DRC violations on short IC bridges

**Root cause:** legitimate physics — a 1.5 mm trace can't fit
between adjacent IC pins at 0.65 mm pitch. The current workflow
is to mark them as DRC exclusions in pcbnew GUI.

**Better idea (user's):** for adjacent same-net IC pins, create
a small filled zone covering both pads instead of a thin track.
The zone bonds the pins, looks like the intentional heat-spread
pour that IC datasheets call for, and satisfies the trunk-width
rule automatically.

**Status:** filed as task #205 (`bridge_same_net_pins` MCP tool).
Not built yet — would need to take a pad-pair, compute a
minimum-bounding-rect with a small margin, and emit a zone on
the appropriate layer with the right net.

### 1.3 — Single vias on high-current nets, no parallel pairs

**Root cause:** no tooling for it.  In past sessions
(`session 7`, 2026-05-15) BAT1 cell-terminal pads got two through-
vias each by hand. The autoroute path never had the option — DSN
class-rule via specifications are single-via only; you can specify
a via size, not "use two of them in parallel." Past automation
notes never carried this forward; it's a real gap, not lost in
compaction.

**Options:**
* Auto-pair via post-autoroute: scan POWER_4A vias, add a second
  via 0.8–1.0 mm offset, same net. Simple and standard.
* Bigger single vias: POWER_4A class already uses 1.0 mm via.
  Larger vias mean larger holes, which take more board area near
  pads. 1.0 mm is roughly the ampacity equivalent of two 0.6 mm
  vias for a 4 A signal, so a single 1.0 mm is OK *electrically*,
  but it's a worse-impedance return path.
* "Via count" netclass attribute: KiCAD doesn't natively support
  this. Would require post-processing.

**Status:** filed as task #206 (`pair_via` MCP tool). Recommend the
post-autoroute auto-pair approach.

### Action items before the next autoroute

  1. ✅ MCP `develop` rebuilt — needs `/mcp` reconnect to load the
     #203 fix.
  2. ✅ `.kicad_pro` re-fixed (CELL_TOP patterns).
  3. Strip the current routing and re-run autoroute. Expect:
     * BAT1 traces stay on B.Cu/F.Cu (not inner planes).
     * CELL_TOP routes at 1.5 mm instead of 0.2 mm.
     * Existing intra-IC pin bridges + west-side BAT1 vias kept
       (or strip-and-redo entirely).
  4. After autoroute: implement #206 `pair_via` to double up the
     high-current vias.
  5. Consider #205 `bridge_same_net_pins` for the remaining narrow
     IC-bridge track_width violations.

## 2026-05-26 — first autoroute pass (handing off mid-routing)

After the routing-side tooling shipped (#176/#177/#178/#181), I
started the routing pass.

Approach evolution: tried hand-routing the BAT+ trunk first (per the
restart plan). Hit immediate pad-clipping issues — trunk widths
(0.8-1.5 mm) can't physically fit between adjacent IC pads at
0.65 mm pitch when the cap-to-IC short-branch path crosses
neighbouring pads. The clearance-aware obstacle check (#177) caught
all these correctly. Hand-debugging each branch would have taken
hours.

Pivoted to the autoroute+manual-fixup pattern that worked in past
sessions. Tagged the clean state as `pre-route-2026-05-26`.

**Routing pass (this session):**

  - 6 intra-IC same-net bridges added with `route_pad_to_pad`
    (0.3-0.5 mm width): U4.2/3 BAT+, U4.12/13 V12_OUT, U1.9/10
    BAT+, Q3.7/8 BAT+, Q2.5/6 BQ_PH, Q2.7/8 USB_VBUS.
  - `autoroute` ran in 149.5 s with the GND-last layer order
    (`[F.Cu, B.Cu, In2.Cu, In1.Cu]`). 593 tracks + 84 vias.
  - `refill_zones` (didn't segfault this time) absorbed the
    spurious clearance + hole_clearance violations that
    freerouting always produces.  DRC: 358 errors → 54 errors.
  - Added 4 stitch vias on the west-side BAT1 cell terminals
    (BAT1.1 BAT+, BAT1.3 CELL2_TOP, BAT1.5 CELL1_TOP, BAT1.6
    BAT-) to bridge the B.Cu cell pads to the In1.Cu tracks
    freerouting left floating. Closed 4 of 10 BAT1 unconnects.
  - East-side BAT1 vias (BAT1.2, BAT1.4) attempted then rolled
    back — the 0.6 mm vias shorted to nearby freerouting traces
    (BAT+ at .4, BB_SLOPE at .2). Hand-fix needed.

**State at end of session (commit ed8c4c5):**

  - 50 errors / 121 warnings (1186 baseline before routing was
    almost all silk noise + courtyard overlaps from placement).
  - **16 unconnected_items** remaining:
    - BAT1.2 CELL2_TOP, BAT1.4 CELL1_TOP — east-side vias rolled
      back (1 each end of those net pairs);
    - 5 BAT+ branches in the U3/U4 area where freerouting bailed
      (C28→U4.3 stub, R4→C9 chain, U3.9→trunk, etc.);
    - 1 V12_OUT (R21→U4.12);
    - 2 BB_VCC (R27 + middle stub);
    - 1 BAT- (BAT1.6 → its In1.Cu track — possibly via clearance);
    - 1 BQ_HIDRV U3.15↔Q2.2 (couldn't route at all);
    - 1 CHG_OUT U3.10→trunk;
    - 1 USB_VBUS U2.8 + 1 USB_VBUS J1.A9 chain;
    - 1 BB_SS C22.1↔U4.8.
  - **16 track_width** violations (intentional narrow IC-pin /
    sense connections — should be marked as DRC exclusions in
    pcbnew GUI).
  - **2 track_dangling** (the two In1.Cu CELL_TOP tracks whose
    BAT1 vias I rolled back — connect when the east-side vias are
    re-added).
  - **4 copper_edge_clearance** (freerouting placed vias too
    close to Edge.Cuts — need manual nudging).
  - **14 courtyards_overlap** (pre-existing placement warnings).
  - **2 lib_footprint_mismatch** (pre-existing).
  - **119 silk warnings** (pre-existing).

**Useful artefacts:**
  - `pcb_initial.png` — clean placement before routing.
  - `pcb_after_autoroute.png` — F.Cu+B.Cu after freerouting.
  - `pcb_final_state.png` — F.Cu+B.Cu+Edge.Cuts+F.SilkS after
    BAT1 vias.  All in `/tmp/claude-1000/`.
  - `pre-route-2026-05-26` git tag — clean state for retrying.

**Next-session top of queue:**

  1. East-side BAT1 vias (#138 redux): re-add BAT1.2 CELL2_TOP +
     BAT1.4 CELL1_TOP. The trick is the 0.6 mm via diameter
     conflicts with adjacent freerouting traces. Options:
     (a) delete the BAT+/BB_SLOPE F.Cu traces that conflict + let
         freerouting redo them with the via present;
     (b) use 0.4 mm via diameter;
     (c) offset the via 1 mm from pad center + connect with a
         short B.Cu stub trace.
  2. Hand-fix the 11 remaining IC-area unconnects with
     `route_pad_to_pad` + `find_via_lane`. The clearance-aware
     check (#177) and pin-escape (#178) should help — many of
     these are short branches that need pin escape from U3/U4.
  3. Resolve 4 copper_edge_clearance violations (delete those
     vias + reroute, or move vias inward).
  4. Mark 16 track_width violations as exclusions in pcbnew GUI.
  5. Re-run DRC, target 0 errors.

## 2026-05-26 — width-aware obstacle detection (#177)

Resumed after a few days; user locked U4 in pcbnew (`(locked yes)` on
the HTSSOP-28-1EP footprint, position 88.378/43.812 mm @ 90°) and the
placer now respects it via #199.  Closed #200.

Then shipped #177 on KiCAD-MCP-Server `develop`:

  - `_iter_route_obstacles` / `_find_route_obstacles` accept
    `trace_width_iu` and `min_clearance_iu` (default 0 = legacy
    centerline behaviour).  Vias get an inflated radius check, tracks
    use a 4-corner seg-seg min-distance, pads use the existing
    `pad.HitTest(point, accuracy=...)` SWIG overload with the inflation
    baked into the accuracy parameter.
  - New `_resolve_route_clearance(width, clearance, net)` helper:
    looks up the trace width (param → board default) and clearance
    (param → net's netclass → board default).
  - `route_trace`, `route_pad_to_pad`, `check_route_segment` accept a
    new optional `clearance` (mm) parameter.  When omitted, the
    netclass clearance is used automatically.
  - MCP descriptions + zod/JSON schemas updated so the LLM can
    discover and use the new param.
  - Tests: 4 unit (resolver) + 4 real-pcbnew integration
    (edge-clipping pad detected, legacy passes, parallel near-miss
    track detected, clearance inflates detection zone).  All 1173
    existing tests still pass.

Pre-existing test cleanup while in the area:
  - `test_placement_constraints` and
    `test_placement_constraint_propagation` referenced the literal `1`
    for `mcp_constraint_version`; bumped them to use the module
    constant so future version bumps don't need test edits.

**Routing-side tooling that's still pending before the actual routing
pass can be safely tackled by the LLM:**
  - ~~`#178` route_pad_to_pad pin-escape~~ ✓ shipped.
  - ~~`#176` stitch_pour_vias MCP tool~~ ✓ shipped.
  - ~~`#181` analyze_congestion layer-aware pad density~~ ✓ shipped.

After #178, the routing tasks #169–172 should be unblocked.

### 2026-05-26 follow-up — pin-escape (#178)

Same session as #177. `route_pad_to_pad` gained optional
`escapeFromWidth`/`escapeFromLength` (and the symmetric `escapeTo*`)
parameters so a fat trunk trace can exit a tight IC pad as a narrow
stub before widening. Direction is perpendicular to the pin row
(footprint center → pad center). Cross-layer escape deferred to a
follow-up; for now `route_pad_to_pad` rejects escape on cross-layer
routes cleanly. Tests: 8 (4 unit + 4 real-pcbnew integration).
Commits on KiCAD-MCP-Server `develop`:
  - `feat(#178): pin-escape stub support on route_pad_to_pad`

### 2026-05-26 follow-up — stitch_pour_vias (#176)

New MCP tool: `stitch_pour_vias(net, gridPitch, ...)`. Walks a grid
over the union bbox of all zones on the net; each candidate must be
inside a zone outline, clear `minClearance` from any foreign-net
copper (uses the same helper as find_via_lane's via-clearance check),
and not duplicate an existing same-net via. Default preview; pass
apply=true to commit. Verified end-to-end on a synthetic real-pcbnew
40×30 mm board with a single GND zone — 28 vias proposed at 5 mm
grid pitch. Tests: 9 (5 unit + 4 real-pcbnew integration).
Commits on KiCAD-MCP-Server `develop`:
  - `feat(#176): stitch_pour_vias MCP tool`

### 2026-05-26 follow-up — analyze_congestion layer filter (#181)

`analyze_congestion` accepts an optional `layer` parameter; when set,
the pad-density score is filtered to pads on that copper layer (PTH
pads count on every layer). Each hotspot also now carries
`pad_count_by_layer` so the F.Cu vs B.Cu breakdown is visible in one
call. Disambiguates "12 pads here" hotspots that used to lump both
sides together.

Docs swept too: `ROUTING_TOOLS_REFERENCE.md` updated for the new
`clearance`/escape params on route_trace + route_pad_to_pad and a
new `stitch_pour_vias` section. `PCB_DESIGN_WORKFLOW.md` and
`TOOL_INVENTORY.md` got the same treatment.

Tests: 5 (3 unit + 2 real-pcbnew integration).
Commits on KiCAD-MCP-Server `develop`:
  - `feat(#181): analyze_congestion layer filter + docs sweep`

## 2026-05-22 — placement converged; storage IO + schedule defaults

User tuned the autoplacer to an acceptable layout and asked to fold
the tuning back into the production defaults, plus implement the
spring-class storage that had been deferred.  Seven commits on
KiCAD-MCP-Server `develop`:

**Bug fixes that unblocked tuning (earlier in the session):**

  - `d05e707` — **OBB rotation convention bug.**  `_obb_corners` /
    `_obb_axes` used raw math-Y-up CCW rotation; every other place
    in the engine (world_pin_xy, the viz's matplotlib angle) used
    screen-Y-down CCW.  For asymmetric bboxes at non-multiple-of-
    90° rotations, the OBB was MIRRORED relative to the rendered
    rectangle — repulsion pushed against ghost bodies.  User
    caught it via R10 visibly inside L1's drawn rectangle while
    `gaps()` reported +1.61 mm of separation.
  - `f6eaf2d` — sequential (Gauss-Seidel) apply mode behind
    `Params.sequential_apply`.  Default off; debugging tool.
  - `7392132` — bbox uses courtyard / fab + offset center.  Pad-only
    bbox missed body extent of inductors / pin headers anchored at
    pin 1.  `Component` now carries `bbox_cx/bbox_cy`; every OBB
    call site uses `obb_center_world()` instead of `(c.x, c.y)`.

**Then the tuning-defaults pass (today's session proper):**

  - `baf16f9` — clean up the 1/r³ repulsion formula (`F = k /
    max(gap - margin, 0.01)³`).  Replaces the cubic-ramp cutoff,
    which produced chaotic rebound in dense clusters.  Tests
    rewritten for the new physics (saturation regime, inverse-cube
    falloff).
  - `85879ea` — fold tuned values into `PCBSchedule` defaults:
    spring_k=1.0, repulsion_k_peak=0.1, rotation_snap_peak=30,
    pinwise_torque_k=1.0, force_step_damping=0.3, spread_iters=200,
    snap_iters=100, cluster_iters=0, relax_iters=0, step_spread=0.2,
    step_snap=0.05.  New `enforce_rotation_snap` flag (default True)
    runs `snap_rotations()` at end for clean alignment.  New
    `boundary_k` field plumbed through with sheet bounds — a soft
    restoring force keeps components on-board during iteration
    (was a post-clamp only).
  - `18fc67e` — `load_pcb_session` honors `fp.IsLocked()` when no
    explicit lockedRefs is supplied.  Right-click → Lock in KiCad
    now anchors the footprint.  Use this for U4 (thermal vias).
  - `e16e2c4` — `Pin_Spring_Class:N` + `Spring_Class` + `Body_Margin`
    footprint properties read at load.  Bare-string or JSON-dict
    format per the storage design.  Resolves the "decoupling caps
    should have decoupling strength" thread via explicit annotation
    rather than heuristic auto-detection.
  - `25715d2` — `.kicad_pro` spring class IO.  `mcp_spring_classes`
    section read on load, bootstrap defaults if absent.  No more
    redoing `sess.nets['USB_VBUS'].spring_class = 'PLANE'` in
    Jupyter each session.  `mcp_constraint_version` bumped 1 → 2.

User left U4-anchor TODO for tomorrow (#200) — right-click Lock in
KiCad, save the board.  The placer will now respect it.

**Open follow-ups carried forward:**
  - `#194` Unify torque mechanism (lever-arm for schematic too) —
    held until PCB lever-arm fully proven; do as a separate
    focused commit.
  - `#176` `stitch_pour_vias` MCP tool.
  - `#177` `route_trace` trace-vs-pad clearance check.
  - `#178` `route_pad_to_pad` pin-escape (narrow at IC, widen to
    trunk) — needed for the actual routing pass.
  - `#181` `analyze_congestion` layer-aware pad density.
  - `#200` Anchor U4 in KiCad UI (small action; unblocked).
  - `#169–172` Route the board (4A trunk → 2A medium → signals →
    final validation).  Unblocked now that placement is stable.

**Useful artefacts for next session:**
  - `power_module_v2test.kicad_pcb` — copy used for relax tuning.
    Independent of the original, safe to mess with.
  - `/tmp/claude-1000/work_kicad/pcb_relax_tune.py` — local Jupyter
    tuning script (the user's working copy).  Cells: load → viz
    → step → save.
  - `KiCAD-MCP-Server/pcb_relax_tune.py` — checked-in copy of the
    same script (with the user's hardcoded paths — adjust before
    running on this machine).

## State at end of 2026-05-16 session 8 (netclass cleanup + DRC width rule)

**Trace-width audit triggered by user observation that battery
traces looked oversized in some places and under-sized in others.**

Findings:

  - Project ALREADY had POWER_4A (1.5mm) and POWER_2A (0.8mm)
    netclasses correctly defined. Assignments existed for BAT+,
    BAT-, V12_OUT, USB_VBUS, CHG_OUT, BQ_PH.
  - **CELL1_TOP and CELL2_TOP were NOT in any netclass** → fell
    to Default (0.2mm). They carry the same 4A as BAT+/BAT-
    through the 3-cell series stack. 0.2mm at 4A external ≈
    80°C+ temperature rise — well past safe.
  - 8 long B.Cu power-carrying traces affected (35.87mm, 29.59mm,
    24.88mm, 24.63mm, etc.).

**Shipped** (power_module main commit `1ada0ab`):

  - Added `CELL1_TOP` and `CELL2_TOP` to POWER_4A netclass_patterns
    in `.kicad_pro`. Future routes get 1.5mm by default.
  - Created `power_module.kicad_dru` with custom rules:
    - `POWER_4A min track width` ≥ 1.0mm
    - `POWER_2A min track width` ≥ 0.5mm
    DRC now fires 28 `track_width` violations — the top 8 by length
    are the real problem (long B.Cu power traces); the rest are
    short F.Cu IC-pin/sense connections (BMS cell-voltage taps)
    that are intentionally narrow and can be marked as DRC
    exclusions individually in pcbnew if desired.

**Deferred** — in-place widening of the existing 8 power traces
failed: 1.5mm width caused 7 short/clearance violations (GND
stitching vias and parallel BAT+/ALERT traces sit in the path).
Requires re-routing the CELL_TOP B.Cu chain with re-positioned
stitching vias and possibly relocating ALERT signal routing — a
layout-level re-work. The DRC rule keeps the issue visible until
this happens.

**MCP fix shipped** (develop commit `51604f5`): `modify_trace`
now accepts both `traceUuid` (TS schema name, matching
delete_trace) and `uuid` (legacy). Surfaced when trying to widen
via MCP; same B2-style mismatch as the get_pad_position fix
earlier today.

**PCB DRC state after this session**:
  - 5 unconnected (baseline, unchanged)
  - 0 shorts, 0 clearance
  - 28 NEW track_width violations (real diagnostic — pre-existing
    issue, now visible)
  - 99 silk + 2 lib_footprint_mismatch (baseline)

**Tasks closed this session**: #157 (netclass), #158 (widen,
deferred-with-rationale), #159 (DRC rule).

**Next-session top of queue**:

  1. **CELL_TOP B.Cu re-route at 1.5mm** — needs layout-level
     re-work (move GND stitching vias, reroute ALERT). Bigger
     project; could be ~1-2 hour focused session.
  2. **CHG_OUT, BQ_PH** — GUI hand-routing on tight QFN area.
  3. **C26** — layout decision (move C26 or hand-route F.Cu detour).
  4. **USB_VBUS C17** — easy fix found earlier this session
     (2-segment around C17.2 GND pad); not yet applied.

## State at end of 2026-05-16 session 7 (Strategy H + C26 structural verdict)

**MCP tooling shipped** (KiCAD-MCP-Server `develop`):

  - **Strategy H — clearance-aware via walk** (task #156, commit
    `d5f26ac`). `_find_safe_via_point` now requires both segment-
    clear AND via-clearance-clear at each walk sample, so via1/
    via2 land at the furthest position safe for both checks.
    Failure diagnostic adds `viaClearanceAtEndpoint` listing
    foreign-layer copper that's in the way.

**C26 BB_VCC — verdict: structurally unroutable via through-via
jumper at default parameters.** With Strategy H applied:

  - With real C26.1 pad as source + minClearance=0.15 mm:
    `no_safe_via_zone` — diagnostic shows BB_SW1 (In1.Cu) and
    BB_COMP (In2.Cu) tracks **overlap** the C26.1 pad region
    (gaps -0.099 mm and -0.275 mm). Any 0.6 mm through via at
    or near C26.1 will short to these inner-layer traces.
  - With minClearance=0 (allow zero gap, just refuse overlap):
    via1 still overlaps BB_BOOT2 by 0.27 mm — via clearance
    refuses.
  - With microvia (0.3 mm): same overlaps because the inner-layer
    tracks pass directly under/over C26.1.

  **The structural issue**: the layout puts BB_SW1, BB_COMP, and
  BB_BOOT2 routing right through where C26's via has to go. No
  via tool can fix this — either:
    (a) move C26 to a less-crowded location (schematic change +
        re-place), or
    (b) hand-route BB_VCC as an F.Cu detour around the whole
        area (no via), or
    (c) move the inner-layer tracks (re-autoroute).

  None of these are tool-driven fixes. C26 is now formally
  closed in NOTES as "out of scope for find_via_lane; needs
  layout-level change".

**Tasks closed this session**: #156 (Strategy H).

**No new tasks queued** — the find_via_lane suite (Strategies A
through H + via clearance) is now feature-complete for the via-
jumper use case. Remaining via-jumper failures (like C26) are
structural and need design changes.

**PCB unchanged this session** (pure tooling work).

**Next-session top of queue**:

  1. **CHG_OUT, BQ_PH** — GUI hand-routing on the 0.5 mm-pitch
     QFN area (find_via_lane confirmed unsuitable for these).
  2. **C26** — layout-level decision: move C26, or accept the
     pre-existing BB_VCC routing topology, or hand-route F.Cu
     detour.
  3. **USB_VBUS C17/J1** — design-intent check (look at schematic
     to understand intended topology before completing).

## State at end of 2026-05-16 session 6 (find_via_lane v4 + via clearance)

**MCP tooling shipped** (KiCAD-MCP-Server `develop`):

  - **`find_via_lane` via-clearance check (task #155, commit
    `a2526ea`).** New `_via_clearance_violations` helper + new
    `minClearance` param (default 0.15 mm). After via1/via2 are
    chosen, both are validated against all foreign-net copper on
    every copper layer the through via touches. Refuses with
    `via_clearance_violation` strategy + per-via violation list
    (with per-element gap in mm). Verified on the CHG_OUT U3.10
    case from session 5: now catches the 0.046 mm gap to pad
    U3-11 that would have shorted.
  - **`find_via_lane` v4 Strategy G — 4-corner Z-shape (task
    #153, commit `26e9c64`).** When via1/via2 straddle a blocker
    and Strategy F's L-shape east/west legs hit secondary
    obstacles, Strategy G tries 4 bbox corners × 2 patterns
    (HVHV + VHVH) = 8 candidate 4-segment Z-shapes. Verified on
    C26 BB_VCC: Strategy G finds the NE-corner HVHV Z (north of
    BB_BOOT2 → east → south → west to via2) — same shape NOTES
    had documented as the workable hand-route.

**C26 status update**: Strategy G finds the right SHAPE for C26
but #155's via-clearance check (correctly) catches that via1 is
0.13 mm from BB_BOOT2 — too close even before the Z-shape
detour begins. Resolving this needs **Strategy H "via re-walk"**
(filed as task #156): when clearance fails, walk via1/via2
further from source/target until clearance passes. Until #156,
C26 still needs GUI hand-routing with a deliberately longer
F.Cu stub from C26.1 going further south past BB_HDRV1.

**PCB unchanged this session** (pure tooling work). DRC still at
baseline: 5 unconnected_items, 0 shorts, 0 dangling.

**Tasks closed this session**: #153 (Strategy G), #155 (via
clearance), #154 already closed earlier in the day.

**Tasks queued**: #156 (Strategy H — via re-walk on clearance
failure), #136 (apply_positions safe wrapper, low priority).

**Next-session top of queue**:

  1. **Strategy H** (task #156) — ~30 min. Would close C26
     automatically end-to-end through find_via_lane.
  2. **C26 hand-route in GUI** if Strategy H isn't desired —
     ~5 min, deterministic.
  3. **CHG_OUT, BQ_PH** — still need GUI hand-routing for the
     0.5 mm-pitch QFN area; tooling won't help here without a
     much bigger pin-pitch-aware router.

## State at end of 2026-05-16 session 5 (get_component_pads layers + CHG_OUT scout)

**MCP tooling shipped** (KiCAD-MCP-Server `develop`):

  - **`get_component_pads` returns `layers` per pad** (commit `97bb047`).
    SMD pads get one entry (e.g. `["B.Cu"]`); through-hole/NPTH
    get the full board Cu stack. Directly motivated by the BAT1
    misroute (assumed F.Cu, pads were B.Cu). Task #154 closed.
    Memory updated: [[feedback-check-pad-layer]].

**CHG_OUT (U3.10↔L1.2) investigated — DEFERRED to GUI hand-route.**

  - L1.2 (F.Cu, big inductor pad) at (41, 70) → U3.10 (F.Cu, tiny
    QFN pin) at (48.4625, 70.25). Existing 2 F.Cu segments from
    L1.2 went SE to (43, 76.46), abandoned (didn't reach U3).
  - South route from (43, 76.46) east: blocked by USB_VBUS
    network + C11.1 pad at (48.28, 76.47).
  - North route from L1.2 (41, 70) going up: blocked by USB_VBUS
    track at (39.6, 67.85).
  - Direct B.Cu route (41,70)→(48.4625, 70.25) clears — but both
    endpoint pads are F.Cu, so need a via-jumper.
  - `find_via_lane` proposed `via_jumper` with via2 at (48.514,
    70.221) — INSIDE U3.10 pad bbox, same-net via-in-pad. **But**
    via diameter 0.6 mm > pad 10 height 0.25 mm, so via copper
    extends 0.175 mm beyond pad 10 → 0.046 mm gap to pad 11
    (GND) → clearance violation. **Bug**: `find_via_lane` doesn't
    check via-vs-nearby-copper clearance (filed as task #155).
  - Attempting to extend stub east hits BQ_REGN via at (49.94,
    70.18); diagonal NE/SE crosses pad 11 (GND) or pad 9 (BAT+);
    even a microvia on U3.10 itself would still short to pad 11.
  - **Verdict**: this is a 0.5 mm-pitch QFN with no breakout
    room. Needs hand-routing in pcbnew GUI — either a microvia
    on U3.10 with explicit clearance tuning, or moving L1
    closer/repositioning so the direct route is shorter and
    fits in the available F.Cu corridor.

**Final DRC state** (back at baseline after restoring abandoned
L1.2 segments — UUID-only churn discarded):
  - 5 unconnected_items, 0 shorts, 0 clearance, 0 dangling.
  - Same 5 baseline cases: BB_VCC C26, BQ_PH, CHG_OUT, USB_VBUS
    C17, USB_VBUS J1.

**Next-session top of queue**:

  1. **CHG_OUT + BQ_PH**: hand-route in pcbnew GUI (or move U3
    /L1/C17 to give breakout room). Both are tight QFN routing.
  2. **C26 BB_VCC** (still deferred): hand-route OR build
     find_via_lane v4 Strategy G — Z-shape (task #153).
  3. **Task #155**: find_via_lane via-vs-copper clearance check.
     Would have caught the CHG_OUT bad proposal in this session.
  4. **USB_VBUS C17/J1**: design-intent check — may need topology
     redesign rather than completing a missing trace.

## State at end of 2026-05-16 session 4 (BAT1 fork-via cleanup)

**Routed today** — BAT1 cell-pad fork-via cleanup + reroute.

Each of the 4 inner BAT1 cell pads (CELL2_TOP pads 2,3 and
CELL1_TOP pads 4,5) had **three** vias: a pad-center via, a
south-offset in-pad via, and a 3 mm displaced via — wired
together by an In1.Cu wide stub + multi-segment narrow jog,
plus the B.Cu long route. Pure waste: the cell pads sit on B.Cu
(cell holder is bottom-mount), the long routing chain is on B.Cu,
no F.Cu transition was ever needed.

**Cleanup**:
  - Deleted 14 In1.Cu traces (4 wide 1.5mm stubs + 10 narrow jog
    segments) and **12 vias** (4 pad-center + 4 south-offset +
    4 displaced).
  - Added 4 direct B.Cu tracks, 1.5 mm wide, from each cell pad
    center to the appropriate chain anchor point.
  - File shrunk -176 lines (224 → 24). 0 new DRC errors.
  - Commit `309905d` on power_module main.

**Gotcha caught**: BAT1 SMD pads are on **B.Cu**, not F.Cu.
First-pass cleanup added the new tracks on F.Cu (assuming top);
DRC immediately flagged them as `track_dangling` with
`Pad N [CELL*_TOP] of BAT1 on B.Cu` — gave it away. Reverted and
re-routed on B.Cu. Saved as [[feedback_check_pad_layer]] memory:
get_component_pads doesn't return layer, so grep the .kicad_pcb
or test-route + check DRC. Also queued task #154 (MCP improvement
to add a `layers` field to get_component_pads).

**Final DRC state** (unchanged from baseline):
  - 5 unconnected_items: BB_VCC C26, BQ_PH, CHG_OUT U3.10↔L1.2,
    USB_VBUS C17.1, USB_VBUS J1.A9 (same pre-existing list).
  - 0 shorts, 0 clearance, 0 dangling vias, 0 dangling tracks.
  - 99 silk warnings + 2 lib_footprint_mismatch (both pre-existing).

**Next-session top of queue**:

  1. **C26 BB_VCC**: hand-route in pcbnew GUI (~5 min) OR build
     find_via_lane v4 Strategy G — Z-shape with back-leg X sweep
     (~30 min, task #153).
  2. **Baseline unconnects** (BQ_PH, CHG_OUT, USB_VBUS C17/J1) —
     these are design-intent calls; should look at intended
     topology before adding traces.
  3. **MCP polish**: task #154 (pad layer in get_component_pads),
     #136 (apply_positions safe wrapper — placement-only, low
     priority since route_trace checkObstacles covers routing).

## State at end of 2026-05-16 session 3 (find_via_lane v3)

**MCP tooling shipped today** (KiCAD-MCP-Server `develop`):

  - **find_via_lane v3 — Strategy F: obstacle-bbox-aware L-shape.**
    Replaces v2's blind ±waypoint_max sweep for the L-shape case
    with a sized-to-the-blocker approach: compute the union bbox of
    via-layer obstacles, propose 4 L-shapes (one past each bbox
    edge + clearance margin). Refactored `_find_route_obstacles`
    into a shared `_iter_route_obstacles` generator so the string
    and object output share one detection core (byte-identical
    strings preserved).

**Verified on C26 BB_VCC** (canonical pathological case):

  - v3 Strategy F runs all 4 candidate edges and now returns:
    - `obstacleBbox` = union extent of via-layer blockers (mm)
    - `bboxLshapesTried` = per-edge, per-leg blocker list
  - All 4 still fail. **Root cause** (newly visible in diagnostic):
    via1 (Y=75.595, north of BB_BOOT2) and via2 (Y=76.669, south
    of it) straddle the bbox. VHV detours can't help geometrically;
    east/west HVH hit secondary obstacles (BB_FB diagonal east,
    BB_SW1/BB_BOOT1 vias west).
  - C26 truly needs a 3-bend Z-shape (Strategy G — task #153) OR
    a hand-route in pcbnew.
  - waypointSearchMax=20 gave the same result as =10 — confirms F
    sizes detours from bbox + clearance, not from search radius.

**Power_module PCB unchanged this session** — pure tooling work.
DRC state still 9 unconnected_items (last session: 5 closed of the
4 cap + 1 trunk batch; rebaseline pending C26 + 4 baseline cases).

**Next-session top of queue**:

  1. **Pick one of**: (a) C26 hand-route in pcbnew GUI (~5 min),
     or (b) build find_via_lane v4 Strategy G — Z-shape with back-
     leg X sweep (~30 min, unlocks similar straddling cases).
  2. **BAT1 reroute** (deferred 4 sessions running, task #138).
  3. **apply_positions safe wrapper** (task #136).

## State at end of 2026-05-18 session (close 3 of 4 cap unconnects)

**Routed today** (commits TBD on power_module main):

  - **C28.1 BAT+** — route_pad_to_pad C28→C27, 0.4 mm F.Cu, 2.29 mm.
    Direct diagonal route at 1.5 mm width shorted to C15.2 GND (1.43 mm
    perpendicular distance). Dropping width to 0.4 mm cleared the
    POWER_2A clearance. `route_pad_to_pad checkObstacles=true` approved.
  - **C7.1 REGOUT** — 3-segment waypoint around U1's east side:
    (14.138, 63.625) east to (16.85, 63.625), south to (16.85, 68.204),
    west to C7.1. First try at X=16.3 shorted to a GND via at
    (16.290, 66.913) — 0.16 mm via clearance forced the bump to 16.85.
  - **C11.1 USB_VBUS** — 3-segment route around south of C11.2 GND pad:
    (49.952, 74.456) south to Y=77.5, west, north into C11.1. Direct
    diagonal hit 0.031 mm clearance to C11.2.

**Deferred — C26.1 BB_VCC** (needs new tooling or GUI):
  - U4.24 BB_VCC pad row at Y=77.138 is fenced by BB_HDRV1 and BB_LDRV1
    driver stubs (X=74.425 and 75.725) on F.Cu — no room for a horizontal
    BB_VCC trace at that Y.
  - B.Cu blocked by BB_BOOT2 long trace at Y=75.855 spanning X=57.9 to
    78.975 — direct vertical B.Cu route at any X in [57.9, 78.975]
    crosses it.
  - Workable path: F.Cu south to Y=74.2 (clear of BB_HDRV1), via to
    B.Cu, east to X=79.5 (past BB_BOOT2 east end), south to Y=78.1, west
    back to (76.005, 78.123) joining the existing BB_VCC F.Cu chain, via
    back to F.Cu. **2 vias + 4 segments** for one decoupling cap.
  - Recommend: hand-route in pcbnew GUI (faster) OR build `find_via_lane`
    MCP tool (see `/tmp/claude-1000/mcp_tooling_notes_2026-05-18.md`).

**Final DRC state:**
  - 5 unconnected_items (was 6 mid-session, closed U4.2/U4.3 BAT+ trunk
    after the route_trace checkObstacles MCP fix shipped): C26.1 BB_VCC
    cap (deferred), BQ_PH stub, CHG_OUT U3.10↔L1.2 (needs route around
    U3 QFN body, ~7.5 mm), USB_VBUS C17.1 (10.87 mm gap, may need
    different topology), USB_VBUS J1.A9 (probable routing-through-U3
    power-path mgmt, not direct to U4).
  - 0 shorts, 0 clearance, 0 tracks_crossing, 0 solder_mask_bridge,
    0 hole_clearance, 0 annular_width — i.e. zero new electrical errors.
  - 99 silk warnings (pre-existing) + 2 lib_footprint_mismatch
    (pre-existing).

**Verified new MCP tool live**: `route_trace checkObstacles` (default
true, shipped as `c4fe565` on develop) caught the C28.2 GND collision
on the U4.3→C28.1 attempt immediately, and accepted the X=75.075
waypointed detour on first try. Compare to earlier session where the
same surgery cost a full delete/restore round-trip.

**Six more MCP commits this session** (all on `develop`):
  - `c4fe565` — `route_trace checkObstacles` (default-on obstacle
    refusal, mirroring `route_pad_to_pad`).
  - `87db988` — `dedupe_traces` + `check_route_segment` +
    `get_pad_position` param fix bundle.
  - `dcc9195` — `find_via_lane` v1 (direct + via-jumper + single-
    waypoint perpendicular-offset search).
  - `f467da5` — `find_via_lane` v2 (minimumStubLength +
    2D grid search + axis-aligned 2-waypoint L-shape).
  - (Earlier today still on the list: place_near tweaks shipped
    yesterday were `e9fcbd2` + `f4c5d03`.)

**Plus `6f3b690` on power_module main** — used the new
`dedupe_traces` tool, removed 332 duplicate tracks/vias left by
prior autoroute SES re-imports across BB_VCC, BB_HDRV1/2, BB_LDRV1/2,
REGOUT and others. DRC unchanged before/after (electrical no-op),
file size dropped by 2704 lines.

**find_via_lane v2 — live test summary**:
  - J1.A9 USB_VBUS with `minimumStubLength=1`: correctly refused
    (`stub_too_short_source: 0.006 mm < 1.0 mm`). The via-on-pad
    case is now caught.
  - C26.1 BB_VCC with `minimumStubLength=0.5`: same refusal at
    0.289 mm. Means C26 can't be via-jumpered without first
    hand-routing a stub OUT of C26's pad column. Cleaner
    diagnostic than v1's silent "via on pad" success.
  - Strategy D (2D grid) and E (L-shape): wired and didn't crash,
    but didn't find a clear solution on power_module's pathological
    cases (C26 needs board-level re-route; J1.A9 needs hand stub).
    Will exercise on simpler future cases.

**MCP tooling gaps captured** (not yet implemented; see
`/tmp/claude-1000/mcp_tooling_notes_2026-05-18.md`):
  - **B1**: `route_trace` needs `checkObstacles` param (same pattern as
    `route_pad_to_pad`). Direct cause of 4 bad routes today that I had
    to revert. **Promoting to MCP commit this session** if time allows.
  - **B2**: `get_pad_position` schema/impl mismatch (`pad` vs
    `padName`/`padNumber`).
  - **B3**: 30+ duplicate traces left over from autoroute SES imports;
    `dedupe_traces` tool would clean them up.
  - **N1**: `close_unconnect(net, padRef, padNumber)` — high-level
    "complete this ratsnest line" with waypointing + via insertion.
  - **N2**: `check_route_segment` — standalone obstacle check (cheap
    pre-flight without committing the route).
  - **N3**: `find_via_lane` — propose via-jumper through B.Cu/inner when
    F.Cu is blocked. Would have solved C26.

### Next-session candidates (in rough priority order)

1. **C26.1 BB_VCC via-jumper** in pcbnew GUI (~5 min) OR build
   `find_via_lane` MCP tool (~1 hr).
2. **U4.2/U4.3 BAT+ trunk connection** (pre-existing baseline). Closest
   trunk point is now my new C28→C27 trace at (75.925, 86.236). ~4 mm
   F.Cu route, must clear BB_SS/BB_RT stubs on U4's south pad row.
3. **BAT1 routing fix** (deferred three sessions running). Strip useless
   fork-vias in cell pads + reroute.
4. **MCP polish**: B1/N2 (route_trace obstacle check + check_route_segment),
   self.board mtime auto-reload, parallel-write thread safety audit.

### Workflow lessons from this session

  - **`route_trace` is fire-and-forget** — no obstacle check; commits the
    segment even if it crosses foreign-net copper. Always pair with
    `run_drc` after a batch and revert on regression. (Or pre-empt with
    `route_pad_to_pad checkObstacles` when applicable.) See B1 above for
    the tool fix.
  - **"Orphan" stubs are not always orphan** — I deleted the 0.65 mm
    BAT+ stub `25a80d39` thinking it was leftover, but it was the
    bridge between U4.2 and U4.3 BAT+ pads. Same with C26's east-going
    fanout — those segments connected C26.1 to C25.1. Always trace where
    BOTH endpoints of a stub go before deleting. Restore was easy (just
    `route_trace` with original coords/width), but cost 4 round-trips.
  - **Pad-row "fence"** — TSSOP/QFP ICs have vertical signal stubs at
    every pad position. Any horizontal route at Y = pad-row-Y shorts to
    multiple pads. Always approach the pad from a direction perpendicular
    to the pad row (above or below), not parallel.
  - **In1.Cu and In2.Cu are routing layers, not single-net planes** on
    this board — BAT+ and USB_VBUS appear as discrete traces on inner
    copper. Don't assume a via to inner copper connects to a continuous
    rail pour; check first.

## State at end of 2026-05-17 session (decoupling-cap placement pass)

**MCP tooling shipped on `develop` today** (motivated by bugs surfaced
during the placement pass):

  - **decoupling_audit 44× faster** (`40aeaa1`): `discover_decoupling_pairs`
    used to call `get_connections_for_net` per-net, re-loading each
    sheet's sexp + adjacency + symbol instances every time. On
    power_module (4 sheets × 55 nets) that was ~57 s — past the MCP
    request timeout. Added `get_all_net_connections` bulk helper in
    `wire_connectivity.py`; one-pass per sheet. 57 s → 1.3 s.
  - **place_near foreign-track collision + run_drc auto-save** (`e9fcbd2`):
    place_near's bbox-only check missed C6's GND pad landing on a
    REGOUT trace (created 2 shorting_items + 2 solder_mask_bridge).
    Added per-pad track-collision check vs every track on the pad's
    layer (skips same-net). Separately, `run_drc` invoked kicad-cli
    against the on-disk file without first persisting `self.board`,
    so the first post-placement DRC silently returned the baseline;
    added auto-save before the cli call.
  - **place_near clearance margin** (`f4c5d03`): the strict bbox
    overlap still missed sub-DRC near-touches. C10's USB_VBUS pad
    ended 0.009 mm from a BQ_PH trace (under POWER_2A 0.13 mm).
    Added `clearanceMargin` parameter (default 0.15 mm) that
    inflates the pad bbox before the foreign-track test.

**Applied to power_module (this session):**

  - **Decoupling placement pass** (commit `22e01fd`): moved 12 of 13
    too_far primary caps. C6 (5.155 mm) skipped as already close.
    Audit went from 13 too_far → 5 too_far. Biggest wins:
    - C9  18.5 → 3.2 mm
    - C15 19.5 → 5.1 mm
    - C28 12.7 → 2.4 mm
    - C26 14.0 → 3.2 mm
    - C25 16.5 → 4.1 mm
    - C17 12.9 → 2.6 mm
    Remaining 5 "too_far" all within 1.5 mm of acceptable (limited
    by physical congestion near U3.1 USB_VBUS and U4.2 BAT+).
    Resolved one prior courtyard warning (L2/C25 — cleared by C25
    move).
  - **Rip dangling + autoroute** (commit `4b13380`): iteratively
    ripped 21 dangling tracks + orphan vias until stable, then
    autorouted. Autoroute introduced 24 zone clearance/hole errors
    (vias placed without anti-pads on inner planes — `refill_zones`
    fixed them) and 3 annular_width errors on BAT+/BAT- vias near
    the battery cells (freerouting used 0.5 mm drill on 0.6 mm pad;
    reset to project default 0.3 mm).

**Final DRC state:**
  - 9 unconnected_items (5 pre-existing baseline + 4 from the cap
    moves that freerouting could not complete: C28.1 BAT+,
    C26.1 BB_VCC, C7.1 REGOUT, one USB_VBUS pair).
  - 0 shorting_items, 0 clearance, 0 hole_clearance, 0 annular_width,
    0 solder_mask_bridge — i.e. zero new electrical errors.
  - 99 warnings (silk overlap / silk over copper, all pre-existing).
  - check_pcb_integrity: 2 courtyard_overlap warnings (R10/L1 and
    R25/J1; L2/C25 cleared by the placement pass).

### Next-session candidates (in rough priority order)

1. **Close the 4 remaining cap unconnects.** Run a second
   freerouting pass (might pick them up with different seed), or
   hand-route the 4 short connections in pcbnew. Likely 30-min job.
2. **BAT1 routing fix** (deferred two sessions running now). The
   2 vias inside each BAT1 cell-terminal pad + In1.Cu bridge are
   useless — the trunk continues on B.Cu. Three options unchanged:
   strip BAT1 nets and hand-route, copy_routing_pattern from a
   matching trunk, or accept and document the suboptimal topology.
3. **apply_positions safe wrapper** (deferred — manual git-revert
   workflow worked well enough for the placement pass).
4. **MCP polish from earlier list**: self.board mtime auto-reload,
   freerouting per-net unrouted reporting, parallel-write thread
   safety audit. Pick whichever bites next.

### Workflow lessons from this session

  - **place_near should always be followed by DRC**, not just
    integrity check. The track-collision logic catches shorts but
    not all sub-clearance near-misses (e.g. via to inner-plane zone).
  - **Refill_zones after any autoroute pass** — freerouting doesn't
    update anti-pads, so post-autoroute DRC always has spurious zone
    clearance / hole_clearance errors that refill_zones absorbs.
  - **Iterate rip-dangling** — removing a leaf trace exposes the
    upstream segment as dangling. Power_module needed 5 iterations
    to stabilise.
  - The MCP server's Python child is long-lived; any time you edit
    Python code in the MCP, **the user must `/mcp` reconnect** before
    the change is visible to subsequent tool calls.

## State at end of 2026-05-16 session 2 (DRC filters + integrity check)

**Second batch of MCP tooling shipped on `develop` today** (after the
placement-constraint work earlier in the day):

  - `get_drc_violations` — now consolidates `unconnected_items` (was
    silently dropped), adds `type`/`net`/`summaryOnly`/`useCachedReport`
    filters, and parses net/layer/length/ref out of kicad-cli item
    descriptions. Commit `fb62505`.
  - `check_pcb_integrity` — new silent-corruption detector. Three
    subchecks: `pad_rotation` (multi-instance per-pad orientation
    drift; uniform=warning, mixed=error), `footprint_overlap`
    (bbox-overlap on same layer, distinguishes pad-copper overlap as
    error vs courtyard-only as warning, reports overlap area), and
    `stacked_pads` (catches same-XY pads on different nets with
    different numbers; skips same-net/same-number/empty false
    positives). Commits `6ef1dd8`, `0584fae`, `f02b7fc`.

**Applied to power_module (this session):**

  - **R26/R27 pad rotation fix** (commit `88c5c91`): pads were at
    rotation 270 deg while footprint was at 0 — remnant of the
    2026-05-14 `apply_positions.py` incident. R12 (same lib_id) was
    the reference. Set pad orientation = footprint orientation;
    cleared 2 cosmetic pad_rotation warnings. DRC: 96 violations
    (was 98), 5 unconnects unchanged, 0 new errors.
  - **Integrity audit results on current v11c**:
    - 0 errors
    - 3 courtyard_overlap warnings (parts placed inside each other's
      manufacturing keep-out, pads don't touch):
      * **R10/L1**: 0.26 mm² (resistor courtyard inside inductor)
      * **L2/C25**: 0.20 mm² (cap edge inside inductor courtyard)
      * **R25/J1**: 0.15 mm² (resistor edge inside USB-C courtyard)
    - 0 stacked_pads, 0 pad_rotation_mismatch
  - **Decoupling audit (unchanged from earlier today)**: 13 primary
    too_far decoupling pairs still flagged; C9 → U1.9 has the
    explicit anchor; the move-and-reroute pass is deferred.

### Next-session candidates (in rough priority order)

1. **BAT1 routing fix** (deferred from earlier today): the 2 vias
   inside each BAT1 cell-terminal pad + In1.Cu bridge are useless
   (the trunk continues on B.Cu — they don't actually carry the
   layer transition). User asked to come back to this. Three options:
   (a) strip BAT1 nets, manually route on B.Cu around courtyard;
   (b) move fork-via cluster from pad XY to the actual transition
   point at (85.60, 64.25); (c) shrink the BAT1 footprint courtyard.
2. **Decoupling placement pass**: 13 too_far primary caps could
   be moved via `place_near`. Each move strips routing on that
   net (BAT+/GND etc.); doable in batches with re-autoroute between.
3. **Courtyard-overlap warnings**: R10/L1, L2/C25, R25/J1 — nudge
   one of each pair to clear the courtyard violation. Same routing-
   damage risk as #2.
4. **More MCP improvements** (still in backlog): `self.board` mtime
   auto-reload, freerouting per-net unrouted, parallel-write thread
   safety audit, `apply_positions` safe wrapper.

---

## State at end of 2026-05-16 session (placement-constraint v1 landed)

**Tooling shipped on the MCP `develop` branch:**

  - `decoupling_audit` — walks the schematic for cap↔IC power-pin pairs
    (auto OR explicit `Placement_Anchor`), measures PCB pad-to-pad
    distance, flags primaries > `within=Nmm`. Per-cap, the closest
    target is "primary"; others on a shared rail are "secondary"
    (reported but not flagged).
  - `place_near(refs, target, maxDist)` — snaps PCB footprints to
    within N mm of a pad/footprint via a polar-grid search; honors
    bbox collisions on the same layer; uses silk-excluded bbox.
  - `Placement_Anchor` schematic property + rename propagation via
    `edit_schematic_component(newReference=…)` and
    `annotate_schematic`. Property grammar:
    `<REF>[.<PIN>]/within=<N>mm[; ...]`.
  - `mcp_constraint_version: 1` in `.kicad_pro` (added on demand by
    constraint-aware tools).

**Applied to power_module (this commit):**

  - Schematic-side anchor: C9 in bms.kicad_sch carries
    `Placement_Anchor = "U1.9/within=3mm"` (intent recorded).
  - `power_module.kicad_pro` has `mcp_constraint_version: 1`.
  - **PCB position unchanged** — moving C9 with `place_near` did work
    (verified: 25,80 → 14.66,67.23, audit went from `too_far` to `ok`
    at 2.24 mm) but stripped routing on BAT+ / GND, taking DRC from
    0 errors → 5 (2 track_dangling, 2 shorting_items, 1 hole_clearance).
    Reverted the .kicad_pcb. The actual placement+rerouting is a
    follow-up: run `place_near` again, then `delete_trace(net="BAT+")`
    + `delete_trace(net="GND")` for stubs around the old C9 spot,
    then re-autoroute.

**Audit current state (this commit):**

  - 13 primary "too_far" decoupling pairs flagged (C9 explicit + 12
    auto-discovered): C9→U1.9 (18.48mm), C8→U1.9 (7.01mm),
    C6→U1.8 (5.16mm), C7→U1.8 (10.72mm), C25/C26→U4.23,
    C10/C11/C16/C17→U2.1 / U3.1, C15/C27/C28→U4.2. All useful
    candidates for placement nudges.

### Next-session resume

The natural next step is the "actually fix the placement" pass:

  1. Decide which decoupling caps to anchor explicitly (the 13 too_far
     primaries are all candidates; some may not be worth fixing if
     they'd require restructuring routing too much).
  2. For each: set `Placement_Anchor` on the schematic, run
     `place_near`, strip the affected nets, re-autoroute.
  3. Re-run `decoupling_audit`; verify primary too_far count drops.

Alternative path: keep going on the layout in general (the 5 residual
unconnects from v11c are mostly QFN-pitch escape problems —
placement-limited; addressing them would also help here).

---

## State at end of 2026-05-15 session (v11c — GND-last + BAT1 fork-vias)

Current PCB state: **v11c (commit b0f7111)** — autorouted with the new
MCP autoroute `layerOrder` default for 4-layer boards
(`[F.Cu, B.Cu, In2.Cu, In1.Cu]`, "GND-last"), then 6 BAT1 cell-terminal
pads fortified with fork-multi-via.

DRC: **0 errors, 5 unconnected items**. The 5 are the residual hard
cases:
  - BAT+ at U4 (two F.Cu track stubs near U4 pads 2-3 not joined)
  - BQ_PH U3-14 → Q2-1 (U3 QFN 0.5mm-pitch escape blocked)
  - CHG_OUT U3-10 → L1-2 (same QFN escape problem)
  - USB_VBUS J1-A9 → J1-A4 (USB-C dual-row jumper)
  - CC1 U2-7 → J1-A5 (regressed under the new layer order; was
    routed in v10)

Plane-cut audit: **439 mm / 54 segments** (vs v9's 912 mm / 99 — 52%
reduction). Better still, the layer balance shifted: In1.Cu/GND only
~68 mm cut, with most signals on In2.Cu/PWR — preserving the GND
image-current return path where it matters most.

BAT1 connectivity: all 6 cell-terminal pads now connect through two
through-vias inside the pad (the pad itself is the "bubble"), bridged
on In1.Cu with a 1.5 mm POWER_4A trace; the existing freerouting
signal becomes the "1 trace out". BAT- pad had one via removed because
it shorted to an F.Cu GND track at (9, 64.05); BAT- currently runs on
single-via to inner — followup work to add a parallel via at a
clear offset (~62.75 mm y).

### MCP server work shipped today

On the develop branch of KiCAD-MCP-Server:

  - **`autoroute` / `export_dsn` `layerOrder` param** (commit `88fad7f`),
    with the GND-last default applied automatically to 4-layer boards.
    DSN rewrite helper has 8 unit tests. Verified end-to-end on this
    board.
  - **`audit_plane_cuts` MCP tool** (commit `7966e6f`) — reports
    inner-layer signal-trace lengths per net, sorted, to pick ripup
    candidates.
  - **`delete_trace` SWIG corruption — root cause + fix** (commit
    `5fc25b3`). `BOARD.Remove(item)` corrupts process-global SWIG
    state after ~650 calls; `BOARD.RemoveNative(item)` is the
    in-process-safe alternative. Switched 5 call sites (4 in
    delete_trace, 1 in delete_component). Subprocess workaround
    from earlier in the session deleted.
  - **`open_project` SETTINGS_MANAGER cache fix** (commit `0f3fb93`)
    — out-of-band .kicad_pro edits now take effect on re-open.
  - **`route_pad_to_pad` obstacle check** (commit `902e7da`) —
    refuses to straight-line through foreign-net copper.
  - **`get_nets_list includeStats`** implementation (same commit).
  - **schema discoverability** — `query_traces includeVias`,
    `delete_trace net="*"` documented (commit `902e7da`).
  - **python tool_schemas.py sync** (commit `2f6b8f1`).
  - **docs/PCB_DESIGN_WORKFLOW.md** updated with the
    `route_pad_to_pad` straight-segment / obstacle warning (same).
  - **CHANGELOG.md** has dated entries for every commit on
    `develop` since 2026-05-13.

### Tomorrow's starting point

User wants to start with **the decoupling-audit + place_near tools**
per the design agreed in
[[feedback-placement-constraints-design]]:

  1. **`decoupling_audit`** — walk the schematic, identify cap↔IC
     power-pin associations by net (a cap with one pad on an IC's
     VCC/VIN-class pin and the other on GND), compare to current PCB
     positions, flag any cap > N mm from its IC pin.
  2. **`place_near`** — `place_near(refs, target_ref_or_pad,
     max_dist)` — places the listed components in free space within
     N mm of the target, respecting bbox collisions.
  3. **`Placement_Anchor`** property support — read from
     `.kicad_sch` (schematic-resident, per the agreed design);
     audit emits unresolved references as warnings.
  4. **Rename propagation** — any tool that renames a schematic
     component should scan all `Placement_Anchor` values and update
     refs accordingly; report dangling refs.
  5. Add `mcp_constraint_version: 1` to `.kicad_pro` for the
     property-value format.

Concrete first target on power_module: **C9** (100 nF, U1 BAT-pin
decoupling) is at (25, 80) but U1 is at (17, 62) — ~20 mm away.
Per the BMS pin reference in this NOTES file, C9 should sit near
U1's pin 10 / 9 (BAT / REGSRC).

### Still-open thread (low priority)

  - File an upstream KiCad GitLab issue for the `BOARD.Remove(item)`
    SWIG corruption — root cause documented in MCP commit `5fc25b3`
    and `mcp_server_issues.md`. A minimal-repro Python script is in
    `KiCAD-MCP-Server/tests/test_remove_native_does_not_corrupt.py`.
  - Add a parallel BAT- via at (6.35, 62.75) (current-sharing for the
    BAT- net, which is single-via on this board).
  - 5 residual unrouted nets above — most are placement-limited.

### Quick orientation for cold-resume

```
git -C ~/projects/kicad_agent/projects/power_module log --oneline -8
git -C ~/projects/kicad_agent/KiCAD-MCP-Server log --oneline -10
```

The PCB is in a good clean state (0 DRC errors). Don't strip and
re-route casually — the BAT1 fork-via fixes are hand-applied on top of
the v11 autoroute output and would be lost. If a re-route IS needed,
re-apply the BAT1 fork-via pattern (script-worthy at this point —
candidate for a `restore_bat1_vias` helper).

## State at end of 2026-05-14 afternoon session (rotation fix + v6 re-route)

Three big things fixed today after the user's visual inspection
caught the pad orientation issue:

  1. **Pad rotation repair.** `apply_positions.py` from yesterday
     rewrote `(at X Y rot)` lines on 57 of 71 footprints without
     touching per-pad local rotations.  Pad POSITIONS rotated
     correctly but pad SHAPES rendered in the library-default
     orientation.  J1's 16 SMD pads stacked vertically on top of
     each other; U4's HTSSOP-28 pad rows pointed into the body;
     same on Q1-4 (SO-8).  Fix: for each rotated footprint, call
     `pad.SetOrientationDegrees(fp.GetOrientation())`.  See
     `fix_pad_rotations.py` archived in the project dir.  Almost
     certainly the real reason yesterday's autoroute capped at ~64%.

  2. **Layout corrections.**  J1 (USB-C) rotated +180° so the
     receptacle opening faces the board edge and pins face inward.
     J2 & J3 (pin headers) rotated +90° so the pin row runs along
     X instead of running off the y=110 board edge.  BAT1 flipped
     to back layer + DNP (user has the physical part).  See
     `fix_orientations_and_bat.py`.

  3. **C24 placement.**  C24 was placed inside L2's bbox at
     (62, 80); moved to (58.5, 80) in the 5 mm gap between C15 and
     L2.  Fixed the 3 shorting_items DRC errors from v4/v5.

v6 routing result:
  - 616 tracks + 117 vias, 20 unrouted ratlines, 0 shorts,
    0 solder_mask_bridges.
  - Freerouting completed in 2:54 (vs 13:52 for v3) — pad shapes
    now correct, no shape-mismatch retries.
  - 13 clearance violations remain: 7 intra-package (U2/U3 QFN
    pitch vs netclass default; tune netclass), 6 component-
    to-component (R1/R12 etc, placement nudges).
  - Cosmetic silk_overlap (60) and silk_over_copper (35) are
    follow-up cleanup, not blockers.

Open process gotcha logged to mcp_server_issues memory: MCP caches
`self.board` and an out-of-band file edit (via direct pcbnew Python)
isn't visible to subsequent MCP calls until `open_project` is
re-called.  Caught us on v5.

## V2 idea backlog

  - **Dedicated IC overheat thermistor** near U3 (BQ24650 charger)
    and U4 (LM5176 buck-boost).  Both ICs have internal thermal
    shutdown but no externally readable temperature.  A 10k 0603
    NTC near each, biased into a BMS spare ADC pin or a dedicated
    µC pin (V2 design likely includes a host µC), would give
    host-visible temperature monitoring.  User has thermistor stock
    on hand.  Note 2026-05-14.
  - **JLCPCB header rotation offset.**  Kicad's pin-header
    footprints and JLCPCB's pick-and-place orientation disagree by
    90° (or sometimes 180°).  When generating CPL for assembly,
    pin headers need a rotation correction — either via a
    documented per-part offset table during BOM/CPL upload, or by
    using JLCPCB-specific footprints with the correction baked in.
    Doesn't affect the schematic / PCB layout, only the assembly
    upload step.

## State at end of 2026-05-14 session (BAT+ inner pour + re-route)

Two MCP-server fixes landed on `develop` this morning that materially
affected this board:

  - `add_layer` formula corrected (commit `6d438de`) — inner-layer
    number now maps to the correct PCB_LAYER_ID (even spacing in
    KiCad 9).  Both the silently-dropped In2.Cu pour and the stray
    F.SilkS zone were the same bug.
  - `export_position_file` handler implemented (commit `0141708`).

PCB repair + re-route summary (commits `29491ea` + `cb8922d`):

  - Renamed layer id 5 back to F.Silkscreen (was corrupted to "In2.Cu").
  - Added BAT+ pour on In2.Cu (the real one, id 6), clearance 0.25mm.
  - Stripped all v2 tracks/vias (379+79) and ran freerouting -mp 25
    on the fresh 4-layer board.
  - **BAT+ went from 218.5mm of F.Cu trace -> 15.9mm + 9 stitching
    vias to the In2.Cu pour.**  GND likewise stitches via 34 vias to
    the In1.Cu pour.
  - Final state: 367 tracks + 76 vias, 2 pours filled.
  - ~18 unrouted ratlines remain, all in the dense buck-boost area
    (BB_HDRV1/HDRV2, BB_EN, BB_PGOOD, BMS_CHG, CHG_OUT — short single-
    conn hops) plus 5 USB_VBUS pin-pair hops between Q2 / U2 / J1
    VBUS pads.  Placement-limited; closing the gap needs either a
    bigger board (110×130 mm) or manual placement refinement.

Side experiment kept in repo: `power_module_planes.dsn` + `.ses`.
Setting In1.Cu/In2.Cu to `(type power)` in the DSN drops routing from
~80% to 40% because signals get squeezed onto F.Cu+B.Cu only.
Documents the trade-off: 4-layer board needs ALL layers as routable
when component density is this high.

### Cold-resume reader next step

Two paths:
  1. **Close the routing gap.**  Grow board to ~110×130 mm and re-
     place via the schematic-autoplacer-equivalent for the PCB
     (doesn't exist yet — currently manual move_component).  Or
     manually route the ~18 remaining ratlines via
     `route_pad_to_pad` / `route_trace`.
  2. **Move on to a new design** treating power_module as
     "feasible MVP" and accepting the ~10% unrouted ratlines as a
     workflow limit on this board.

## State at end of 2026-05-13 session (cell holder swap)

**BT1-3 holder swap complete (task #93).** The three `Device:Battery_Cell`
symbols (BT1-3) have been replaced by a single 6-pin `power_module_lib:BH-18650-B5BA016`
symbol named **BAT1** at (175.26, 80.01) in `bms.kicad_sch`.

Pin-to-net mapping (all cells facing same direction, + on left side
matching pad-1 polarity marker on the holder footprint):

  - Pin 1 (top-left, cell-1+)   = BAT+
  - Pin 2 (top-right, cell-1-)  = CELL2_TOP   ← tap to VC3 sense via R3/C3
  - Pin 3 (mid-left, cell-2+)   = CELL2_TOP   ← physical PCB jumper pad 2↔3
  - Pin 4 (mid-right, cell-2-)  = CELL1_TOP   ← tap to VC2 sense via R2/C2
  - Pin 5 (bot-left, cell-3+)   = CELL1_TOP   ← physical PCB jumper pad 4↔5
  - Pin 6 (bot-right, cell-3-)  = BAT-        ← VC0 reference

BAT1 has Footprint + LCSC + Description set. ERC: 2 errors + 7 warnings,
mostly pre-existing or cosmetic (easyeda2kicad symbol uses "unspecified"
pin types → Passive/Unspecified warnings on R1-4 connections; "Pin not
connected" likely refers to a different sheet).

**J1 USB-C swap complete (task #94).** Symbol replaced
`Connector:USB_C_Receptacle_PowerOnly_24P` → `Connector:USB_C_Receptacle_USB2.0_16P`
on `charger.kicad_sch` at (220, 80). All 5 active nets relabeled
(USB_VBUS, CC1, CC2, GND on connector pin, GND on SHIELD pin). The 6
data+SBU pins (A6/B6 = D+, A7/B7 = D-, A8/B8 = SBU) carry NC markers.
ERC dropped 9 → 2 (the remaining 1 error is the long-standing
PWR_FLAG/Input-Power issue; 1 warning is the global fp-lib-table not
including `power_module_lib` — harmless, project-local lib-table has it).

**Stackup + netclasses applied (tasks #86, #87).**

  - 4-layer copper added: F.Cu (L1), In1.Cu (L2 = GND), In2.Cu (L3 =
    PWR), B.Cu (L4). Verify via `grep -A 6 '(layers' power_module.kicad_pcb`.
  - Netclasses POWER_4A (1.5 mm / 0.25 mm) and POWER_2A (0.8 mm /
    0.2 mm) added to `power_module.kicad_pro` `net_settings.classes`
    array with netclass_patterns assignments for BAT+, BAT-, V12_OUT
    (POWER_4A) and USB_VBUS, CHG_OUT, BQ_PH (POWER_2A). Done via
    direct .kicad_pro edit because both `add_net_class` and
    `create_netclass` MCP tools are broken (one "Unknown command",
    the other crashes on a SWIG netclasses_map.Find lookup).

**sync_schematic_to_board partial — restart required (task #88).**

  - First run imported only the 3 top-level footprints (J2, J3, SW1)
    and skipped the 67 child-sheet components. Root cause:
    `_auto_import_footprints_from_schematic` in `python/kicad_interface.py`
    iterated only the top schematic, not the hierarchical sub-sheets.
    Patched in `KiCAD-MCP-Server` develop branch (commit `6117986`)
    to rglob every `.kicad_sch` and deduplicate by reference. The
    Python subprocess inside the MCP server caches the old module, so
    the fix needs a Claude Code restart to take effect.
  - 56 nets are already populated on the PCB from the partial sync,
    and the 3 top-level footprints have pad nets assigned.

**Cold-resume reader next step (after restart):**

  Re-run `sync_schematic_to_board` against
  `power_module.kicad_sch` + `power_module.kicad_pcb`. The
  hierarchical walk should pick up the 67 missing footprints and
  assign all pad nets. Confirm via
  `grep -c '^\t(footprint' power_module.kicad_pcb` — expect ≥70.
  Then continue with tasks #89-#92 (layout → outline → autoroute →
  DRC/export).

---

## State at end of 2026-05-13 session 2 (PCB layout + autoroute)

PCB layout, pours, and a first autoroute pass are now committed.
The board is at 95×110 mm rounded rectangle with all 71 footprints
placed (`apply_positions.py` script kept in repo for direct-rewrite
recovery if MCP write paths diverge again).

Stackup applied:
  - L1 F.Cu — signal routing
  - L2 In1.Cu — GND pour (the working one)
  - L3 In2.Cu — BAT+ pour did NOT persist; layer-duplicate bug in
    `add_layer` / `get_layer_list` corrupts persistence. Deferred.
  - L4 B.Cu — signal routing only (no pour; the original B.Cu GND
    pour was occluding signal routes and was stripped before v2
    autoroute)

Autoroute v1 (8 passes): 412 tracks + 74 vias, 66/184 nets still
unrouted.

Autoroute v2 (20 passes, after iteration): 379 tracks + 79 vias.
Slightly worse — placement density is the real ceiling here. 34
via_dangling errors in DRC indicate incomplete routes.

**Three more MCP-server bugs fixed in develop this session:**

  - `sync_schematic_to_board` auto-import skipped hierarchical
    sub-sheets (commit `6117986`).
  - `place_component(boardPath=…)` rebuilt ComponentCommands,
    invalidating the `move_component` dispatch reference so writes
    silently went to an orphaned BOARD instance (commit `b8183d8`).
  - `autoroute` was missing from longRunningCommands so its 30s
    timeout killed any non-trivial run (commit `c990d48`).
  - `export_bom` didn't walk hierarchical sub-sheets — BOM had only
    3 parts instead of 71 (commit `eca569a` — needs MCP restart to
    take effect).

**Cold-resume reader next step:**

  1. MCP restart.
  2. `mcp__kicad__export_bom(schematicPath=...kicad_sch,
     outputPath=power_module_bom.csv, format=CSV,
     includeAttributes=[LCSC, Description])` — confirm row count
     is 28 (28 unique BOM lines from 71 instances).
  3. `mcp__kicad__export_gerber(outputDir=gerber/,
     generateDrillFiles=true, generateMapFile=true)`.
  4. `mcp__kicad__export_position_file(outputPath=pos.csv,
     format=CSV, units=mm)`.
  5. Commit `gerber/`, `power_module_bom.csv`, `pos.csv`. Tag #92
     completed.

The autoroute coverage gap (62-64%) is best closed in a later
session by either (a) growing the board to ~110×130 mm and re-
placing, or (b) doing manual placement informed by a ratsnest view.
Not a workflow blocker — the demo end-to-end has been exercised.

---

## State at end of 2026-05-12 session (PCB layout phase started)

**Parts pass complete** for all non-cell components (67 instances).
Footprint + LCSC + Description set on every R, C, L, IC, FET, LED,
NTC, and J1 across `bms.kicad_sch`, `charger.kicad_sch`, and
`buckboost.kicad_sch`.

### Decisions made this session

  - **Stackup**: 4-layer (GND@L2, PWR@L3). Not yet applied to .kicad_pcb.
  - **Battery holder**: 3-cell `BH-18650-B5BA016` (LCSC C19184086,
    Extended). Fetched via `easyeda2kicad --full --lcsc_id C19184086`
    into `projects/power_module/libs/power_module_lib.{kicad_sym,pretty}`.
    6-pin footprint (one pad per cell terminal). **Schematic swap of
    BT1-3 → single holder symbol still pending** (task #93).
  - **USB-C J1**: 16-pin physical part (TYPE-C-31-M-12, C165948).
    Schematic still references the 24P `Connector:` symbol — KiCad
    netlist export should still work since unused symbol pins won't
    map to footprint pads, but ERC may warn. Cleanest fix: swap symbol
    to `Connector:USB_C_Receptacle_USB2.0_16P`. Deferred.
  - **R21 value**: changed 90k → 91k (E96 1% value, allows part
    selection); buck-boost FB ratio becomes 91k:10k → Vout ≈ 12.1V
    with the LM5176's 1.2V Vref. Acceptable for the 12V output.
  - **Description property**: new workflow guideline — short
    function-not-spec (<8 words, role-focused) on every component as
    placed. Applied retroactively to all 67 components this session.
    Refine the rule into `workflow_pcb_from_schematic.md` after the
    full PCB pass.

### Key parts (full BOM in conversation transcript)

  - **Basic** (14): UNI-ROYAL 0603 resistors {100Ω, 1k, 5.1k, 10k,
    20k, 22k, 100k}; Samsung X7R caps {1nF, 10nF, 100nF, 1µF 0805,
    10µF 0805, 22µF 1206}; C0G 47pF 0603; Green LED 0805 (KT-0805G).
  - **Extended** (14): 91k 0603 (R21); 0.005Ω + 0.01Ω 1206 power R;
    6.8µH + 10µH SMD inductors (custom footprint from easyeda2kicad);
    NTC 10k 0603; Blue LED 0805; BQ76920PWR; CH224K; BQ24650RVAR;
    LM5176PWPR; AP9926 (FDS9926A sub) ×4 instances; USB-C 16P; 3S
    cell holder.

  Total Extended setup at JLCPCB: 14 × $3 = **$42**.

### Files added this session

  - `projects/power_module/fp-lib-table` — registers
    `power_module_lib` project-local footprint library.
  - `projects/power_module/sym-lib-table` — same for symbols.
  - `projects/power_module/libs/power_module_lib.kicad_sym` — symbols
    for holder + 2 inductors (from easyeda2kicad).
  - `projects/power_module/libs/power_module_lib.pretty/*.kicad_mod`
    — footprints for same.
  - `projects/power_module/libs/power_module_lib.3dshapes/` — 3D
    models.
  - `easyeda2kicad` (pip package) installed into project venv.

### Next steps (deferred from end-of-day stop)

  1. **BT1-3 → holder symbol swap** (#93). Replace 3 Battery_Cell
     symbols with one `BH-18650-B5BA016` 6-pin symbol. Wire pads
     1,2=cell1±; 3,4=cell2±; 5,6=cell3±. Verify pad orientation from
     datasheet at
     https://jlcpcb.com/api/file/downloadByFileSystemAccessId/8590907619093520384
     (cells may all face same direction per user preference).
  2. **J1 symbol** — swap from 24P to 16P USB-C symbol so ERC stops
     warning. Pin remapping: VBUS (A4,A9,B4,B9), GND (A1,A12,B1,B12),
     CC1/CC2 → CH224K, D+/D- → noop or NC.
  3. **Stackup** (#86) — configure 4-layer in `.kicad_pcb`.
  4. **Netclasses** (#87) — POWER_4A / POWER_2A / signal default.
  5. **sync_schematic_to_board** (#88) — imports footprints + nets.
  6. **Layout** (#89) — `move_component` per subcircuit.
  7. **Board outline + pours** (#90), **autoroute** (#91), **DRC +
     BOM/Gerber export** (#92).

### Where to resume

If the next session starts cold: read this section, then run
`mcp__kicad__list_schematic_components` on any of the three child
sheets and confirm LCSC properties are present. Then start with
either the BT1-3 holder swap (cleanest first) or jump to stackup +
sync if you want to defer the holder until layout.

## State at end of 2026-05-13 session

User signed off on the autoplacer + recipe + connect_pins + diagnostics
work as "sufficiently good for now".  Final state of the three child
sheets:

  - bms, charger, buckboost all pass `compare_netlists` against the
    originals (every pin's named net preserved).
  - All three pass `diagnose_chains` with 0 DUPLICATE_LABELS and
    0 CROSS_NET.  LOOP flags remain on a handful of multi-pin chains
    but are now legitimate small wire-graph cycles, not parallel-edge
    artefacts.
  - 0 unrelated-wire-crossings after the chain-aware fix to
    `_scan_unrelated_wire_crossings` (it had been flagging two
    segments of one labelled chain as "unrelated" because the
    label-at-endpoint check missed labels reachable only via the
    wire graph).
  - Recipe output schematics at /tmp/claude-1000/autoplace_run/
    (not in git).

Open task #74 still latent: cross-net merge in
`WireManager._break_wires_at_point`.  Reproducer at
`tests/test_wire_manager_cross_net.py` is `xfail strict=True`; once
the underlying defect is fixed (thread `expected_net` through
`add_wire`, refuse cross-net splits in `_break_wires_at_point`), the
test passes and pytest will tell you to remove the marker.

### Maybe-someday: post-routing layout tightening

Idea raised 2026-05-13: once a routed schematic is topologically
valid (every pin on its target net, no cross-net merges), an
optional polish pass could:

  - Shrink wires that are now longer than they need to be (the
    autoplacer left components farther apart than the final route
    geometry needs).
  - Pull components inward toward their connection centroids,
    respecting bounding-box collisions, to reduce visual sprawl.
  - Re-check whether any previously-disjoint chains can now be
    bridged with a short wire after the tightening, and lay it.

Constraint: must NOT alter the netlist (call `compare_netlists`
after each pass to verify).  Pure visual / area refinement.  Not
urgent — current output is "feasible for a human to parse".

## State at end of 2026-05-12 session (part 2)

User tested the morning's Phase 5 rewrite on the BMS sheet and
reported 6 remaining issues; all 6 were confirmed via a new
diagnostic script ``/tmp/claude-1000/claude/diagnose_chains.py``
that enumerates chains/labels/pins per chain and flags
``DUPLICATE_LABELS``/``CROSS_NET``/``LOOP``.

Three Phase-5-side fixes landed this afternoon:

1. **``use_stub_style`` now counts all this-net chains, not just
   orphans.**  Fixes the VC3 asymmetric-labelling case where a Phase
   3-stubbed chain coexisted with an orphan multi-pin chain that got
   an in-line label.
2. **Branch-stub merge guard.**  Before laying a candidate
   perpendicular stub, walk the wire chain at the stub-end and refuse
   any direction that would T-junction with another (disjoint) chain.
   Fixes the REGOUT / SRP duplicate-labels-on-merged-loop case where
   two orphan sub-chains got separate branch-stubs that bridged
   together via the new wires.
3. **Re-walk each chain right before labelling.**  Picks up any
   merges/labels added by previous iterations in the same Phase 5
   call.  Belt-and-suspenders with #2.

Remaining open:

- **Issue #5 (FET_MID loop)** — chain has 12 wires for 8 duplicate-
  pad pins on Q1's two units; MST pairs include zero-distance same-
  coord pairs (Q1u1/7 ≡ Q1u1/8) which create parallel-edge cycles.
  Lower priority; out of scope for Phase 5.
- **Issue #6 (VC1 + VC2 merged)** — issue #74 (cross-net merge in
  ``WireManager.add_wire``'s ``_break_wires_at_point``).  Bigger fix
  surface, still pending.  Phase 5's "skip chain with foreign-net
  label" guard prevents the merge from being amplified into extra
  labels but doesn't fix the underlying bug.

Next session: have user re-run autoplacer + rewire on the BMS sheet
(Jupyter with autoreload picks up these changes automatically), then
diagnose again.  If clean on #2/#3/#4, take on #74.

## State at end of 2026-05-12 session

**Phase 5 duplicate-label bug fixed via a chain-graph rewrite.**
- New public helper `commands.wire_connectivity.walk_wire_chain` BFSes
  the real wire graph (T-junction aware via the existing
  `_build_adjacency`).  Returns `WireChain` with `points`, `labels`,
  `wire_indices`, `segments`, `free_endpoints`.  9 unit tests.
- Phase 5 in `connection_schematic.py` rewritten on top of it.  Runs
  AFTER Phase 3 (so Phase 3's labels are in the wire graph already).
  Walks chains from each wired pin endpoint, dedupes by wire_indices,
  classifies as labelled / orphan, places labels (free-endpoint
  preferred, corner branch-stub when ≥2 orphan chains, in-line
  fallback for single-chain pin-to-pin nets).  Defensive: skips
  chains carrying a foreign-net label (don't compound issue #74).
- Union-find pair-grouping and `phase3_future_labels` lookahead are
  deleted.  Helper lives at `_phase5_label_orphan_chains` in
  `connection_schematic.py`; placement at `_choose_label_position`
  and `_try_branch_stub_at_corner`.
- 4 new integration tests in `TestPhase5ChainFinder` cover T-junction
  single-labelling, already-labelled chain non-relabelling, two-
  disjoint-chains-each-labelled, and foreign-label skip.

**Issue #74 fixed 2026-05-13.**  `WireManager.add_wire` and
`add_polyline_wire` now take an optional `expected_net=` argument.
When set, `_break_wires_at_point` and `_existing_endpoints_on_segment`
walk the existing wire's chain via `walk_wire_chain` and refuse to
split it if any chain label is foreign (not `expected_net`).  All
`connect_pins` / `connect_to_net` / Phase 5 / `add_schematic_net_label`
call sites pass the expected net.  Default `None` preserves the old
behavior.  See `tests/test_wire_manager_cross_net.py`.

Test the new code on the BMS sheet by pushing the failing schematic
to `/tmp/work_kicad/work.kicad_sch` and re-running connect_pins(auto)
on the previously-doubled-label nets (FET_MID, REGOUT, VC3).

## State at end of 2026-05-10 session

**The autoplacer + connect_pins(auto) work has been the focus.** A
long chain of improvements landed today on `fixes/improvements_2`,
listed roughly in commit order:

  - PinLocator multi-unit lookup, wire splits at existing endpoints,
    add_schematic_net_label always-stub, astar-tee run-out fix.
  - Pin-aware attraction + multi-pass snap_positions with pin-coord
    safety check (catches duplicate-pad collisions and stub-end-on-
    pin-endpoint between different ref+unit combos).
  - Stub-zone reservation in routing (rule 7), preserve no_connects,
    centre placement on A4 page.
  - MST-ordered pair wiring (commit `89c05c5`) — fixes split-chain
    issues like REGOUT.
  - Adaptive max_len in rewire_session — scaled with placement
    diagonal, fixes routes around big ICs (commit `c9eb506`).
  - Phase 5 branch-stub for multi-orphan nets only; otherwise in-line
    label.  Two-pass with future-Phase-3-labels lookahead (commits
    `0ff4efb`, `fab22f9`).
  - Polarity force rendered separately in viz.  New polarity_torque
    force rotates GND pins down, V+ pins up.  Pin-orientation torque
    skips power nets.  Routing _build_grid_obstacles now unblocks the
    cell ONE STEP outward of each pin endpoint so routes can approach
    pins whose component bbox extends past the pin.
  - Autoplacer real-time visualizer (`commands/autoplacer_viz.py`):
    matplotlib-based; bbox + pins + force overlays.  Runs in iPython
    or Jupyter Lab via `%matplotlib qt5` / `%matplotlib widget`.

**Outstanding issues for Monday (2026-05-11)**:

The user has been visually inspecting the autoplacer output and
observed two remaining problems on the BMS sheet:

  1. **Some duplicate labels persist** despite the Phase 5 future-
     Phase-3-labels lookahead.  Hypothesis: the union-find chain-
     grouping in Phase 5 uses wired_pairs' segment endpoints, which
     don't reflect mid-segment wire splits done by sync_junctions /
     `_break_wires_at_point`.  Two pairs whose wires connect via a
     T-junction (one's endpoint on another's interior) end up in
     separate chain groups, each getting its own auto-label.

  2. **At least one instance of separate nets being merged.**
     Hypothesis: WireManager.add_wire's `_break_wires_at_point`
     splits any existing wire whose interior contains the new wire's
     endpoint, regardless of net.  After the split, sync_junctions
     adds a junction → KiCad's wire graph treats both nets as
     connected.  The spurious-connection guard (rule 3) is supposed
     to catch this BEFORE the wire is added, but may have a gap.

Reference file: `/tmp/work_kicad/work.kicad_sch` is the user's last
test-run output, kept for the Monday session.

**Plan for Monday** (see tasks #73, #74, #75):
  - Build a `walk_wire_chain(start_pt, schematic_path) -> Set[Point]`
    helper that BFSes the actual wire graph in the file, accounting
    for splits and junctions.  This is the foundation for both fixes.
  - Use it to fix Phase 5 chain grouping (issue #1).
  - Audit the spurious-connection guard for gaps that allow cross-
    net merging via wire splits (issue #2).  Possibly tighten
    `_break_wires_at_point` to refuse cross-net splits.

## State at end of 2026-05-09 session

**Schematic is COMPLETE and split into hierarchical sheets.**
The flat power_module.kicad_sch has been partitioned into:
  - `power_module.kicad_sch` (top-level: 3 sheet blocks + J2 output
    header + J3 I²C breakout + SW1 user switch)
  - `bms.kicad_sch` (BMS chip + cells + protection FETs + signals)
  - `charger.kicad_sch` (USB-C → CH224K → BQ24650 sync buck)
  - `buckboost.kicad_sch` (LM5176 4-switch buck-boost)

Cross-sheet nets are global_label: BAT+, GND, V12_OUT, SDA, SCL,
ALERT, MODULE_EN.

ERC at top-level: 0 errors, 1 inductor-footprint warning (pending
the LCSC pass).

Today (2026-05-09) the heavy lifting was on the MCP server side —
many fixes / new tools landed on the `fixes/improvements_2` branch:

  - `add_schematic_sheet` (instantiate a hierarchical sheet block)
  - Schematic autoplacer (force-directed; 7 MCP tools)
  - Renderer crop+colored, sheet-bbox aware, multi-sheet picker
  - PinLocator cache invalidation on file mtime
  - Autorouter rule 6 (no perpendicular wire crossings)
  - Phase 5 orphan-chain fix (label every wired chain)
  - Auto-orientation for net labels
  - Per-unit autoplacer node, real bbox, property text follow
  - Standalone-friendly instances when applying placer output

The schematic auto-orient labels pass was applied to all four child
sheets so labels face outward from their pins.

## Next steps (in order)

1. **Fix `PinLocator` multi-unit pin lookup bug.** Currently it
   returns the first-placed instance's `(at)` for ALL pin numbers,
   so unit-2 pins on multi-unit symbols (FDS9926A) come back at
   wrong world coords.  Workaround in autoplacer's rewire bypasses
   `connect_pins` for this reason; once fixed, autoplacer can
   re-enable autorouted wires.  See `mcp_server_issues.md` for
   details.

2. **Tune the autoplacer's force constants** on the BMS sheet
   (or a small synthetic test project — see #52 in tasks).
   Current run produces correct connectivity but components are
   spread too thin; want denser packing without overlap.

3. **Apply the autoplacer to power_module sheets in polish mode.**
   Low force, short anneal, on the real bms / charger / buckboost
   sheets.  Needs to use `standalone=False` to keep the
   hierarchical paths intact.

4. **Set Footprint + LCSC** properties on every non-power
   component (the easy-to-skip step — see workflow memory).

5. **PCB layout pass on power_module** — task #54.  Shake bugs
   out of the PCB workflow on this design before starting v2.

6. **Optionally**: kick off a fresh v2 design using all the
   tooling lessons we've accumulated (placer, sheets, label
   orientation, etc.).

## BMS pin reference (BQ76920PW, TSSOP-20)

```
Left side (gate drives + I²C + control):
  pin 1  DSG     output         — discharge FET gate
  pin 2  CHG     output         — charge FET gate
  pin 4  SDA     bidirectional  — I²C data
  pin 5  SCL     input          — I²C clock
  pin 6  TS1     passive        — temperature sense (NTC to gnd)
  pin 7  CAP1    passive        — cell-balance bootstrap cap (1 µF to gnd)
  pin 20 ALERT   bidirectional  — host alert / wake (active high)
Right side (battery sensing + power):
  pin 8  REGOUT  power_out      — internal LDO output (~3.3 V)
  pin 9  REGSRC  power_in       — regulator source (top of stack via R)
  pin 10 BAT     input          — battery voltage input (top of stack)
  pin 12 VC5     input          — for 4-5S; jumper to VC3 in 3S
  pin 13 VC4     input          — for 4-5S; jumper to VC3 in 3S
  pin 14 VC3     input          — top of cell 3 (= BAT+ in 3S)
  pin 15 VC2     input          — between cell 2 and cell 3
  pin 16 VC1     input          — between cell 1 and cell 2
  pin 17 VC0     input          — bottom of cell 1 (BAT-, top of sense R)
  pin 18 SRP     input          — sense-resistor positive (BAT- side)
  pin 19 SRN     input          — sense-resistor negative (module GND)
Bottom:
  pin 3  VSS     power_in       — IC ground = SRN
  pin 11 NC      no_connect
```

3S configuration: jumper VC3=VC4=VC5 to BAT+ (top of cell 3).

## Wiring intent (BMS subcircuit, high level)

- **Cell stack** (top→bottom): BT3+ (BAT+) → BT3- = BT2+ → BT2- = BT1+
  → BT1- (top of sense path).
- **Cell taps via 100 Ω resistors** R1–R4 → VC0..VC3:
    R1 (100): BT1- ─ VC0      ; R2 (100): BT1+/BT2- ─ VC1
    R3 (100): BT2+/BT3- ─ VC2 ; R4 (100): BT3+ (= BAT+) ─ VC3.
  Tap-RC caps C1–C4 (1 nF) from each VC node to local cell-negative.
- **VC3 = VC4 = VC5** all tied to BAT+ (3S configuration).
- **Protection FETs** (Q1, dual N-channel SO-8):
    Drains tied together; sources go to BAT- (DSG side) and to top
    of sense resistor (CHG side).  CHG gate ← BMS.CHG (pin 2),
    DSG gate ← BMS.DSG (pin 1).  Standard back-to-back arrangement.
- **Sense resistor R5 (0.005 Ω)** in series between Q1 and module
  GND.  SRP at top, SRN at bottom (module GND).
- **VSS (pin 3) = SRN = module GND**.
- **REGOUT (pin 8)**: 1 µF (C6) + 100 nF (C7) to GND.
- **BAT (pin 10), REGSRC (pin 9)**: 10 µF (C8) + 100 nF (C9) to GND.
- **CAP1 (pin 7)**: 1 µF (C5) to GND.
- **I²C**: SDA / SCL → 10 kΩ (R6/R7) pull-ups to REGOUT, plus
  external 4-pin header (later integration step).
- **ALERT (pin 20)**: 10 kΩ (R8) pull-up to REGOUT (open-drain output).
- **TS1 (pin 6)**: 10 kΩ NTC (TH1) to GND, 10 kΩ (R9) bias to REGOUT.
- **User switch SW1**: in this BMS-only subcircuit it's unwired;
  the wiring to the BMS shutdown (typically via a small npn pulling
  TS1 below threshold, or via a dedicated /SHUT pin on later BMS
  variants) is finalised during the integration step.

## Q1 / FET notes

- Symbol used: `Transistor_FET:FDS9926A` (dual N-channel SO-8).
  The symbol is electrically representative of the chosen part.
- LCSC part to set during the LCSC pass: `C353066` (8 A, 30 V,
  26 mΩ, 1.5 V Vgs(th)) — same SO-8 footprint, better specs.
- Footprint to set: `Package_SO:SO-8_3.9x4.9mm_P1.27mm` (or the
  specific manufacturer footprint if the symbol has a default).

## PCB layout preferences (for when we get there)

- **4-layer stackup**, not 2-layer:
    L1 signal · L2 GND plane · L3 power plane · L4 signal.
- **High-current trace widths sized by ampacity** (IPC-2221 / JLC
  calculator, not eyeballed). Power-rail nets to identify ahead of
  routing: `BAT+`, `BAT-`, `V12_OUT`, charger inductor / FET nodes,
  buck-boost inductor / FET nodes. Create per-current-band netclasses
  (`POWER_4A`, `POWER_2A`, signal-default) before routing.
- Heads-up: **layer count and per-class trace widths have not been
  tested in the MCP server**. Watch for tooling weirdness (autorouter
  ignoring class widths, inner-layer pours misbehaving, etc.) and log
  to `mcp_server_issues.md`. See `feedback_pcb_stackup.md` for detail.

## Other live threads (cross-reference)

- MCP server `fixes/improvements_2` branch has 13 commits today;
  `develop` exists but is behind. When ready to promote, use
  `git merge --no-ff` (see `feedback_git_history.md`).
- Open MCP-server issues worth picking up later (in
  `mcp_server_issues.md`):
  - Thread-safety audit of write tools.
  - `set_board_size` + `add_board_outline` overlap.
  - JLCPCB backfill: 2.68M rows still have empty category.
- Memory updated this session:
  - `feedback_parallel_writes.md` (sequential writes for non-idempotent)
  - `feedback_git_history.md` (no-ff merges, no rebase)
  - `feedback_pcb_workflow_check.md` (read workflow before starting PCB)
  - `workflow_pcb_from_schematic.md` (rewritten with fixes from today)

## Useful artefacts saved

- `/tmp/claude/place_bms.py` — script that placed the BMS components.
  May not survive across sessions; if it's gone, the placement is
  already in the schematic so the script is just historical.
- `/tmp/claude/show_bq76920_pins.py` — pin-layout extractor; output
  is reproduced above for permanence.
- `/tmp/claude/dedupe_no_connects.py` and `dedupe_edge_cuts.py` —
  workarounds for known MCP issues.
