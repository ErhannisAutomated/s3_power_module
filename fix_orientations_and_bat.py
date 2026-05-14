"""Address user's observations after the pad-rotation fix:

  1. Strip all existing tracks/vias (routes were computed against the
     pre-fix pad shapes; they'll be wrong relative to the now-correctly
     oriented pads).
  2. Rotate J1 by 180° so its pins face inward (USB-C receptacle opening
     to the board edge).
  3. Rotate J2 and J3 by 90° so the pin rows run along X — currently
     vertical pin headers at (x, 103) extended past the y=110 board edge.
  4. Flip BAT1 to the back layer and mark do-not-populate; user has a
     physical part already.
  5. Refill zones.
"""
import pcbnew

PCB = "/home/vagrant/projects/kicad_agent/projects/power_module/power_module.kicad_pcb"
b = pcbnew.LoadBoard(PCB)

# 1) strip tracks/vias
tracks = list(b.GetTracks())
for t in tracks:
    b.Remove(t)
print(f"removed {len(tracks)} track/via items")

# 2-4) orientation + BAT1 fixes
fixed = {}
for fp in b.GetFootprints():
    ref = fp.GetReference()
    if ref == "J1":
        old = fp.GetOrientation().AsDegrees()
        fp.SetOrientationDegrees(old + 180)  # was -90 -> now 90
        fixed[ref] = ("rotate +180°", old, fp.GetOrientation().AsDegrees())
    elif ref in ("J2", "J3"):
        old = fp.GetOrientation().AsDegrees()
        fp.SetOrientationDegrees(old + 90)
        fixed[ref] = ("rotate +90°", old, fp.GetOrientation().AsDegrees())
    elif ref == "BAT1":
        # Flip to back layer, around its own centre.
        fp.Flip(fp.GetPosition(), False)
        # Mark do-not-populate so JLCPCB skips it.
        try:
            fp.SetDNP(True)
        except AttributeError:
            # Older API: set via attributes / properties
            attr_dnp = getattr(pcbnew, "FP_DNP", None)
            if attr_dnp is not None:
                fp.SetAttributes(fp.GetAttributes() | attr_dnp)
        fixed[ref] = ("flip to B.Cu + DNP", None, None)

for ref, info in fixed.items():
    if info[1] is not None:
        print(f"  {ref}: {info[0]}  ({info[1]:+.1f}° -> {info[2]:+.1f}°)")
    else:
        print(f"  {ref}: {info[0]}")

# 5) refill zones
filler = pcbnew.ZONE_FILLER(b)
filler.Fill(b.Zones())
print(f"refilled {len(list(b.Zones()))} zones")

b.Save(PCB)
print(f"\nsaved {PCB}")
