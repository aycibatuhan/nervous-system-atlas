"""Console-script entry points (see pyproject [project.scripts])."""
from __future__ import annotations


def download():
    from .download import main; main()

def volumes():
    from .volumes import main; main()

def bp3d_select():
    from .bp3d import main_select; main_select()

def register():
    from .register import main; main()

def bp3d_meshes():
    from .bp3d import main_meshes; main_meshes()

def atlas_meshes():
    from .atlas_meshes import main; main()

def labels():
    from .labels import main; main()

def manifest():
    from .manifest import main; main()

def qa():
    from .qa import main; main()

def build_all():
    """Run the whole pipeline in order (the same sequence as pipeline/rebuild.sh, minus the Blender export)."""
    import subprocess, sys
    from pathlib import Path
    steps = ["atlas-download", "atlas-volumes", "atlas-atlas-meshes", "atlas-venat", "atlas-bp3d-select", "atlas-bp3d-meshes",
             "atlas-zanatomy-midline", "atlas-zanatomy-meshes", "atlas-pam50", "atlas-derived", "atlas-brainstem-nav",
             "atlas-lc-metamask",
             "atlas-labels", "atlas-manifest", "atlas-qa"]
    bindir = Path(sys.executable).parent
    for step in steps:
        exe = bindir / step
        if not exe.exists():
            print(f"[build] skip {step} (not installed)"); continue
        print(f"[build] == {step}")
        r = subprocess.run([str(exe)] + (sys.argv[1:] if step == "atlas-manifest" else []))
        if r.returncode != 0:
            print(f"[build] {step} failed with code {r.returncode}"); sys.exit(r.returncode)

def zanatomy_register():
    from .zanatomy import main_register; main_register()

def zanatomy_midline():
    from .midline import main; main()

def zanatomy_meshes():
    from .zanatomy import main_meshes; main_meshes()

def venat():
    from .venat import main; main()

def brainstem_nav():
    from .brainstem_nav import main; main()

def lc_metamask():
    from .lc_metamask import main; main()

def derived():
    from .derived import main; main()

def pam50():
    from .pam50 import main; main()
