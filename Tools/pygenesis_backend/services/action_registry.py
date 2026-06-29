# services/action_registry.py
from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ActionRegistry:
    """
    Catálogo de acciones en memoria, cargado desde Unity vía POST /actions/register.

    Se usa para:
      1. Construir el bloque de acciones disponibles en el prompt del LLM.
      2. Validar y normalizar los params de POST /apply-action.
      3. Inyectarse como param_validator en AnalysisService (vía main.py).

    El singleton `action_registry` se instancia al final del módulo.
    Los tests instancian ActionRegistry() directamente para estar aislados.
    """

    def __init__(self):
        self._actions: dict[str, dict] = {}  # id → ActionDef dict

    # ── Carga ──────────────────────────────────────────────────────────────

    def load(self, actions: list[dict]) -> None:
        self._actions = {a["id"]: a for a in actions}
        logger.info("[ActionRegistry] Catálogo cargado: %s", list(self._actions.keys()))

    # ── Consulta ───────────────────────────────────────────────────────────

    def known_ids(self) -> list[str]:
        return list(self._actions.keys())

    def get(self, action_id: str) -> dict | None:
        return self._actions.get(action_id)

    def is_empty(self) -> bool:
        return len(self._actions) == 0

    # ── Validación y coerción ──────────────────────────────────────────────

    def validate_and_coerce(
        self,
        action_id: str,
        raw_params: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str]]:
        """
        Valida que los params requeridos estén presentes y convierte los tipos.

        Devuelve (params_coercionados, lista_de_warnings).
        Lanza ValueError si la acción es desconocida o falta un param requerido.
        """
        defn = self._actions.get(action_id)
        if defn is None:
            raise ValueError(f"Acción desconocida: '{action_id}'")

        coerced: dict[str, Any] = {}
        warnings: list[str] = []

        for pd in defn.get("params_def", []):
            pname    = pd["name"]
            ptype    = pd["type"]
            required = pd.get("required", False)
            default  = pd.get("default_value")

            if pname in raw_params:
                value = raw_params[pname]
            elif default is not None and default != "":
                value = default
                warnings.append(
                    f"Param '{pname}' ausente, usando default '{default}'"
                )
            elif required:
                raise ValueError(
                    f"Param requerido '{pname}' ausente en acción '{action_id}'"
                )
            else:
                continue  # opcional sin default → no incluir

            # Coerción de tipos
            try:
                if ptype == "float":
                    coerced[pname] = float(value)
                elif ptype == "bool":
                    if isinstance(value, bool):
                        coerced[pname] = value
                    else:
                        coerced[pname] = str(value).lower() in ("true", "1", "yes")
                else:  # string
                    coerced[pname] = str(value)
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"Param '{pname}' no se puede convertir a {ptype}: {e}"
                )

        return coerced, warnings

    # ── Prompt ────────────────────────────────────────────────────────────

    def to_prompt_block(self) -> str:
        """
        Genera el bloque de texto que se inyecta en el prompt del LLM
        para que solo use acciones del catálogo registrado.
        """
        if self.is_empty():
            return ""

        lines = ["Acciones disponibles (usa SOLO estas en suggestions[].action):"]
        for defn in self._actions.values():
            params_desc = ", ".join(
                f"{p['name']} ({p['type']}{'*' if p.get('required') else ''})"
                for p in defn.get("params_def", [])
            )
            desc = defn.get("description") or defn.get("label", "")
            lines.append(f"  - {defn['id']}: {desc}")
            if params_desc:
                lines.append(f"      params: {params_desc}  (* = requerido)")

        lines.append("")
        lines.append("Nunca inventes nombres de acción fuera de esta lista.")
        return "\n".join(lines)


# Singleton global — usado en main.py y en /actions/register
# Los tests NO deben importar esto; deben instanciar ActionRegistry() directamente.
action_registry = ActionRegistry()