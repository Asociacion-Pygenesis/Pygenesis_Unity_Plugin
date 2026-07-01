"""Parser de bloque PYGENESIS_CREATE_SCRIPT + ```csharp```."""

from services.script_creation_parser import extract_script_creation


def test_extract_valid_script():
    raw = """Aquí tienes el script.

```csharp
using UnityEngine;
public class A : MonoBehaviour { }
```
---PYGENESIS_CREATE_SCRIPT---
{"fileName":"PlayerMove2D.cs"}
---PYGENESIS_SCRIPT_END---
"""
    visible, meta = extract_script_creation(raw)
    assert "PYGENESIS_CREATE_SCRIPT" not in visible
    assert meta is not None
    assert meta["asset_path"] == "Assets/Scripts/PlayerMove2D.cs"
    assert "MonoBehaviour" in meta["content"]


def test_no_markers_no_meta():
    visible, meta = extract_script_creation("Solo texto sin bloques.")
    assert meta is None


def test_fence_with_space_after_backticks():
    raw = """Ok.

``` csharp
using UnityEngine;
public class SpacedTag : MonoBehaviour { }
```
---PYGENESIS_CREATE_SCRIPT---
{"fileName":"SpacedTag.cs"}
---PYGENESIS_SCRIPT_END---
"""
    visible, meta = extract_script_creation(raw)
    assert meta is not None
    assert meta["asset_path"] == "Assets/Scripts/SpacedTag.cs"
    assert "SpacedTag" in meta["content"]


def test_generic_triple_backtick_when_csharp_like():
    raw = """Script:
```
using UnityEngine;
public class Gen : MonoBehaviour { }
```
---PYGENESIS_CREATE_SCRIPT---
{"fileName":"Gen.cs"}
---PYGENESIS_SCRIPT_END---
"""
    visible, meta = extract_script_creation(raw)
    assert meta is not None
    assert "Gen" in meta["content"]


def test_json_wrapped_in_fence_inside_markers():
    raw = """```csharp
class X : UnityEngine.MonoBehaviour {}
```
---PYGENESIS_CREATE_SCRIPT---
```json
{"fileName":"X.cs"}
```
---PYGENESIS_SCRIPT_END---
"""
    _, meta = extract_script_creation(raw)
    assert meta is not None
    assert meta["asset_path"] == "Assets/Scripts/X.cs"


def test_invalid_filename():
    raw = """```csharp
class X {}
```
---PYGENESIS_CREATE_SCRIPT---
{"fileName":"bad name.cs"}
---PYGENESIS_SCRIPT_END---
"""
    _, meta = extract_script_creation(raw)
    assert meta is None


def test_ignore_early_markers_when_visible_would_be_tiny():
    """Marcadores citados al inicio (p. ej. desde el system prompt) sin respuesta real tras ellos."""
    noise = ("thinking_line " * 90)
    raw = f"Respondes en C# y en Unity.\n\n---PYGENESIS_CREATE_SCRIPT---\n{noise}\n---PYGENESIS_SCRIPT_END---\n"
    assert len(raw) > 900
    visible, meta = extract_script_creation(raw)
    assert meta is None
    assert len(visible) > 200
    assert "thinking_line" in visible


def test_ignore_early_markers_on_short_answer():
    """Eco de marcadores tras una línea suelta, sin bloque de código."""
    raw = (
        "Respondes en C# y en Unity.\n"
        "---PYGENESIS_CREATE_SCRIPT---\n"
        '{"fileName":"Echo.cs"}\n'
        "---PYGENESIS_SCRIPT_END---\n"
        "1. ARQUITECTURA Y CONCEPTO: detalle GC en UI."
    )
    visible, meta = extract_script_creation(raw)
    assert meta is None
    assert "ARQUITECTURA" in visible
    assert len(visible) > 100

