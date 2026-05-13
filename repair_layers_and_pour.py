"""Repair power_module.kicad_pcb layer-name corruption + add In2.Cu BAT+ pour.

Background: the previous add_layer call (before the MCP fix) renamed
layer id=5 (F.Silkscreen) to "In2.Cu" because of the bad In1_Cu+(n-1)
formula.  Layer id=6 also became "In2.Cu" after save_project
normalisation.  This script:
  1. Restores layer 5's name to "F.Silkscreen" so GetLayerID("In2.Cu")
     unambiguously returns 6 (the real In2.Cu).
  2. Adds a BAT+ copper pour on In2.Cu, mirroring the existing GND pour
     on In1.Cu, so the 4-layer stack becomes a real GND/PWR sandwich
     between the two signal layers.
  3. Refills all zones and saves.
"""
import pcbnew

PCB = "/home/vagrant/projects/kicad_agent/projects/power_module/power_module.kicad_pcb"

board = pcbnew.LoadBoard(PCB)

# Step 1: undo the layer-5 rename.
if board.GetLayerName(5) == "In2.Cu":
    board.SetLayerName(5, "F.Silkscreen")
    print(f"  fixed layer 5 name: 'In2.Cu' -> 'F.Silkscreen'")
else:
    print(f"  layer 5 already named {board.GetLayerName(5)!r}")

# Sanity: In2.Cu now unique.
in2 = board.GetLayerID("In2.Cu")
print(f"  GetLayerID('In2.Cu') = {in2}  (expect 6)")
assert in2 == pcbnew.In2_Cu == 6, f"In2.Cu didn't resolve correctly: {in2}"

# Step 2: find BAT+ net.
nets = board.GetNetInfo().NetsByName()
assert nets.has_key("BAT+"), "BAT+ net not found on board"
bat_net = nets["BAT+"]
print(f"  BAT+ netcode = {bat_net.GetNetCode()}")

# Mirror the In1.Cu GND pour geometry (use board outline minus corner radius).
bbox = board.GetBoardEdgesBoundingBox()
scale = 1_000_000  # nm
x1 = bbox.GetX() / scale
y1 = bbox.GetY() / scale
x2 = (bbox.GetX() + bbox.GetWidth()) / scale
y2 = (bbox.GetY() + bbox.GetHeight()) / scale

# Detect corner radius from Edge.Cuts arcs
edge_layer = board.GetLayerID("Edge.Cuts")
corner_radius = 0.0
for item in board.GetDrawings():
    if item.GetLayer() == edge_layer and item.GetClass() == "PCB_ARC":
        r = item.GetRadius() / scale
        if r > corner_radius:
            corner_radius = r
inset = corner_radius
print(f"  board bbox: ({x1:.1f}, {y1:.1f}) -> ({x2:.1f}, {y2:.1f}); corner_radius={corner_radius:.2f}")

# Step 3: drop any stale BAT+ zone we may have added earlier, then add a new one.
to_remove = []
for z in board.Zones():
    if z.GetLayer() == pcbnew.In2_Cu:
        to_remove.append(z)
for z in to_remove:
    board.Remove(z)
    print(f"  removed stale zone on In2.Cu (net={z.GetNet().GetNetname() if z.GetNet() else 'none'})")

zone = pcbnew.ZONE(board)
zone.SetLayer(pcbnew.In2_Cu)
zone.SetNet(bat_net)
zone.SetAssignedPriority(0)
zone.SetLocalClearance(int(0.25 * scale))
zone.SetMinThickness(int(0.2 * scale))
zone.SetFillMode(pcbnew.ZONE_FILL_MODE_POLYGONS)

outline = zone.Outline()
outline.NewOutline()
for px, py in [(x1+inset, y1+inset), (x2-inset, y1+inset),
               (x2-inset, y2-inset), (x1+inset, y2-inset)]:
    outline.Append(pcbnew.VECTOR2I(int(px * scale), int(py * scale)))

board.Add(zone)
print(f"  added In2.Cu BAT+ pour (priority 0, clearance 0.25mm)")

# Step 4: refill all zones.
filler = pcbnew.ZONE_FILLER(board)
filler.Fill(board.Zones())
print(f"  refilled {len(list(board.Zones()))} zones")

# Step 5: save.
board.Save(PCB)
print(f"  saved {PCB}")

# Verify.
b2 = pcbnew.LoadBoard(PCB)
print()
print("Verification after save:")
print(f"  layer 5 name: {b2.GetLayerName(5)!r}")
print(f"  layer 6 name: {b2.GetLayerName(6)!r}")
print(f"  zones:")
for z in b2.Zones():
    print(f"    layer {z.GetLayer()} ({b2.GetLayerName(z.GetLayer())}) net={z.GetNet().GetNetname()}")
