#!/usr/bin/env python3
"""Generate the reproducible terrain and obstacle layout for lunar scene 02."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import argparse
import csv
import json
import math
import re
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class CsvRow:
    kind: str
    name: str
    x_m: float
    y_m: float
    radius_m: float
    asset: str
    scale: float
    yaw_deg: float


@dataclass(frozen=True)
class TerrainCrater:
    name: str
    x_m: float
    y_m: float
    radius_m: float
    rim_width_m: float
    rim_height_m: float
    basin_depth_m: float


@dataclass(frozen=True)
class RockPlacement:
    kind: str
    name: str
    x_m: float
    y_m: float
    yaw_rad: float
    scale: float
    asset: str


WORLD_SIZE_M = 24.0
GRID_STEPS = 129
SPAWN_CLEAR_RADIUS_M = 1.75
DEFAULT_CRATER_RIM_HEIGHT_SCALE = 4.5
DEFAULT_GROUND_LIFT_M = 0.04
BORDER_WALL_OVERLAP_M = 0.5
BORDER_WALL_LENGTH_M = WORLD_SIZE_M + 2.0 * BORDER_WALL_OVERLAP_M
BORDER_WALL_THICKNESS_M = 0.28
BORDER_WALL_HEIGHT_M = 0.95
CSV_PATH = Path("scripts/world_generation/world02.csv")
WORLD_PATH = Path("ros2_ws/src/rover_gazebo/worlds/competition_luna_scene_02.sdf")
OUTPUT_DIR = Path("outputs/competition_luna_scene_02/terrain")
CSV_CANDIDATES = (
    Path("scripts/world_generation/world.02.csv"),
    Path("scripts/world_generation/world02.csv"),
)

ASSET_SPECS = {
    "apollo_sample20": {
        "bbox_path": Path("ros2_ws/src/rover_gazebo/assets/luna/rock/apollo_sample20.bbox.json"),
    },
    "lunalab_boulder1": {
        "bbox_path": Path("ros2_ws/src/rover_gazebo/assets/luna/rock/lunalab_boulder1.bbox.json"),
    },
}

ASSET_FILENAMES = {
    "apollo_sample20": "apollo_sample20.glb",
    "lunalab_boulder1": "lunalab_boulder1.glb",
}

GENERATED_BEGIN = "    <!-- BEGIN GENERATED ROCK MODELS: run scripts/generate_luna_scene_02_assets.py -->"
GENERATED_END = "    <!-- END GENERATED ROCK MODELS -->"


def _load_bbox_dimensions(path: Path) -> tuple[float, float, float]:
    data = json.loads(path.read_text(encoding="utf-8"))
    dims = data["normalized_bounds"]["dimensions"]
    return float(dims[0]), float(dims[1]), float(dims[2])


def _load_asset_dims() -> dict[str, tuple[float, float, float]]:
    return {name: _load_bbox_dimensions(spec["bbox_path"]) for name, spec in ASSET_SPECS.items()}


def asset_uri(scene_id: str, asset_name: str) -> str:
    return f"file:///tmp/thirover_scene_{scene_id}_assets/object/rock/{ASSET_FILENAMES[asset_name]}"


def _sanitize_identifier(value: str) -> str:
    cleaned = []
    for char in value.strip():
        cleaned.append(char if char.isalnum() or char in {"_", "-"} else "_")
    return "".join(cleaned) or "item"


def resolve_csv_path(path: Path | None = None) -> Path:
    if path is not None:
        return path
    for candidate in CSV_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"could not find any CSV candidate: {', '.join(str(p) for p in CSV_CANDIDATES)}")


def load_world02_csv(path: Path) -> list[CsvRow]:
    raw = path.read_text(encoding="utf-8")
    text = raw.replace("\\n", "\n")
    expected = ["kind", "name", "x_m", "y_m", "radius_m", "asset", "scale", "yaw_deg"]
    reader = csv.DictReader(text.splitlines())
    if reader.fieldnames != expected:
        raise ValueError(f"{path} must have columns {expected}")
    rows = list(reader)
    if not rows:
        raise ValueError(f"{path} is empty")

    parsed: list[CsvRow] = []
    for line_no, row in enumerate(rows, start=2):
        kind = (row.get("kind") or "").strip()
        name = (row.get("name") or "").strip()
        asset = (row.get("asset") or "").strip()
        if not kind or not name:
            raise ValueError(f"{path}:{line_no}: missing kind or name")
        try:
            x_m = float(row["x_m"])
            y_m = float(row["y_m"])
            radius_m = float(row["radius_m"]) if row["radius_m"] else 0.0
            scale = float(row["scale"]) if row["scale"] else 0.0
            yaw_deg = float(row["yaw_deg"]) if row["yaw_deg"] else 0.0
        except ValueError as exc:
            raise ValueError(f"{path}:{line_no}: invalid numeric value") from exc
        parsed.append(CsvRow(kind, name, x_m, y_m, radius_m, asset, scale, yaw_deg))
    return parsed


def validate_csv_rows(
    rows: list[CsvRow],
    crater_rim_height_scale: float,
) -> tuple[list[TerrainCrater], list[RockPlacement]]:
    craters = [row for row in rows if row.kind == "crater"]
    rocks = [row for row in rows if row.kind == "rock"]
    small_rocks = [row for row in rocks if row.asset == "apollo_sample20"]
    large_rocks = [row for row in rocks if row.asset == "lunalab_boulder1"]

    if len(craters) != 20:
        raise ValueError(f"expected 20 crater rows, got {len(craters)}")
    if len(small_rocks) != 10:
        raise ValueError(f"expected 10 small rock rows, got {len(small_rocks)}")
    if len(large_rocks) != 5:
        raise ValueError(f"expected 5 large rock/boulder rows, got {len(large_rocks)}")

    world_half = WORLD_SIZE_M / 2.0
    terrain: list[TerrainCrater] = []
    placements: list[RockPlacement] = []
    seen_names: set[str] = set()
    warnings: list[str] = []

    for row in craters:
        if row.name in seen_names:
            raise ValueError(f"duplicate row name: {row.name}")
        seen_names.add(row.name)
        if abs(row.x_m) + row.radius_m > world_half or abs(row.y_m) + row.radius_m > world_half:
            raise ValueError(f"crater {row.name} exceeds world bounds")
        rim_width = max(0.18, min(0.72, 0.16 * row.radius_m + 0.08))
        rim_height = max(
            0.032,
            min(0.14, (0.014 * row.radius_m + 0.02) * crater_rim_height_scale),
        )
        basin_depth = max(0.018, min(0.07, rim_height * 0.74))
        terrain.append(
            TerrainCrater(
                name=row.name,
                x_m=row.x_m,
                y_m=row.y_m,
                radius_m=row.radius_m,
                rim_width_m=rim_width,
                rim_height_m=rim_height,
                basin_depth_m=basin_depth,
            )
        )
        edge_distance = max(0.0, math.hypot(row.x_m, row.y_m) - row.radius_m)
        if edge_distance < SPAWN_CLEAR_RADIUS_M:
            warnings.append(
                f"spawn warning: crater {row.name} edge is {edge_distance:.2f} m from origin"
            )

    for row in rocks:
        if row.name in seen_names:
            raise ValueError(f"duplicate row name: {row.name}")
        seen_names.add(row.name)
        if row.asset not in ASSET_SPECS:
            raise ValueError(f"unknown asset '{row.asset}' for {row.name}")
        if abs(row.x_m) > world_half or abs(row.y_m) > world_half:
            raise ValueError(f"rock {row.name} exceeds world bounds")
        placements.append(
            RockPlacement(
                kind=row.kind,
                name=row.name,
                x_m=row.x_m,
                y_m=row.y_m,
                yaw_rad=math.radians(row.yaw_deg),
                scale=row.scale,
                asset=row.asset,
            )
        )
        if math.hypot(row.x_m, row.y_m) < SPAWN_CLEAR_RADIUS_M:
            warnings.append(f"spawn warning: rock {row.name} is within {SPAWN_CLEAR_RADIUS_M:.2f} m of origin")

    if warnings:
        for warning in warnings:
            print(warning)
    else:
        print(f"spawn clear: no crater or rock row is within {SPAWN_CLEAR_RADIUS_M:.2f} m of origin")

    return terrain, placements


def crater_height(
    x: float,
    y: float,
    craters: Iterable[TerrainCrater],
    crater_rim_height_scale: float,
) -> float:
    height = 0.005 * math.sin(0.31 * x + 0.4) * math.cos(0.27 * y - 0.3)
    height += 0.0035 * math.sin(0.63 * x + 0.41 * y)
    for crater in craters:
        radius = math.hypot(x - crater.x_m, y - crater.y_m)
        rim_sigma = max(0.10, crater.rim_width_m * 0.48)
        basin_sigma = max(0.18, crater.radius_m * 0.52)
        # Keep the crater rims prominent enough for the lidar to register them.
        rim = crater.rim_height_m * crater_rim_height_scale * math.exp(
            -((radius - crater.radius_m) / rim_sigma) ** 2
        )
        basin = crater.basin_depth_m * math.exp(-(radius / basin_sigma) ** 2)
        height += rim - basin
    return height


def generate_height_field(
    craters: Iterable[TerrainCrater],
    crater_rim_height_scale: float,
) -> tuple[list[list[float]], float, float, float]:
    crater_list = list(craters)
    half = WORLD_SIZE_M / 2.0
    spacing = WORLD_SIZE_M / (GRID_STEPS - 1)
    raw = [
        [
            crater_height(
                -half + col * spacing,
                -half + row * spacing,
                crater_list,
                crater_rim_height_scale,
            )
            for col in range(GRID_STEPS)
        ]
        for row in range(GRID_STEPS)
    ]
    raw_min = min(map(min, raw))
    raw_max = max(map(max, raw))
    normalized = [[height - raw_min for height in row] for row in raw]
    visual_offset = -(crater_height(0.0, 0.0, crater_list, crater_rim_height_scale) - raw_min)
    return normalized, raw_min, raw_max, visual_offset


def _normal(x: float, y: float, z: float) -> tuple[float, float, float]:
    length = math.sqrt(x * x + y * y + z * z)
    return (x / length, y / length, z / length) if length else (0.0, 0.0, 1.0)


def write_terrain_mesh(
    output_dir: Path,
    craters: Iterable[TerrainCrater],
    scene_id: str,
    crater_rim_height_scale: float,
) -> tuple[dict[str, object], float]:
    heights, raw_min, raw_max, visual_offset = generate_height_field(craters, crater_rim_height_scale)
    half = WORLD_SIZE_M / 2.0
    spacing = WORLD_SIZE_M / (GRID_STEPS - 1)
    terrain_name = f"lunar_scene_{scene_id}_terrain"
    obj_path = output_dir / f"{terrain_name}.obj"
    mtl_path = output_dir / f"{terrain_name}.mtl"

    lines = [f"mtllib {mtl_path.name}", f"o {terrain_name}"]
    for row in range(GRID_STEPS):
        y = -half + row * spacing
        for col in range(GRID_STEPS):
            lines.append(f"v {-half + col * spacing:.6f} {y:.6f} {heights[row][col]:.6f}")
    for row in range(GRID_STEPS):
        for col in range(GRID_STEPS):
            lines.append(f"vt {col / (GRID_STEPS - 1):.6f} {row / (GRID_STEPS - 1):.6f}")
    for row in range(GRID_STEPS):
        for col in range(GRID_STEPS):
            left = heights[row][max(0, col - 1)]
            right = heights[row][min(GRID_STEPS - 1, col + 1)]
            down = heights[max(0, row - 1)][col]
            up = heights[min(GRID_STEPS - 1, row + 1)][col]
            nx, ny, nz = _normal(-(right - left) / (2 * spacing), -(up - down) / (2 * spacing), 1.0)
            lines.append(f"vn {nx:.6f} {ny:.6f} {nz:.6f}")
    lines.extend(["usemtl lunar_regolith", "s 1"])
    idx = lambda row, col: row * GRID_STEPS + col + 1
    for row in range(GRID_STEPS - 1):
        for col in range(GRID_STEPS - 1):
            a, b, c, d = idx(row, col), idx(row, col + 1), idx(row + 1, col), idx(row + 1, col + 1)
            lines.extend(
                [
                    f"f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}",
                    f"f {b}/{b}/{b} {d}/{d}/{d} {c}/{c}/{c}",
                ]
            )
    obj_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    mtl_path.write_text(
        "newmtl lunar_regolith\nKa 0.34 0.335 0.325\nKd 0.52 0.51 0.49\n"
        "Ks 0.015 0.015 0.015\nNs 8.0\nd 1.0\nillum 2\n",
        encoding="utf-8",
    )
    summary = {
        "mesh": obj_path.name,
        "materials": [mtl_path.name],
        "grid_steps": GRID_STEPS,
        "world_size_m": WORLD_SIZE_M,
        "height_min_m": round(raw_min + visual_offset, 6),
        "height_max_m": round(raw_max + visual_offset, 6),
        "visual_z_offset_m": round(visual_offset, 6),
        "craters": [asdict(crater) for crater in craters],
    }
    return summary, visual_offset


def model_sdf(
    rock: RockPlacement,
    number: int,
    scene_id: str,
    asset_dims: dict[str, tuple[float, float, float]],
    craters: Iterable[TerrainCrater],
    crater_rim_height_scale: float,
    ground_lift_m: float,
) -> str:
    dx, dy, dz = asset_dims[rock.asset]
    scale = rock.scale
    name = f"{rock.asset}_scene_{scene_id}_{_sanitize_identifier(rock.name)}_{number:02d}"
    crater_list = list(craters)
    surface_z = crater_height(
        rock.x_m,
        rock.y_m,
        crater_list,
        crater_rim_height_scale,
    ) - crater_height(0.0, 0.0, crater_list, crater_rim_height_scale)
    surface_z += ground_lift_m
    return f'''    <!-- {rock.kind}:{rock.name} -->
    <model name="{name}">
      <static>true</static>
      <pose>{rock.x_m:.3f} {rock.y_m:.3f} {surface_z:.4f} 0 0 {rock.yaw_rad:.4f}</pose>
      <link name="link">
        <collision name="collision">
          <pose>0 0 {dz * scale / 2:.6f} 0 0 0</pose>
          <geometry><box><size>{dx * scale:.6f} {dy * scale:.6f} {dz * scale:.6f}</size></box></geometry>
        </collision>
        <visual name="visual">
          <geometry><mesh><uri>{asset_uri(scene_id, rock.asset)}</uri><scale>{scale:.4f} {scale:.4f} {scale:.4f}</scale></mesh></geometry>
          <cast_shadows>true</cast_shadows>
        </visual>
      </link>
    </model>'''


def border_wall_sdf(scene_id: str, side: str) -> str:
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
    <model name="{side}_border_wall_scene_{scene_id}">
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
    rocks: list[RockPlacement],
    visual_offset: float,
    scene_id: str,
    asset_dims: dict[str, tuple[float, float, float]],
    craters: Iterable[TerrainCrater],
    crater_rim_height_scale: float,
    ground_lift_m: float,
) -> None:
    text = world_path.read_text(encoding="utf-8")
    ground_block = re.search(r'(<model name="lunar_ground">.*?</model>)', text, flags=re.DOTALL)
    if not ground_block:
        raise ValueError(f"expected lunar_ground model in {world_path}")
    ground_text = ground_block.group(1)
    pose_value = f"0 0 {visual_offset + ground_lift_m:.6f} 0 0 0"

    def replace_pose(block: str, tag: str) -> str:
        pattern = rf'(<{tag} name="[^"]*">\s*<pose>)([^<]*)(</pose>)'

        def repl(match: re.Match[str]) -> str:
            return f"{match.group(1)}{pose_value}{match.group(3)}"

        new_block, count = re.subn(pattern, repl, block, count=1, flags=re.DOTALL)
        if count != 1:
            raise ValueError(f"expected {tag} pose in {world_path}")
        return new_block

    ground_text = replace_pose(ground_text, "collision")
    ground_text = replace_pose(ground_text, "visual")
    text = text[: ground_block.start(1)] + ground_text + text[ground_block.end(1) :]

    if GENERATED_BEGIN in text:
        start = text.index(GENERATED_BEGIN)
        end = text.index(GENERATED_END, start) + len(GENERATED_END)
    else:
        raise ValueError(f"expected generated rock marker block in {world_path}")
    models = "\n\n".join(
        model_sdf(
            rock,
            i + 1,
            scene_id,
            asset_dims,
            craters,
            crater_rim_height_scale,
            ground_lift_m,
        )
        for i, rock in enumerate(rocks)
    )
    borders = "\n\n".join(border_wall_sdf(scene_id, side) for side in ("west", "east", "south", "north"))
    models = f"{models}\n\n{borders}"
    generated = f"{GENERATED_BEGIN}\n{models}\n{GENERATED_END}"
    world_path.write_text(text[:start] + generated + text[end:], encoding="utf-8")


def ensure_world_template(world_path: Path, scene_id: str, world_name: str) -> None:
    if world_path.exists():
        return
    world_path.parent.mkdir(parents=True, exist_ok=True)
    world_path.write_text(
        f'''<?xml version="1.0" ?>
<sdf version="1.9">
  <world name="{world_name}">
    <gravity>0 0 -1.62</gravity>
    <magnetic_field>0 0 0</magnetic_field>
    <atmosphere type="adiabatic"/>

    <physics name="default_physics" default="true" type="ode">
      <max_step_size>0.001</max_step_size>
      <real_time_factor>1.0</real_time_factor>
    </physics>

    <scene>
      <ambient>0.035 0.035 0.04 1</ambient>
      <background>0.0 0.0 0.0 1</background>
      <grid>false</grid>
      <shadows>true</shadows>
    </scene>

    <plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-user-commands-system" name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>
    <plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors">
      <render_engine>ogre2</render_engine>
    </plugin>

    <light type="directional" name="sun_lunar_{world_name}">
      <cast_shadows>true</cast_shadows>
      <pose>0 0 13 0 0 0</pose>
      <attenuation>
        <range>1200</range>
        <constant>1</constant>
        <linear>0</linear>
        <quadratic>0</quadratic>
      </attenuation>
      <diffuse>0.96 0.93 0.86 1</diffuse>
      <specular>0.22 0.22 0.22 1</specular>
      <direction>-0.5 0.18 -0.85</direction>
    </light>

    <model name="lunar_ground">
      <static>true</static>
      <pose>0 0 0 0 0 0</pose>
      <link name="link">
        <collision name="collision">
          <pose>0 0 -0.018 0 0 0</pose>
          <geometry>
            <mesh>
              <uri>file:///tmp/thirover_scene_{scene_id}_assets/terrain/lunar_scene_{scene_id}_terrain.obj</uri>
              <scale>1 1 1</scale>
            </mesh>
          </geometry>
        </collision>
        <visual name="visual">
          <pose>0 0 -0.018 0 0 0</pose>
          <geometry>
            <mesh>
              <uri>file:///tmp/thirover_scene_{scene_id}_assets/terrain/lunar_scene_{scene_id}_terrain.obj</uri>
              <scale>1 1 1</scale>
            </mesh>
          </geometry>
          <material>
            <ambient>0.34 0.335 0.325 1</ambient>
            <diffuse>0.52 0.51 0.49 1</diffuse>
            <specular>0.015 0.015 0.015 1</specular>
            <emissive>0 0 0 1</emissive>
          </material>
          <cast_shadows>true</cast_shadows>
        </visual>
      </link>
    </model>

    {GENERATED_BEGIN}
    {GENERATED_END}
  </world>
</sdf>
''',
        encoding="utf-8",
    )


def _validate_xml(path: Path) -> None:
    import xml.etree.ElementTree as ET

    ET.parse(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene-id", default="02")
    parser.add_argument("--map-csv", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--world", type=Path, default=WORLD_PATH)
    parser.add_argument("--world-name", default=None)
    parser.add_argument("--crater-rim-height-scale", type=float, default=DEFAULT_CRATER_RIM_HEIGHT_SCALE)
    parser.add_argument("--ground-lift-m", type=float, default=DEFAULT_GROUND_LIFT_M)
    args = parser.parse_args()

    scene_id = str(args.scene_id).zfill(2)
    world_path = args.world
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    world_name = args.world_name or f"competition_luna_scene_{scene_id}"
    ensure_world_template(world_path, scene_id, world_name)

    asset_dims = _load_asset_dims()
    map_csv = resolve_csv_path(args.map_csv)
    rows = load_world02_csv(map_csv)
    craters, rocks = validate_csv_rows(rows, args.crater_rim_height_scale)

    summary, visual_offset = write_terrain_mesh(
        output_dir,
        craters,
        scene_id,
        args.crater_rim_height_scale,
    )
    summary["csv_path"] = str(map_csv)
    summary["world_name"] = world_name
    summary["rows_total"] = len(rows)
    summary["crater_count"] = len(craters)
    summary["rock_count"] = len(rocks)
    summary["rocks"] = [asdict(rock) for rock in rocks]
    summary["asset_dims"] = {name: list(dims) for name, dims in asset_dims.items()}
    update_world(
        world_path,
        rocks,
        visual_offset,
        scene_id,
        asset_dims,
        craters,
        args.crater_rim_height_scale,
        args.ground_lift_m,
    )

    summary_path = output_dir / "terrain_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "params: "
        f"scene_id={scene_id} "
        f"world_size_m={WORLD_SIZE_M:g} "
        f"crater_rim_height_scale={args.crater_rim_height_scale:g} "
        f"ground_lift_m={args.ground_lift_m:g} "
        f"border_wall_length_m={BORDER_WALL_LENGTH_M:g} "
        f"border_wall_overlap_m={BORDER_WALL_OVERLAP_M:g} "
        f"csv={map_csv}"
    )
    print(f"wrote {output_dir / f'lunar_scene_{scene_id}_terrain.obj'}")
    print(f"wrote {output_dir / f'lunar_scene_{scene_id}_terrain.mtl'}")
    print(f"updated {world_path} with {len(rocks)} rocks")
    print(f"wrote {summary_path}")
    _validate_xml(world_path)
    print(f"xml sanity check passed for {world_path}")


if __name__ == "__main__":
    main()
