# LUNA World Generation Pipeline

This document records the current `thirover` LUNA competition world pipeline as it exists in the repo now. It is an inspection note, not a behavior change.

## 1. Current world files

The repo contains these related world files under `ros2_ws/src/rover_gazebo/worlds/`:

* `competition_luna_scene_01.sdf`
* `competition_luna_scene_02.sdf`
* `competition_luna_scene_probe_01.sdf`
* `competition_luna_external_asset_probe.sdf`
* `competition_luna_training_01.sdf`

For the competition scenes themselves:

* `competition_luna_scene_01.sdf` is a checked-in generated snapshot. The file still preserves a small hand-edited explanatory layer around the `lunar_ground` block, but the terrain/rock/border-wall content is rewritten by `scripts/generate_luna_scene_01_assets.py`.
* `competition_luna_scene_02.sdf` is also a checked-in generated snapshot. It is rebuilt by `scripts/generate_luna_scene_02_assets.py`.
* `competition_luna_scene_probe_01.sdf` and `competition_luna_external_asset_probe.sdf` are probe worlds, not the main competition scenes.

Which worlds are actually launched:

* `scripts/run_competition_luna_scene_01.sh` launches `competition_luna_scene_01.sdf`
* `scripts/run_competition_luna_scene_02.sh` launches `competition_luna_scene_02.sdf`
* `scripts/run_competition_luna_participant.sh` auto-generates and launches `competition_luna_scene_${world}.sdf` from `--world`
* `scripts/run_gazebo_rover_competition_luna.sh` launches `competition_luna_training_01.sdf`, which is separate from the competition scenes

## 2. Current input/source files

Scene 01:

* Source of truth is `scripts/generate_luna_scene_01_assets.py`
* Craters are hard-coded in the `CRATERS` list inside that script
* Rocks are generated deterministically in `generate_rocks()`
* The checked-in `competition_luna_scene_01.sdf` is a generated output snapshot, not the authoring source

Scene 02:

* The authoring surface is `scripts/world_generation/luna_2d_map_editor.svg`
* That SVG contains the editable object list and exports CSV text from its embedded script
* The checked-in CSV source is `scripts/world_generation/world02.csv`
* `world02.csv` is imported into the repo and is read by `scripts/generate_luna_scene_02_assets.py`
* The CSV file is stored with literal `\n` separators, and the generator normalizes them back to real newlines before parsing
* `scripts/generate_luna_scene_02_assets.py` can generate any numeric `--scene-id` / `--world` pairing, provided the matching CSV exists

## 3. Generator pipeline

Scene 01 generator:

* Script: `scripts/generate_luna_scene_01_assets.py`
* Purpose: build the terrain mesh, generate rock placements, and rewrite `competition_luna_scene_01.sdf`
* Tunables:
  * `--crater-rim-height-scale`
  * `--ground-collision-z`
  * `--ground-visual-offset`
* Terrain generation:
  * builds a `129 x 129` height field over a `24.0 m` square world
  * writes OBJ + MTL terrain files
  * computes a visual Z offset so the rover spawn area sits at the nominal `z=0` plane
* Rock generation:
  * places 48 deterministic rocks
  * writes rock models into the generated block in the SDF
  * adds the four border walls
* Command pattern:

```bash
python3 scripts/generate_luna_scene_01_assets.py \
  --output-dir outputs/competition_luna_scene_01/terrain \
  --world ros2_ws/src/rover_gazebo/worlds/competition_luna_scene_01.sdf \
  --crater-rim-height-scale 4.0 \
  --ground-collision-z -0.04 \
  --ground-visual-offset 0.0
```

Scene 02 generator:

* Script: `scripts/generate_luna_scene_02_assets.py`
* Purpose: read a CSV map, build the terrain mesh, and rewrite `competition_luna_scene_${scene-id}.sdf`
* Tunables:
  * `--crater-rim-height-scale`
  * `--ground-lift-m`
  * `--world-name`
* Terrain generation:
  * builds a `129 x 129` height field over a `24.0 m` square world
  * writes OBJ + MTL terrain files
  * computes a visual Z offset and adds the configured ground lift
* Rock generation:
  * reads 20 crater rows, 10 small rocks, and 5 large boulders from the CSV
  * uses bounding-box data from the converted GLB asset sidecars
  * writes scene-specific GLB URIs under `/tmp/thirover_scene_${scene-id}_assets/object/rock/`
  * writes rock models and border walls into the generated block in the SDF
* Command pattern:

Current standard command:

```bash
python3 scripts/generate_luna_scene_02_assets.py \
  --scene-id 02 \
  --map-csv scripts/world_generation/world02.csv \
  --output-dir outputs/competition_luna_scene_02/terrain \
  --world ros2_ws/src/rover_gazebo/worlds/competition_luna_scene_02.sdf \
  --world-name competition_luna_scene_02 \
  --crater-rim-height-scale 2.5 \
  --ground-lift-m 0.04
```

Outputs created by the generators:

* Runtime-required:
  * `outputs/competition_luna_scene_01/terrain/lunar_scene_01_terrain.obj`
  * `outputs/competition_luna_scene_01/terrain/lunar_scene_01_terrain.mtl`
  * `outputs/competition_luna_scene_02/terrain/lunar_scene_02_terrain.obj`
  * `outputs/competition_luna_scene_02/terrain/lunar_scene_02_terrain.mtl`
  * the two checked-in SDF snapshots, after they are rewritten with the generated block
* Temporary/debug only:
  * `outputs/competition_luna_scene_01/terrain/terrain_summary.json`
  * `outputs/competition_luna_scene_02/terrain/terrain_summary.json`
  * `outputs/competition_luna_scene_01/terrain/lunar_scene_01_terrain_height.png` if present from earlier runs
  * the probe world outputs under `outputs/luna_crater_world_seed/`

## 4. Asset pipeline

Tracked release rock assets live in:

* `ros2_ws/src/rover_gazebo/assets/luna/rock/apollo_sample20.glb`
* `ros2_ws/src/rover_gazebo/assets/luna/rock/lunalab_boulder1.glb`
* matching sidecars:
  * `ros2_ws/src/rover_gazebo/assets/luna/rock/apollo_sample20.bbox.json`
  * `ros2_ws/src/rover_gazebo/assets/luna/rock/lunalab_boulder1.bbox.json`

How they are produced:

* `scripts/convert_usdz_to_glb_with_blender.py` converts USD/USDZ assets to GLB with Blender
* The `.bbox.json` sidecars are written by the same script and are consumed by the scene 02 generator
* For the current release, the converted GLBs and sidecars are tracked in the repository under `ros2_ws/src/rover_gazebo/assets/luna/rock/`

Which assets are used:

* Small rocks: `apollo_sample20.glb`
* Large boulders: `lunalab_boulder1.glb`

How they are deployed at runtime:

* `scripts/run_competition_luna_scene_01.sh`, `scripts/run_competition_luna_scene_02.sh`, and `scripts/run_competition_luna_participant.sh` copy the GLBs into `/tmp/thirover_scene_${world}_assets/object/rock/`
* Scene 02 also copies the terrain OBJ/MTL into `/tmp/thirover_scene_${world}_assets/terrain/`

Tracking status:

* The competition rock GLBs and `.bbox.json` files are tracked release assets
* `outputs/external_asset_conversion_probe/` is no longer required at runtime for competition scenes
* The repo still does not track the `outputs/` tree, so terrain OBJ/MTL remain generated artifacts

## 5. Runtime pipeline

Base launch file:

* `ros2_ws/src/rover_gazebo/launch/gazebo_rover.launch.py`
* Launch arguments:
  * `gui` defaults to `true`
  * `world` defaults to `moon_rover_basic.sdf`
  * `camera_bridge` defaults to `false`
  * `rviz` defaults to `false`
* GUI/headless selection is handled by `gui`
  * `gui:=true` includes `gz_sim.launch.py` in GUI mode
  * `gui:=false` includes `gz_sim.launch.py` with `-s` for headless simulation
* The world is selected by the `world` launch argument, which is passed as a full path by the shell wrappers

Scene 01 launch:

* `scripts/run_competition_luna_scene_01.sh`
* Copies scene 01 GLBs and terrain into the Gazebo container
* Rebuilds `rover_gazebo` and `rover_autonomy`
* Launches `gazebo_rover.launch.py gui:=true world:=.../competition_luna_scene_01.sdf`

Scene 02 launch:

* `scripts/run_competition_luna_scene_02.sh`
* Copies scene 02 GLBs and terrain into the Gazebo container
* Rebuilds `rover_gazebo` and `rover_autonomy`
* Launches `gazebo_rover.launch.py gui:=true world:=.../competition_luna_scene_02.sdf`

Participant mode:

* `scripts/run_competition_luna_participant.sh`
* Selects the world by `--world`, default `01`
* Optional `--csv PATH` overrides the scene 02 CSV input
* Selects GUI by `--gui true|false`
* Selects RViz by `--rviz true|false`
* Selects regeneration mode by `--regen auto|always|never`, default `auto`
* Selects build mode by `--build auto|always|never`, default `auto`
* Always enables `camera_bridge:=true`
* Builds the world path as `competition_luna_scene_${world}.sdf`
* Regenerates scene 01 directly, and regenerates any other numeric world through the CSV-based generator using `scripts/world_generation/world${world}.csv` unless `--csv` overrides it
* `--regen never` now fails fast if the selected SDF or terrain OBJ/MTL are missing
* `--build never` now fails fast if `ros2_ws/install/setup.bash` is missing

Fast cached run:

```bash
scripts/run_competition_luna_participant.sh --world 02 --gui false --rviz false --regen never --build never
```

Normal run:

```bash
scripts/run_competition_luna_participant.sh --world 02 --gui false --rviz false --regen auto --build auto
```

RViz/camera helpers:

* `scripts/run_gazebo_rover_rviz.sh` starts RViz only
* `scripts/run_gazebo_rover_remote_control.sh` starts the rover remote control node
* `scripts/run_gazebo_rover_gui_rviz_rays.sh` launches a GUI/RViz/rays launch variant

## 6. Parameters and magic numbers

Scene 01:

* `WORLD_SIZE_M = 24.0` in `scripts/generate_luna_scene_01_assets.py`
  * centralized in the generator, duplicated in the checked-in SDF as the box size `24 24 0.08`
  * recommended centralization: keep only in the generator and regenerate the SDF
* `GRID_STEPS = 129`
  * centralized in the generator
* `DEFAULT_CRATER_RIM_HEIGHT_SCALE = 4.0`
  * centralized in the generator and exposed via `--crater-rim-height-scale`
* `BORDER_WALL_LENGTH_M = 25.0`, `BORDER_WALL_THICKNESS_M = 0.28`, `BORDER_WALL_HEIGHT_M = 0.95`
  * centralized in the generator
  * the 25 m length comes from a `0.5 m` corner overlap beyond the 24 m world square
* crater parameters
  * defined per crater in the `CRATERS` list
  * each crater stores `x_m`, `y_m`, `radius_m`, `rim_width_m`, `rim_height_m`, and `basin_depth_m`
  * duplicated nowhere else in source, but the generated SDF and OBJ are derived from them
* rock scales
  * `generate_rocks()` uses deterministic random ranges:
    * Apollo rocks: roughly `13.0-28.0` depending on zone
    * boulders: roughly `1.25-2.15`
  * centralized in the generator
* terrain/ground Z offset
  * `--ground-collision-z` and `--ground-visual-offset` are exposed for tuning
  * the generator still computes `visual_offset` from the height field and adds the visual offset adjustment
  * the checked-in SDF currently stores the tuned result after generation

Scene 02:

* `WORLD_SIZE_M = 24.0` in `scripts/generate_luna_scene_02_assets.py`
  * centralized in the generator
* `GRID_STEPS = 129`
  * centralized in the generator
* `SPAWN_CLEAR_RADIUS_M = 1.75`
  * centralized in the generator
* `DEFAULT_CRATER_RIM_HEIGHT_SCALE = 4.5`
  * centralized in the generator and exposed via `--crater-rim-height-scale`
* `DEFAULT_GROUND_LIFT_M = 0.04`
  * centralized in the generator and exposed via `--ground-lift-m`
* `BORDER_WALL_LENGTH_M = 25.0`, `BORDER_WALL_THICKNESS_M = 0.28`, `BORDER_WALL_HEIGHT_M = 0.95`
  * centralized in the generator
  * the 25 m length comes from a `0.5 m` corner overlap beyond the 24 m world square
* crater parameters
  * derived from `world02.csv`
  * rim width and basin depth are computed from crater radius inside the generator
* rock scales
  * CSV stores explicit values:
    * `apollo_sample20` small rocks: `18.0`
    * `lunalab_boulder1` large boulders: `1.0`
  * asset mesh dimensions come from the generated `.bbox.json` sidecars
* terrain/ground Z offset
  * derived from the generated height field plus `--ground-lift-m`
  * `--world-name` controls the world name written into the SDF template
  * the checked-in SDF currently stores the tuned result after generation

## 7. Boundary walls

Yes, both competition generators create boundary wall boxes.

* They are only at the border: west, east, south, and north
* There are no interior walls in the generator output
* The north/south wall orientation is now correct in both generators; the long side follows the field edge instead of standing crosswise
* The wall boxes now overlap at the corners, so there is no escape gap between adjacent walls
* Scene 01 creates them in `border_wall_sdf()` inside `scripts/generate_luna_scene_01_assets.py`
* Scene 02 creates them in `border_wall_sdf()` inside `scripts/generate_luna_scene_02_assets.py`
* They are generated, not manually inserted

## 8. Repo hygiene recommendation

Should be tracked:

* `scripts/generate_luna_scene_01_assets.py`
* `scripts/generate_luna_scene_02_assets.py`
* `scripts/world_generation/luna_2d_map_editor.svg`
* `scripts/world_generation/world02.csv`
* the checked-in competition world snapshots in `ros2_ws/src/rover_gazebo/worlds/`
* `ros2_ws/src/rover_gazebo/assets/luna/rock/*`

Should remain untracked/generated:

* `outputs/competition_luna_scene_01/terrain/*`
* `outputs/competition_luna_scene_02/terrain/*`
* `outputs/luna_crater_world_seed/*`
* other runtime outputs under `outputs/`

Should probably be removed before push:

* `.venv/`
* `scripts/world_generation/__pycache__/`
* `scripts/world_generation/luna_2d_map_editor.svg:Zone.Identifier`
* any other accidental local environment or browser/editor artifacts

For the `scripts/run_competition_luna_participant.sh --world 02 --gui true --rviz true` path specifically, these tracked files are not needed at runtime and are the first cleanup candidates if you want a minimal competition-only repo:

* `ros2_ws/src/rover_gazebo/worlds/competition_luna_external_asset_probe.sdf`
* `ros2_ws/src/rover_gazebo/worlds/competition_luna_scene_probe_01.sdf`
* `ros2_ws/src/rover_gazebo/worlds/competition_luna_training_01.sdf`
* `scripts/world_generation/design_crater_layout.py`
* `scripts/world_generation/generate_luna_crater_world.py`
* `scripts/world_generation/luna_2d_map_editor.svg`
* `scripts/world_generation/README.md`
* `scripts/run_competition_luna_external_asset_probe.sh`
* `scripts/run_competition_luna_scene_probe_01.sh`
* `scripts/run_gazebo_empty_world.sh`
* `scripts/run_gazebo_gui_direct.sh`
* `scripts/run_gazebo_rover_gui.sh`
* `scripts/run_gazebo_rover_headless.sh`
* `scripts/run_gazebo_rover_remote_control.sh`
* `scripts/run_gazebo_rover_rviz.sh`
* `scripts/run_gazebo_rover_teleop.sh`

## Inspection commands run

These commands were used while documenting the pipeline:

```bash
git status --short --untracked-files=all
find ros2_ws/src/rover_gazebo/worlds -maxdepth 1 -type f | sort
find scripts/world_generation -maxdepth 2 -type f | sort
sed -n '1,220p' scripts/world_generation/README.md
sed -n '1,260p' scripts/world_generation/generate_luna_crater_world.py
sed -n '1,260p' scripts/generate_luna_scene_01_assets.py
sed -n '1,260p' scripts/generate_luna_scene_02_assets.py
sed -n '1,240p' ros2_ws/src/rover_gazebo/launch/gazebo_rover.launch.py
sed -n '1,260p' scripts/world_generation/world02.csv
sed -n '1,220p' scripts/run_competition_luna_scene_01.sh
sed -n '1,220p' scripts/run_competition_luna_scene_02.sh
sed -n '1,220p' scripts/run_competition_luna_participant.sh
sed -n '1,220p' scripts/run_gazebo_rover_competition_luna.sh
sed -n '1,220p' scripts/run_competition_luna_external_asset_probe.sh
sed -n '1,220p' scripts/run_competition_luna_scene_probe_01.sh
sed -n '1,220p' scripts/run_gazebo_rover_headless.sh
sed -n '1,220p' scripts/run_gazebo_rover_gui.sh
sed -n '1,220p' scripts/run_gazebo_rover_rviz.sh
sed -n '1,220p' scripts/run_gazebo_rover_remote_control.sh
sed -n '1,220p' scripts/run_gazebo_rover_gui_rviz_rays.sh
sed -n '1,160p' ros2_ws/src/rover_gazebo/worlds/competition_luna_scene_01.sdf
sed -n '1,160p' ros2_ws/src/rover_gazebo/worlds/competition_luna_scene_02.sdf
git diff -- ros2_ws/src/rover_gazebo/worlds/competition_luna_scene_01.sdf scripts/generate_luna_scene_01_assets.py scripts/generate_luna_scene_02_assets.py scripts/world_generation/world02.csv
git ls-files ros2_ws/src/rover_gazebo/worlds | sort
find outputs -maxdepth 3 -type f | sort
git ls-files outputs | sort
rg -n "BEGIN GENERATED|END GENERATED|Upper-left crater|lunar_ground|border_wall|apollo_sample20|lunalab_boulder1|camera_bridge|rviz|gui:=|world:=" ros2_ws/src/rover_gazebo/worlds/competition_luna_scene_01.sdf ros2_ws/src/rover_gazebo/worlds/competition_luna_scene_02.sdf ros2_ws/src/rover_gazebo/launch/gazebo_rover.launch.py scripts/run_competition_luna_*.sh scripts/run_gazebo_rover_*.sh scripts/generate_luna_scene_*.py
rg -n "height.png|terrain_summary|bbox_path|external_asset_conversion_probe|world02.csv|world.02.csv|scene_probe_01|competition_luna_training_01" scripts ros2_ws/src/rover_gazebo -g '!**/__pycache__/**'
rg -n "world02.csv|crater|CSV|save|download|editor" scripts/world_generation/luna_2d_map_editor.svg
sed -n '220,340p' scripts/world_generation/luna_2d_map_editor.svg
sed -n '1,120p' scripts/world_generation/luna_2d_map_editor.svg
rg -n "apollo_sample20|lunalab_boulder1|blender|usdz|bbox|external_asset_conversion_probe" scripts outputs ros2_ws/src/rover_gazebo -g '!**/__pycache__/**'
sed -n '1,260p' scripts/convert_usdz_to_glb_with_blender.py
python3 scripts/generate_luna_scene_01_assets.py --output-dir outputs/competition_luna_scene_01/terrain --world ros2_ws/src/rover_gazebo/worlds/competition_luna_scene_01.sdf
python3 scripts/generate_luna_scene_02_assets.py --scene-id 02 --map-csv scripts/world_generation/world02.csv --output-dir outputs/competition_luna_scene_02/terrain --world ros2_ws/src/rover_gazebo/worlds/competition_luna_scene_02.sdf --world-name competition_luna_scene_02
python3 -m py_compile scripts/generate_luna_scene_01_assets.py scripts/generate_luna_scene_02_assets.py
bash -n scripts/run_competition_luna_participant.sh
grep -RIn "external_asset_conversion_probe" scripts/generate_luna_scene_01_assets.py scripts/generate_luna_scene_02_assets.py scripts/run_competition_luna_participant.sh scripts/run_competition_luna_scene_01.sh scripts/run_competition_luna_scene_02.sh
```
