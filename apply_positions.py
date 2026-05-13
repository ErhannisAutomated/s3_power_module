#!/usr/bin/env python3
"""Apply component positions to a .kicad_pcb directly.

Workaround for an MCP server bug where move_component operated on a
different in-memory BOARD than save_project wrote to disk.
"""
import re
import sys
from pathlib import Path

POSITIONS = {
    "U4": (78, 80, 90),     "SW1": (78, 103, 0),    "J3": (17, 103, 0),
    "J2": (47, 103, 0),     "J1": (88, 55, 270),    "R16": (52, 55, 90),
    "C17": (60, 55, 90),    "C16": (51, 80, 90),    "C15": (55, 80, 90),
    "C14": (51, 65, 90),    "C13": (32, 65, 90),    "C12": (41, 65, 90),
    "C11": (36, 80, 90),    "C10": (32, 80, 90),    "R15": (48, 55, 90),
    "D1":  (60, 50, 0),     "R14": (44, 55, 90),    "R13": (40, 55, 90),
    "R12": (36, 55, 90),    "R11": (32, 55, 90),    "R10": (43, 75, 90),
    "L1":  (38, 70, 0),     "Q2":  (55, 70, 90),    "U3":  (47, 70, 0),
    "U2":  (78, 50, 0),     "C20": (70, 60, 90),    "R26": (92, 80, 90),
    "C21": (66, 60, 90),    "C31": (84, 60, 90),    "R25": (82, 55, 90),
    "C22": (74, 60, 90),    "R22": (66, 55, 90),    "R21": (62, 55, 90),
    "C26": (70, 90, 90),    "C25": (62, 85, 90),    "R27": (92, 95, 90),
    "D2":  (88, 95, 0),     "C30": (76, 95, 90),    "C29": (80, 92, 90),
    "R20": (73, 88, 90),    "R24": (74, 55, 90),    "R23": (70, 55, 90),
    "C28": (84, 92, 90),    "C27": (65, 90, 90),    "C24": (62, 80, 90),
    "C23": (62, 75, 90),    "L2":  (65, 80, 0),     "Q4":  (88, 85, 90),
    "Q3":  (88, 75, 90),    "BAT1": (47.5, 23, 0),  "TH1": (25, 62, 90),
    "R9":  (21, 55, 90),    "R8":  (13, 55, 90),    "R7":  (9, 55, 90),
    "R6":  (5, 55, 90),     "C9":  (25, 80, 90),    "C8":  (9, 70, 90),
    "C7":  (5, 70, 90),     "C6":  (9, 65, 90),     "C5":  (5, 65, 90),
    "R5":  (12, 80, 90),    "Q1":  (17, 80, 90),    "C4":  (53, 51, 90),
    "C3":  (48, 51, 90),    "C2":  (43, 51, 90),    "C1":  (38, 51, 90),
    "R4":  (53, 47, 90),    "R3":  (48, 47, 90),    "R2":  (43, 47, 90),
    "R1":  (38, 47, 90),    "U1":  (17, 62, 0),
}

def rewrite(pcb_text: str) -> tuple[str, list]:
    """Walk each (footprint ...) block; rewrite its (at ...) line if we know
    the reference designator's new position."""
    out, applied = [], []
    pos = 0
    for m in re.finditer(r'^\t\(footprint ', pcb_text, flags=re.MULTILINE):
        out.append(pcb_text[pos:m.start()])
        after = pcb_text[m.start():]
        nxt = re.search(r'^\t\(footprint |^\t\(embedded_fonts ', after[1:], flags=re.MULTILINE)
        # original_len: where this block ends IN THE SOURCE TEXT (used to
        # advance pos).  Don't reuse the post-subn block length below — a
        # shorter (at X Y) replacement would leave pos lagging and cause
        # the next iteration to re-emit the tail of this footprint, injecting
        # stray ')' characters into the file.
        original_len = len(after) if not nxt else nxt.start() + 1
        block = after[:original_len]
        ref_m = re.search(r'\(property "Reference" "([^"]+)"', block)
        if ref_m and ref_m.group(1) in POSITIONS:
            ref = ref_m.group(1)
            x, y, rot = POSITIONS[ref]
            at_re = re.compile(r'\t\t\(at [-\d.]+ [-\d.]+(?: [-\d.]+)?\)')
            new_at = f'\t\t(at {x} {y} {rot})' if rot else f'\t\t(at {x} {y})'
            block, n = at_re.subn(new_at, block, count=1)
            if n:
                applied.append(ref)
        out.append(block)
        pos = m.start() + original_len
    out.append(pcb_text[pos:])
    return "".join(out), applied


if __name__ == "__main__":
    path = Path(sys.argv[1] if len(sys.argv) > 1 else
                "/home/vagrant/projects/kicad_agent/projects/power_module/power_module.kicad_pcb")
    text = path.read_text()
    new_text, applied = rewrite(text)
    path.write_text(new_text)
    print(f"Applied {len(applied)}/{len(POSITIONS)} positions")
    missing = [r for r in POSITIONS if r not in applied]
    if missing:
        print(f"  not found in file: {missing}")
