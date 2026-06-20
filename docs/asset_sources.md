# External Asset Audit

- Source repo: `AndrejOrsula/space_robotics_gz_envs`
- Clone path: `/home/turnwald/robot_assets/external_repos/space_robotics_gz_envs`
- License: `LICENSE-CC0` in the asset submodule source, with a note in the repo README that some assets may require attribution if they derive from third-party resources.

## Findings

- The lunar/rock asset snapshot in `assets/srb_assets` is USD-only for the relevant content.
- I did not find directly loadable mesh formats for the lunar probe in this snapshot, such as `.dae`, `.obj`, `.stl`, `.glb`, or `.gltf`.
- The repo's procedural generation scripts emit SDF assets from Blender rather than prebuilt direct mesh files.

## Candidate files inspected

- `object/rock/apollo_sample20.usdz` - 276K
- `object/rock/apollo_sample21.usdz` - 280K
- `object/rock/apollo_sample2.usdz` - 284K
- `object/rock/spaceport_moon_rock6.usdz` - 2.8M
- `object/rock/spaceport_moon_rock7.usdz` - 2.8M
- `object/rock/spaceport_moon_rock5.usdz` - 3.2M
- `object/rock/spaceport_moon_rock1.usdz` - 3.4M
- `object/rock/lunalab_boulder1.usdz` - 5.0M
- `object/rock/lunalab_boulder4.usdz` - 5.2M
- `object/rock/lunalab_boulder2.usdz` - 5.8M
- `object/rock/lunalab_boulder3.usdz` - 6.5M
- `object/rock/spaceport_moon_rock2.usdz` - 7.1M

## Conclusion

- No suitable directly loadable lunar rock/surface asset exists in this repo snapshot for the Gazebo probe without conversion or new asset generation.
- For the external asset probe, `object/rock/apollo_sample20.usdz` is the selected conversion source and is intended to be exported to `outputs/external_asset_conversion_probe/apollo_sample20.glb` before Gazebo loads it.
