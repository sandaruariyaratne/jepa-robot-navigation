"""Quick look at the environment: `python -m environment [--png DIR]`."""

from __future__ import annotations

import argparse
from pathlib import Path

from . import ACTION_NAMES, REFERENCE_START, GridWorld, distances_to_goal, save_png, shortest_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--png", type=Path, help="also save the reference start and goal frames here")
    args = parser.parse_args()

    env = GridWorld(terminate_on_goal=True)
    obs = env.reset(start=REFERENCE_START)
    print(f"Observation: {obs.dtype} {list(obs.shape)}, free cells: {len(env.map.free_cells())}")
    print("\nMap (R robot, G goal, # wall):")
    print(env.render_ascii())

    dist = distances_to_goal(env.map)
    print("\nShortest-path distance to goal (# = wall):")
    for row in dist:
        print(" ".join(" #" if d < 0 else f"{d:2d}" for d in row))

    path = shortest_path(env.map, REFERENCE_START)
    print(f"\nOptimal path from {REFERENCE_START}: {len(path)} steps")
    print(" ".join(ACTION_NAMES[a] for a in path))
    for a in path:
        result = env.step(a)
    print(f"Reached goal: {result.at_goal}, terminated: {result.terminated}, steps: {env.steps}")

    if args.png:
        args.png.mkdir(parents=True, exist_ok=True)
        save_png(env.render(REFERENCE_START), args.png / "start.png", scale=8)
        save_png(env.goal_obs(), args.png / "goal.png", scale=8)
        print(f"Saved start.png and goal.png to {args.png}")


if __name__ == "__main__":
    main()
