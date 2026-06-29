# Filtrar el modo Thinking de Qwen3 en el backend

## El problema

El modelo `pygenesis-unity` está basado en **Qwen3**, que tiene el modo *thinking* integrado en los pesos. Esto significa que antes de responder genera un bloque de razonamiento interno que no debe llegar al plugin.

El bloque thinking tiene este aspecto en la respuesta raw:

```
Okay, the user is asking how to use Rigidbody...
Let me start by recalling what Rigidbody is...
</think>
Para mover un personaje en Unity3D usando Rigidbody...
```

La respuesta útil siempre viene **después** del `</think>`.

---

## La solución: filtrar en FastAPI

El filtro se aplica en el backend antes de devolver la respuesta al plugin. El plugin nunca ve el thinking.

### Función de filtrado

```python
import re

def filtrar_thinking(texto: str) -> str:
    # Caso 1: formato estándar <think>...</think>
    texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL)
    # Caso 2: solo </think> suelto al final (formato de Qwen3)
    if "</think>" in texto:
        texto = texto.split("</think>")[-1]
    return texto.strip()
```

### Dónde aplicarla en el endpoint

```python
@app.post("/consultar")
async def consultar(consulta: Consulta):
    # ... llamada a Ollama ...
    
    data         = response.json()
    texto        = data.get("response", "")
    texto_limpio = filtrar_thinking(texto)   # <-- aquí se filtra
    
    return {"respuesta": texto_limpio}
```

---

## Configuración de Ollama para minimizar el thinking

En la llamada a Ollama, estos parámetros ayudan a reducir la longitud del thinking:

```python
"options": {
    "temperature":      0.2,
    "top_p":            0.95,
    "top_k":            20,
    "presence_penalty": 1.5,
    "stop": ["<|im_end|>", "<|im_start|>"]  # tokens de parada
}
```

Y usar `"raw": True` para controlar el prompt manualmente:

```python
{
    "model":  "pygenesis-unity",
    "prompt": prompt_completo,
    "stream": False,
    "raw":    True,          # evita que Ollama aplique su propio template
    "options": { ... }
}
```

---

## Template correcto en el Modelfile

El Modelfile debe usar el formato **ChatML nativo de Qwen** con tokens de parada:

```
FROM ./qwen-unity-q4km.gguf

TEMPLATE """<|im_start|>system
{{ .System }}<|im_end|>
<|im_start|>user
{{ .Prompt }}<|im_end|>
<|im_start|>assistant
"""

SYSTEM """
Eres PYgenesis AI, el asistente experto del plugin PyGenesis para Unity.
...
"""

PARAMETER stop "<|im_end|>"
PARAMETER stop "<|im_start|>"
PARAMETER temperature 0.2
PARAMETER top_p 0.95
PARAMETER top_k 20
PARAMETER presence_penalty 1.5
```

Recrear el modelo tras cambiar el Modelfile:
```powershell
ollama create pygenesis-unity -f Modelfile
```

---

## Flujo completo con filtrado

```
Plugin Unity
    │
    ▼
POST /consultar {"prompt": "..."}
    │
    ▼
FastAPI construye el prompt con formato ChatML
    │
    ▼
Ollama ejecuta pygenesis-unity
    │
    ▼
Respuesta raw (con thinking):
  "Okay, let me think... </think> Para mover un personaje..."
    │
    ▼
filtrar_thinking() elimina todo antes de </think>
    │
    ▼
{"respuesta": "Para mover un personaje en Unity3D..."}
    │
    ▼
Plugin Unity recibe respuesta limpia
```

---

## Alternativa a largo plazo: fine-tuning con Qwen2.5

Si el filtrado no es suficiente o se quiere una solución más limpia, la alternativa es repetir el fine-tuning con **Qwen2.5-3B-Instruct**, que no tiene modo thinking en absoluto:

- Mismo proceso en Google Colab
- Cambiar `model_name = "Qwen/Qwen2.5-3B-Instruct"` en la celda 2
- El resto del notebook es idéntico
- Resultado: respuestas directas sin necesidad de filtrado
