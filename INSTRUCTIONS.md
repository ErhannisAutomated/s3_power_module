# Power Module — design instructions

Original prompt verbatim (given to flux.ai 2026-05). Context: the user
had previously hand-built a 12 V Li-ion power module that "won't
charge and shorting the output leads to the control transistor
catching fire" — that's the flawed *original* user design, not a
flux.ai output. Flux.ai was asked to design a replacement; it
consumed compute aggressively without reaching PCB layout, and had
no clean KiCad export path, so flux's design quality is unknown.
That dead-end kicked off the move to a self-hosted MCP/KiCad workflow.

> Hello! I tried to build a 12V liion power module, and while it
> TECHNICALLY performs its most basic function, it won't charge and
> shorting the output leads to the control transistor catching fire.
> Which is not great, haha. Would you be willing to design me a better
> one? Here's the specs:
>
> 1. 1P 3S, 18650 lithium ion cells (which can be swapped in/out of a
>    bracket rather than soldered in place).
> 2. It's meant to be a module to be copied into other boards, so the
>    output is just two pins, regulated +12V and GND, capable of at
>    least 2A sustained, ideally 4A+ if feasible.
> 3. Physical off-switch; I'm undecided whether it directly interrupts
>    power or just signals the transistor to cut power.
> 4. Standard protections: over-charging, under-voltage, short-circuit,
>    thermal shutdown, anything else that seems reasonable.
> 5. USB-C PD charging.
> 6. Might be nice if there were some SPI or I2C lines available with
>    voltage or other stats, but it's optional.
> 7. Bonus points if you can hot-swap individual cells without the
>    system losing power, but I doubt most chips support that use case,
>    and I don't want to triple the complexity of the design, haha.
> Anything I've missed? Does that make sense?

## Confirmed parts / preferences from later discussion

- **Cell holder:** JLCPCB `C19184086` (triple-cell 18650 holder; more
  compact than three single holders flux.ai used).
- The earlier flux.ai attempt used three separate holders — avoid that.

## Open decisions to confirm before schematic work

1. **Output topology.** A 3S pack is 9 V (cutoff) – 12.6 V (full
   charge), so the requested "regulated 12 V output" needs either:
   - A **buck-boost** converter (true 12 V across full battery range,
     more complex), or
   - A **boost-only** converter (fails near full charge when battery
     ≥ 12 V), or
   - **No output regulator** (output = battery voltage, varies
     9 V–12.6 V — call it "nominal 12 V"; downstream uses tolerate it).
   - A **buck** to 12 V from a higher-voltage rail (rules out 3S; would
     need 4S — but spec is 3S).
   Recommend buck-boost for "real 12 V"; or accept unregulated and
   simplify a lot. Need to choose.

2. **Off-switch behaviour.** Direct power interrupt (SPST in the high
   current path) is simplest mechanically but the switch itself must
   handle 4 A+. Signal-to-MOSFET (SPST signals an enable pin) is
   electrically cleaner and the switch is cheap, but it adds a
   permanently-on quiescent path through the gate-drive logic. Need
   to choose.

3. **Telemetry.** The BMS chip we pick (e.g. BQ76920) typically has
   I²C built in — comes "free". Spec says optional; default is
   yes/include unless it pushes part count significantly.

4. **Hot-swap individual cells.** Spec says nice-to-have; deferred
   unless an obvious cheap path appears.

5. **Form factor.** Module-style, so output is 2 pins (12 V / GND).
   Mechanical questions: triple cell holder dictates a footprint of
   roughly 78 × 22 mm just for the cells. Total board could be
   ~80 × 50 mm with charger + BMS + regulator alongside. Need to
   confirm size constraint or none.

6. **Assembly:** JLC SMT assembly preferred (per general project
   feedback). Implies all SMT, footprint constraints (no exotic
   packages), prefer JLC Basic where reasonable.

## Design summary (to be filled in once decisions are made)

- Charger IC:
- BMS IC:
- Output regulator:
- USB-C PD sink controller:
- Cell holder: `C19184086`
- Off-switch: TBD
- Telemetry interface: TBD (likely I²C on the BMS bus)
