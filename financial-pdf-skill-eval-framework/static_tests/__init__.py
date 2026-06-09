"""Static (offline) gatekeeping checks for the eval framework.

These checks read only the repo on disk, never hit the network, never invoke
the Skill, and never touch case ``output_dir``s. They are intended to run as a
fast first stage in CI to surface schema regressions, missing Skill files, or
accidentally committed secrets.
"""
