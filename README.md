# Emergency Evacuation Planning System (Python AI Project)

A desktop demonstration that models an illustrative campus/building as a graph and compares **BFS**, **A2**, and a separate **utility-based route agent**. The interface uses Tkinter and the model uses only Python's standard library.

> **Safety note:** This is an academic simulation. It does not connect to real fire/flood sensors, estimate real-world smoke or water movement, or validate real emergency routes. In an actual emergency, follow official alarms, wardens, emergency services, and approved evacuation plans.

## Features included

- Graph of rooms, corridors, exits, a West Passage bypass, stairwells, an atrium, and a restricted maintenance zone.
- BFS finds a route with the fewest connections and avoids all marked hazards.
- A* minimizes a weighted cost for distance, risk, crowd load, and accessibility preference.
- Utility agent enumerates viable simple routes and scores the distance/risk/crowd/accessibility trade-off.
- Severe hazards (70% or higher) are treated as impassable for all algorithms; smaller hazards add cost to A* and utility routing.
- Six named scenarios: Normal operations, Fire in north wing, Flooded south corridor, Smoke in central hall, South exit blocked, and Multiple failures.
- Room 101 has a West Passage alternative around Corridor A; the Library has a southern West Passage alternative around Corridor B.
- Four default evacuation groups, including a group that requires an accessible route. Groups can be edited, added, and removed.
- Slider controls for distance, safety, crowd, and accessibility weights.
- Click map nodes to select/block or toggle hazards. Click an edge line and use the connection button to block/reopen an ordinary connection.
- Route overlays, route metrics, group-specific instructions, dynamic route recalculation, and a no-safe-route message when no valid path exists.
- Automated tests for all three algorithms, every preset/group combination, hazards, accessibility, blocked edges, closed exits, reset behavior, and the original Room 101 dead-end issue.

## Files

- `main.py` — Tkinter GUI.
- `evacuation_engine.py` — graph model and algorithms.
- `test_evacuation.py` — automated route tests.
- `PROJECT_REPORT.md` — project write-up for review/submission.
- `requirements.txt` — notes that no third-party packages are needed.
- `run_windows.bat` — launches the GUI on Windows if Python's `py` launcher is installed.

## Run on Windows

1. Install Python 3.10 or newer. Tkinter must be included with the Python installation.
2. Extract this folder.
3. Open this folder in VS Code (or open Command Prompt in this folder).
4. Run:

```bash
python main.py
```

If `python` is not recognized, try:

```bash
py main.py
```

You can also double-click `run_windows.bat`.

## Run automated tests

From the project folder, run:

```bash
python -m unittest -v
```

Or use `py -m unittest -v` on Windows. The GUI does not need to be open for these tests.

## Suggested demo flow

1. Start with `Normal operations`; compare BFS, A*, and the utility agent.
2. Choose `Fire in north wing`. Select Room 101 and verify that the route uses the West Passage instead of Corridor A.
3. Choose `Flooded south corridor`. Verify that the Library can use the alternate passage and does not route through the flooded Corridor B.
4. Select `Utility agent — balanced` and adjust the safety or crowd weight to observe a changed preference where a viable alternative exists.
5. Select the `Care Unit` group and confirm it avoids the stairwell and North Exit.
6. Click a connection line, use `Toggle selected connection`, and calculate again. Try `Reset hazards` to return to normal conditions.
7. Block every exit to demonstrate that the application reports no safe route rather than inventing one.

## Model assumptions

- Graph distances use abstract route units, not calibrated metres.
- A node or edge hazard at 0.70 or above is considered impassable. BFS avoids any non-zero hazard; A* and utility search may use lower-level hazards with a risk penalty.
- Accessibility is a hard restriction for groups marked `Requires accessible route`; otherwise it remains a weighted preference.
- Multi-group routing plans larger groups first and estimates congestion from earlier planned routes. This is a simple planning approximation, not a time-based crowd simulation.
- The utility agent evaluates up to 5,000 simple paths; the included graph is small enough for this approach.
