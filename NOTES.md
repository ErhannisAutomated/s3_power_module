# Power module — session resume notes

Living document; updated at the end of each session so the next session
can pick up from a cold start (after Claude Code context compaction).

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
