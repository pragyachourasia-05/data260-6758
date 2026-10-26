"""HW7 Part 1: fix the three issues Ruff reported (used by code/hw07_lint_demo.ps1).

F811  schema.py   - RelatedDetailUpdate was defined twice; keep one definition.
E402  main.py     - hw5_entities import sat at the bottom of the file; move it to the imports.
B904  main.py     - re-raise inside `except IntegrityError` with `from None`.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "backend" / "app"

schema = APP / "schema.py"
lines = schema.read_text(encoding="utf-8").splitlines()
heads = [i for i, line in enumerate(lines) if line.startswith("class RelatedDetailUpdate(")]
if len(heads) == 2:
    start = heads[1]
    end = start + 1
    while end < len(lines) and (lines[end].startswith((" ", "\t")) or not lines[end].strip()):
        end += 1
    kept = lines[:start] + lines[end:]
    while kept and not kept[-1].strip():
        kept.pop()
    schema.write_text("\n".join(kept) + "\n", encoding="utf-8")
    print("F811 fixed: removed the duplicate RelatedDetailUpdate class in schema.py")

main = APP / "main.py"
m = main.read_text(encoding="utf-8")
late = "from .hw5_entities import router as hw5_router\n"
if m.rstrip().endswith("app.include_router(hw5_router)") and late in m:
    m = m.replace(late, "", 1)
    m = m.replace("from .database import Base, engine, get_db\n",
                  "from .database import Base, engine, get_db\n" + late, 1)
    print("E402 fixed: moved the hw5_entities import to the top of main.py")
old = '''        raise HTTPException(
            status_code=409,
            detail="Username or email already exists",
        )
'''
if old in m:
    m = m.replace(old, '''        raise HTTPException(
            status_code=409,
            detail="Username or email already exists",
        ) from None
''', 1)
    print("B904 fixed: register_user re-raises with 'from None'")
main.write_text(m, encoding="utf-8")
