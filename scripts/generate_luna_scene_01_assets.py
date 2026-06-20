#!/usr/bin/env python3
"""Generate the reproducible terrain and obstacle layout for lunar scene 01."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import argparse
import json
import math
import re
from pathlib import Path
import random


@dataclass(frozen=True)
class CraterFeature:
    name: str
    x_m: float
    y_m: float
    radius_m: float
    rim_width_m: float
    rim_height_m: float
    basin_depth_m: float


@dataclass(frozen=True)
class Rock:
    asset: str
    x_m: float
    y_m: float
    yaw_rad: float
    scale_x: float
    scale_y: float
    scale_z: float
    zone: str


WORLD_SIZE_M = 24.0
GRID_STEPS = 129
TERRAIN_NAME = "lunar_scene_01_terrain"
WORLD_PATH = Path("ros2_ws/src/rover_gazebo/worlds/competition_luna_scene_01.sdf")
ASSET_ROOT = Path("ros2_ws/src/rover_gazebo/assets/luna/rock")
GENERATED_BEGIN = "    <!-- BEGIN GENERATED ROCK MODELS: run scripts/generate_luna_scene_01_assets.py -->"
GENERATED_END = "    <!-- END GENERATED ROCK MODELS -->"
DEFAULT_CRATER_RIM_HEIGHT_SCALE = 4.0
DEFAULT_GROUND_COLLISION_Z = -0.04
DEFAULT_GROUND_VISUAL_OFFSET = 0.0
BORDER_WALL_OVERLAP_M = 0.5
BORDER_WALL_LENGTH_M = WORLD_SIZE_M + 2.0 * BORDER_WALL_OVERLAP_M
BORDER_WALL_THICKNESS_M = 0.28
BORDER_WALL_HEIGHT_M = 0.95
ASSET_SPECS = {
    "apollo": {
        "filename": "apollo_sample20.glb",
        "bbox_path": ASSET_ROOT / "apollo_sample20.bbox.json",
    },
    "boulder": {
        "filename": "lunalab_boulder1.glb",
        "bbox_path": ASSET_ROOT / "lunalab_boulder1.bbox.json",
    },
}

# Broad, shallow features: visual terrain texture, never invisible barriers.
CRATERS: list[CraterFeature] = [
    CraterFeature("northwest_large", -7.4, 6.5, 1.85, 0.50, 0.075, 0.055),
    CraterFeature("north_mid", -1.9, 8.3, 1.15, 0.36, 0.060, 0.045),
    CraterFeature("northeast_pair_a", 5.4, 7.1, 1.45, 0.42, 0.070, 0.050),
    CraterFeature("northeast_pair_b", 8.4, 5.0, 0.78, 0.28, 0.048, 0.035),
    CraterFeature("west_shallow", -8.7, 1.5, 1.05, 0.34, 0.052, 0.040),
    CraterFeature("east_large", 8.0, 0.8, 1.95, 0.52, 0.080, 0.060),
    CraterFeature("southwest_pair_a", -7.2, -5.8, 1.55, 0.44, 0.072, 0.052),
    CraterFeature("southwest_pair_b", -4.5, -8.2, 0.72, 0.27, 0.045, 0.032),
    CraterFeature("south_mid", 0.7, -7.4, 1.22, 0.38, 0.060, 0.046),
    CraterFeature("southeast_large", 6.5, -6.2, 1.72, 0.46, 0.078, 0.055),
    CraterFeature("southeast_small", 9.2, -3.5, 0.62, 0.24, 0.042, 0.030),
    CraterFeature("west_micro", -3.8, 3.5, 0.58, 0.22, 0.038, 0.026),
    CraterFeature("east_micro", 3.7, 3.0, 0.66, 0.24, 0.040, 0.028),
    CraterFeature("southern_micro", -2.9, -3.9, 0.54, 0.21, 0.036, 0.025),
]

def asset_uri(scene_id: str, asset: str) -> str:
    return f"file:///tmp/thirover_scene_{scene_id}_assets/object/rock/{ASSET_SPECS[asset]['filename']}"


def _load_asset_dims() -> dict[str, tuple[float, float, float]]:
    dims: dict[str, tuple[float, float, float]] = {}
    for name, spec in ASSET_SPECS.items():
        data = json.loads(spec["bbox_path"].read_text(encoding="utf-8"))
        raw_dims = data["normalized_bounds"]["dimensions"]
        dims[name] = (float(raw_dims[0]), float(raw_dims[1]), float(raw_dims[2]))
    return dims


def crater_height(x: float, y: float, crater_rim_height_scale: float) -> float:
    """Return gentle visual relief relative to the nominal z=0 plane."""
    height = 0.006 * math.sin(0.31 * x + 0.4) * math.cos(0.27 * y - 0.3)
    height += 0.004 * math.sin(0.63 * x + 0.41 * y)
    for crater in CRATERS:
        radius = math.hypot(x - crater.x_m, y - crater.y_m)
        rim_sigma = max(0.10, crater.rim_width_m * 0.48)
        basin_sigma = max(0.18, crater.radius_m * 0.52)
        # Boost the rim height so the lidar can pick it up cleanly.
        rim = (crater.rim_height_m * crater_rim_height_scale) * math.exp(
            -((radius - crater.radius_m) / rim_sigma) ** 2
        )
        basin = crater.basin_depth_m * math.exp(-(radius / basin_sigma) ** 2)
        height += rim - basin
    return height


def generate_height_field(crater_rim_height_scale: float) -> tuple[list[list[float]], float, float, float]:
    half = WORLD_SIZE_M / 2.0
    spacing = WORLD_SIZE_M / (GRID_STEPS - 1)
    raw = [
        [
            crater_height(-half + col * spacing, -half + row * spacing, crater_rim_height_scale)
            for col in range(GRID_STEPS)
        ]
        for row in range(GRID_STEPS)
    ]
    raw_min = min(map(min, raw))
    raw_max = max(map(max, raw))
    normalized = [[height - raw_min for height in row] for row in raw]
    # This offset places the visible surface at the rover spawn exactly on z=0.
    visual_offset = -(crater_height(0.0, 0.0, crater_rim_height_scale) - raw_min)
    return normalized, 0.0, raw_max - raw_min, visual_offset


def _normal(x: float, y: float, z: float) -> tuple[float, float, float]:
    length = math.sqrt(x * x + y * y + z * z)
    return (x / length, y / length, z / length) if length else (0.0, 0.0, 1.0)


def generate_rocks(crater_rim_height_scale: float) -> list[Rock]:
    """Build 48 deterministic rocks in arcs, clusters, and sparse fields."""
    rng = random.Random(4107)
    rocks: list[Rock] = []

    def apollo(x: float, y: float, zone: str, lo: float = 15.0, hi: float = 25.0) -> None:
        scale = rng.uniform(lo, hi)
        rocks.append(Rock("apollo", x, y, rng.uniform(-math.pi, math.pi), scale,
                          scale * rng.uniform(0.84, 1.16), scale * rng.uniform(0.88, 1.18), zone))

    def boulder(x: float, y: float, zone: str, lo: float = 1.25, hi: float = 2.15) -> None:
        scale = rng.uniform(lo, hi)
        rocks.append(Rock("boulder", x, y, rng.uniform(-math.pi, math.pi), scale,
                          scale * rng.uniform(0.88, 1.12), scale * rng.uniform(0.82, 1.12), zone))

    crater_by_name = {crater.name: crater for crater in CRATERS}
    arcs = [
        ("northwest_large", [0.05, 0.55, 1.05, 1.55, 2.08]),
        ("northeast_pair_a", [-0.45, 0.05, 0.52, 1.02, 1.48]),
        ("southwest_pair_a", [1.70, 2.17, 2.68, 3.18, 3.68]),
        ("southeast_large", [-2.75, -2.25, -1.75, -1.25, -0.72]),
    ]
    for crater_name, angles in arcs:
        crater = crater_by_name[crater_name]
        for angle in angles:
            radius = crater.radius_m + rng.uniform(-0.13, 0.15)
            apollo(crater.x_m + radius * math.cos(angle),
                   crater.y_m + radius * math.sin(angle), f"{crater_name}_partial_arc", 17.0, 28.0)

    # Irregular dense pockets leave the central east-west corridor open.
    for zone, cx, cy, count, spread in [
        ("west_cluster", -8.8, -0.9, 4, 1.05),
        ("north_cluster", 0.6, 7.1, 4, 1.20),
        ("east_cluster", 8.6, 3.0, 3, 0.95),
        ("south_cluster", -1.2, -8.8, 3, 1.10),
    ]:
        for _ in range(count):
            angle = rng.uniform(-math.pi, math.pi)
            radius = spread * math.sqrt(rng.random())
            apollo(cx + radius * math.cos(angle), cy + radius * math.sin(angle), zone, 14.0, 24.0)

    for x, y in [(-9.8, 8.8), (-5.2, 9.0), (2.8, 9.4), (9.7, 8.0),
                 (-9.4, -8.7), (-4.7, -5.0), (3.6, -8.8), (9.4, -8.5)]:
        apollo(x, y, "sparse_field", 13.0, 22.0)

    for x, y, zone in [
        (-9.1, 4.2, "west_anchor"), (-5.8, -8.9, "southwest_anchor"),
        (1.8, 6.0, "north_anchor"), (7.5, 7.8, "northeast_anchor"),
        (8.8, -1.8, "east_anchor"), (5.0, -8.5, "southeast_anchor"),
    ]:
        boulder(x, y, zone)

    _ = crater_rim_height_scale

    assert len(rocks) == 48
    assert all(math.hypot(rock.x_m, rock.y_m) >= 3.0 for rock in rocks)
    return rocks


def write_terrain_mesh(output_dir: Path, crater_rim_height_scale: float) -> tuple[dict[str, object], float]:
    heights, min_height, max_height, visual_offset = generate_height_field(crater_rim_height_scale)
    half = WORLD_SIZE_M / 2.0
    spacing = WORLD_SIZE_M / (GRID_STEPS - 1)
    obj_path = output_dir / f"{TERRAIN_NAME}.obj"
    mtl_path = output_dir / f"{TERRAIN_NAME}.mtl"
    lines = [f"mtllib {mtl_path.name}", f"o {TERRAIN_NAME}"]
    for row in range(GRID_STEPS):
        y = -half + row * spacing
        for col in range(GRID_STEPS):
            lines.append(f"v {-half + col * spacing:.6f} {y:.6f} {heights[row][col]:.6f}")
    for row in range(GRID_STEPS):
        for col in range(GRID_STEPS):
            lines.append(f"vt {col/(GRID_STEPS-1):.6f} {row/(GRID_STEPS-1):.6f}")
    for row in range(GRID_STEPS):
        for col in range(GRID_STEPS):
            left = heights[row][max(0, col - 1)]
            right = heights[row][min(GRID_STEPS - 1, col + 1)]
            down = heights[max(0, row - 1)][col]
            up = heights[min(GRID_STEPS - 1, row + 1)][col]
            nx, ny, nz = _normal(-(right-left)/(2*spacing), -(up-down)/(2*spacing), 1.0)
            lines.append(f"vn {nx:.6f} {ny:.6f} {nz:.6f}")
    lines.extend(["usemtl lunar_regolith", "s 1"])
    idx = lambda row, col: row * GRID_STEPS + col + 1
    for row in range(GRID_STEPS - 1):
        for col in range(GRID_STEPS - 1):
            a, b, c, d = idx(row, col), idx(row, col+1), idx(row+1, col), idx(row+1, col+1)
            lines.extend([f"f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}",
                          f"f {b}/{b}/{b} {d}/{d}/{d} {c}/{c}/{c}"])
    obj_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    mtl_path.write_text("newmtl lunar_regolith\nKa 0.34 0.335 0.325\nKd 0.52 0.51 0.49\n"
                        "Ks 0.015 0.015 0.015\nNs 8.0\nd 1.0\nillum 2\n", encoding="utf-8")
    return ({"mesh": obj_path.name, "materials": [mtl_path.name], "grid_steps": GRID_STEPS,
             "world_size_m": WORLD_SIZE_M, "height_min_m": round(min_height + visual_offset, 6),
             "height_max_m": round(max_height + visual_offset, 6),
             "visual_z_offset_m": round(visual_offset, 6),
             "craters": [asdict(crater) for crater in CRATERS]}, visual_offset)


def model_sdf(
    rock: Rock,
    number: int,
    scene_id: str,
    crater_rim_height_scale: float,
    asset_dims: dict[str, tuple[float, float, float]],
) -> str:
    dx, dy, dz = asset_dims[rock.asset]
    sx, sy, sz = rock.scale_x, rock.scale_y, rock.scale_z
    surface_z = max(
        0.0,
        crater_height(rock.x_m, rock.y_m, crater_rim_height_scale)
        - crater_height(0.0, 0.0, crater_rim_height_scale),
    )
    name = f"{rock.asset}_scene_{number:02d}"
    return f'''    <!-- {rock.zone} -->
    <model name="{name}">
      <static>true</static>
      <pose>{rock.x_m:.3f} {rock.y_m:.3f} {surface_z:.4f} 0 0 {rock.yaw_rad:.4f}</pose>
      <link name="link">
        <collision name="collision">
          <pose>0 0 {dz*sz/2:.6f} 0 0 0</pose>
          <geometry><box><size>{dx*sx:.6f} {dy*sy:.6f} {dz*sz:.6f}</size></box></geometry>
        </collision>
        <visual name="visual">
          <geometry><mesh><uri>{asset_uri(scene_id, rock.asset)}</uri><scale>{sx:.4f} {sy:.4f} {sz:.4f}</scale></mesh></geometry>
          <cast_shadows>true</cast_shadows>
        </visual>
      </link>
    </model>'''


def border_wall_sdf(side: str) -> str:
    half = WORLD_SIZE_M / 2.0
    if side in {"west", "east"}:
        x = -half if side == "west" else half
        y = 0.0
        yaw = 0.0
        size_x = BORDER_WALL_THICKNESS_M
        size_y = BORDER_WALL_LENGTH_M
    else:
        x = 0.0
        y = -half if side == "south" else half
        yaw = 1.57079632679
        size_x = BORDER_WALL_THICKNESS_M
        size_y = BORDER_WALL_LENGTH_M
    return f'''    <!-- {side}_border_wall -->
    <model name="{side}_border_wall_scene_01">
      <static>true</static>
      <pose>{x:.3f} {y:.3f} {BORDER_WALL_HEIGHT_M / 2.0:.3f} 0 0 {yaw:.6f}</pose>
      <link name="link">
        <collision name="collision">
          <geometry><box><size>{size_x:.3f} {size_y:.3f} {BORDER_WALL_HEIGHT_M:.3f}</size></box></geometry>
        </collision>
        <visual name="visual">
          <geometry><box><size>{size_x:.3f} {size_y:.3f} {BORDER_WALL_HEIGHT_M:.3f}</size></box></geometry>
          <material><ambient>0.60 0.57 0.50 1</ambient><diffuse>0.60 0.57 0.50 1</diffuse></material>
          <cast_shadows>true</cast_shadows>
        </visual>
      </link>
    </model>'''


def update_world(
    world_path: Path,
    rocks: list[Rock],
    visual_offset: float,
    ground_collision_z: float,
    ground_visual_offset: float,
    crater_rim_height_scale: float,
    asset_dims: dict[str, tuple[float, float, float]],
) -> None:
    text = world_path.read_text(encoding="utf-8")
    text = text.replace("<size>8 8 0.08</size>", f"<size>{WORLD_SIZE_M:g} {WORLD_SIZE_M:g} 0.08</size>", 1)
    ground_block = re.search(r'(<model name="lunar_ground">.*?</model>)', text, flags=re.DOTALL)
    if not ground_block:
        raise ValueError(f"expected lunar_ground model in {world_path}")
    ground_text = ground_block.group(1)

    def replace_pose(block: str, tag: str, pose_value: float) -> str:
        pattern = rf'(<{tag} name="[^"]*">.*?<pose>)([^<]*)(</pose>)'

        def repl(match: re.Match[str]) -> str:
            return f"{match.group(1)}0 0 {pose_value:.6f} 0 0 0{match.group(3)}"

        new_block, count = re.subn(pattern, repl, block, count=1, flags=re.DOTALL)
        if count != 1:
            raise ValueError(f"expected {tag} pose in {world_path}")
        return new_block

    ground_text = replace_pose(ground_text, "collision", ground_collision_z)
    ground_text = replace_pose(ground_text, "visual", visual_offset + ground_visual_offset)
    text = text[: ground_block.start(1)] + ground_text + text[ground_block.end(1) :]

    if GENERATED_BEGIN in text:
        start = text.index(GENERATED_BEGIN)
        end = text.index(GENERATED_END, start) + len(GENERATED_END)
    else:
        start = text.index("    <!-- Upper-left crater:")
        end = text.rindex("\n  </world>")
    models = "\n\n".join(
        model_sdf(rock, i + 1, "01", crater_rim_height_scale, asset_dims)
        for i, rock in enumerate(rocks)
    )
    borders = "\n\n".join(border_wall_sdf(side) for side in ("west", "east", "south", "north"))
    models = f"{models}\n\n{borders}"
    generated = f"{GENERATED_BEGIN}\n{models}\n{GENERATED_END}"
    world_path.write_text(text[:start] + generated + text[end:], encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/competition_luna_scene_01/terrain"))
    parser.add_argument("--world", type=Path, default=WORLD_PATH)
    parser.add_argument("--crater-rim-height-scale", type=float, default=DEFAULT_CRATER_RIM_HEIGHT_SCALE)
    parser.add_argument("--ground-collision-z", type=float, default=DEFAULT_GROUND_COLLISION_Z)
    parser.add_argument("--ground-visual-offset", type=float, default=DEFAULT_GROUND_VISUAL_OFFSET)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary, visual_offset = write_terrain_mesh(args.output_dir, args.crater_rim_height_scale)
    rocks = generate_rocks(args.crater_rim_height_scale)
    asset_dims = _load_asset_dims()
    summary["rocks"] = [asdict(rock) for rock in rocks]
    summary["rock_count"] = len(rocks)
    update_world(
        args.world,
        rocks,
        visual_offset,
        args.ground_collision_z,
        args.ground_visual_offset,
        args.crater_rim_height_scale,
        asset_dims,
    )
    summary_path = args.output_dir / "terrain_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "params: "
        f"world_size_m={WORLD_SIZE_M:g} "
        f"crater_rim_height_scale={args.crater_rim_height_scale:g} "
        f"ground_collision_z={args.ground_collision_z:g} "
        f"ground_visual_offset={args.ground_visual_offset:g} "
        f"border_wall_length_m={BORDER_WALL_LENGTH_M:g} "
        f"border_wall_overlap_m={BORDER_WALL_OVERLAP_M:g}"
    )
    print(f"wrote {args.output_dir / f'{TERRAIN_NAME}.obj'}")
    print(f"wrote {args.output_dir / f'{TERRAIN_NAME}.mtl'}")
    print(f"updated {args.world} with {len(rocks)} rocks")
    print(f"wrote {summary_path}")


if __name__ == "__main__":
    main()
