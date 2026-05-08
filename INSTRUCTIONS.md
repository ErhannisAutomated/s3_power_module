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

## Decisions made (2026-05-08)

1. **Output topology:** 4-switch buck-boost regulator, ~4 A, true
   regulated 12 V output across the full 9–12.6 V battery range.
2. **Off-switch placement:** Single pair of CHG/DSG protection
   N-channel MOSFETs in series with battery negative (low side).
   These are driven by the BMS IC's gate-drive pins for fault
   protection (over-current, short-circuit, over-charge,
   deep-discharge). User on/off switch toggles the BMS IC's
   shutdown / wake pin — opening the DSG FET turns the whole module
   off via the same FETs. No separate output MOSFET.
   - Rationale: protection FETs at battery negative is the standard
     BMS architecture (matches datasheet). Reusing them for the user
     switch avoids a redundant high-side FET on the output, drops
     quiescent in OFF state to BMS sleep current (tens of µA), and
     keeps current paths short.
3. **Telemetry:** I²C breakout from BMS to a 4-pin header
   (SCL/SDA/GND/3V3) — standard pinout for connecting to a host MCU
   when the module is plugged into a larger board.

## Open decisions to confirm before schematic work

4. **Hot-swap individual cells.** Spec says nice-to-have; deferred
   unless an obvious cheap path appears.

5. **Form factor.** Module-style, so output is 2 pins (12 V / GND).
   Triple cell holder is roughly 78 × 22 mm just for the cells. Total
   board likely ~80 × 50 mm with charger + BMS + buck-boost alongside.
   Confirm size constraint or proceed open-ended.

6. **Assembly:** JLC SMT assembly preferred (per general project
   feedback). Implies all SMT, footprint constraints (no exotic
   packages), prefer JLC Basic where reasonable.

## Design summary

| Function                  | Part           | LCSC        | Stock    | Notes                               |
| ------------------------- | -------------- | ----------- | -------- | ----------------------------------- |
| USB-C PD sink controller  | CH224K         | `C970725`   | 1,996    | ESSOP-10, requests up to 20 V       |
| 3S Li-ion charger         | BQ25700A       | `C965493`   | 3,224    | QFN-32, 3.5–24 V in, 4 A, SMBus     |
| BMS / cell-monitor        | BQ7692003PWR   | `C601650`   | 2,730    | TSSOP-20, 3-5S, I²C, balancing      |
| 4-switch buck-boost       | LM5176PWPR     | `C442493`   | 5,497    | HTSSOP-28, 4.2-55 V, controller     |
| Protection / power FETs   | (TBD dual N)   | `C353066`   | 81,644   | SOP-8 dual-N, 30 V / 8 A / 26 mΩ    |
| Cell holder (3 × 18650)   |                | `C19184086` | 2,977    | BH-18650-B5BA016                    |
| Off-switch                | (small SMD)    | TBD         |          | Signal-only → BMS shutdown pin      |

**Dual N-MOSFET note:** `C353066` (30 V Vds, 8 A, 26 mΩ@10 V, 1.5 V
Vgs(th)) used for both the BMS protection FETs and the LM5176's four
power FETs. 30 V Vds is OK with margin for 12.6 V battery + 20 V PD
input. Logic-level Vgs(th) matches BQ76920's gate-drive output.
