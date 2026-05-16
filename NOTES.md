# Power module — session resume notes

Living document; updated at the end of each session so the next session
can pick up from a cold start (after Claude Code context compaction).

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
