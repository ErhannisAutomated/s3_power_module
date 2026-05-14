"""Repair stale pad rotations after the apply_positions.py incident.

Background: yesterday's `apply_positions.py` recovered footprint
positions by directly rewriting the `(at X Y rot)` line of each
footprint in `power_module.kicad_pcb`.  It did NOT update the per-pad
local rotation fields.  KiCad's renderer + pcbnew API combine
footprint_rot for the pad's WORLD POSITION but use only the pad's
LOCAL rotation for the pad SHAPE orientation.  Net result: every pad
on every rotated footprint is drawn at the right CENTER but with the
WRONG ORIENTATION — long axis points the wrong way, pads overlap each
other.

This script fixes it by setting each pad's local rotation equal to the
footprint's rotation, which is the right answer when the library
footprint had no per-pad rotations (which is the case for every
broken footprint in this file — verified by audit).
"""
import pcbnew

PCB = "/home/vagrant/projects/kicad_agent/projects/power_module/power_module.kicad_pcb"
b = pcbnew.LoadBoard(PCB)

n_repaired = 0
n_skipped_zero = 0

for fp in b.GetFootprints():
    fp_rot = fp.GetOrientation().AsDegrees()
    if abs(fp_rot) < 0.5:
        n_skipped_zero += 1
        continue

    # Check whether at least one non-circular pad currently has rotation ~0,
    # which is the diagnostic for the bug.
    sample_pad = None
    for p in fp.Pads():
        sz = p.GetSize()
        if abs(sz.x - sz.y) > 0.05:
            sample_pad = p
            break
    if sample_pad is None:
        # All round pads; can't detect, but apply anyway (rotation is benign
        # on round pads).
        already_correct = False
    else:
        sample_rot = sample_pad.GetOrientation().AsDegrees()
        # Already-correct state: pad_rot == fp_rot (modulo full turns).
        already_correct = abs(((sample_rot - fp_rot) % 360)) < 0.5

    if already_correct:
        continue

    # Apply: set every pad's local rotation to the footprint's rotation.
    for p in fp.Pads():
        p.SetOrientationDegrees(fp_rot)
    n_repaired += 1
    print(f"  fixed {fp.GetReference():6s} (fp_rot={fp_rot:+.1f}°, "
          f"{len(list(fp.Pads()))} pads)")

# Refill zones so pad changes propagate into pour cutouts.
filler = pcbnew.ZONE_FILLER(b)
filler.Fill(b.Zones())

b.Save(PCB)
print()
print(f"Repaired {n_repaired} footprints (skipped {n_skipped_zero} "
      f"with zero rotation, plus already-correct).")
