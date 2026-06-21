# Public Release Process

This document defines the release boundary for the THI LUNA rover challenge.
It is intentionally conservative: if a file is not clearly part of the public
release surface, it stays private.

## Repository Roles

- Private repo: the working repo for planning, experiments, new world drafts,
  internal notes, scoring drafts, debugging, and day-to-day development.
- Public org repo: the release repo for stable, intentional exports only.

The public repo is not the daily working repo. It should receive curated
release snapshots, not the full private development history.

## Development Flow

1. Develop privately.
2. Validate locally in the private repo.
3. Export only the release allowlist into a clean public repo tree.
4. Test the exported tree from a fresh clone or fresh checkout.
5. Push the public repo only after the fresh-clone test passes.

## Why Private History Must Stay Private

The private repo contains unreleased tasks, prototype worlds, scratch scripts,
debug probes, planning notes, and intermediate outputs. Publishing the private
git history would leak that internal work, make the public repo noisy, and risk
shipping unfinished or misleading material.

For that reason, the public repo should be created from a clean release export,
not by mirroring the private history wholesale.

## What Stays Private Only

Keep these out of the public repo unless they are explicitly promoted:

- unreleased tasks and scoring drafts
- new world drafts and probe worlds
- internal planning notes
- debug and probe scripts
- experimental scripts
- outputs, logs, and other generated runtime artifacts
- local build products and cache directories

## What May Be Released

The public repo may include:

- stable ROS packages
- participant and demo launch scripts
- final published SDF worlds
- generators for published worlds
- CSV and SVG authoring files for published worlds
- tracked release assets such as meshes and bbox sidecars
- public documentation needed by users

## Required Validation Before Public Release

Before a release export is published, run the lightweight checks that confirm
the tree is internally consistent:

- bash syntax checks for release scripts
- `python3 -m py_compile` for the world generator scripts
- world generation for the published worlds
- Gazebo and RViz smoke tests if practical
- fresh clone test after the public push

If a validation step is impractical for a given release, document the reason
and prefer the smallest substitute that still checks the release boundary.

## Release Rule

The public repo is only for release-ready content. Private development continues
in the private repo first, and only the approved allowlist is exported into the
public org repo.
