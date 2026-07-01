# Pygenesis AI con Ollama

Modelo local **`pygenesis-unity`**: GGUF fine-tuned + `Modelfile.pygenesis-unity`.

## Estructura

```
Tools/ollama/
  Modelfile.pygenesis-unity    # persona + parámetros (versionado en Git)
  create_ollama_model.ps1      # registra el modelo en Ollama
  write_modelfile_unity.py     # regenera el Modelfile si editas la plantilla
  models/
    pygenesis-unity-q4km.gguf  # pesos locales (NO se suben a Git)
```

## Pasos

1. Copia el GGUF a `Tools/ollama/models/pygenesis-unity-q4km.gguf`.
2. Registra en Ollama:

```powershell
cd Tools\ollama
powershell -File .\create_ollama_model.ps1
```

Equivalente manual:

```powershell
ollama create pygenesis-unity -f Modelfile.pygenesis-unity
```

3. En `Tools/pygenesis_backend/.env`:

```env
PYGENESIS_LLM_MODEL=pygenesis-unity
PYGENESIS_CHAT_PERSONA=modelfile
PYGENESIS_CHAT_DOMAIN_BLOCKS=off
PYGENESIS_LLM_CHAT_TEMPERATURE=0.55
PYGENESIS_LLM_REPEAT_PENALTY=1.22
PYGENESIS_LLM_CHAT_MAX_TOKENS=1536
PYGENESIS_OLLAMA_REASONING_EFFORT=none
```

4. Reinicia el backend y prueba el chat en Unity.

`PYGENESIS_CHAT_PERSONA=modelfile` evita que el backend duplique otra persona larga encima de la del Modelfile.

## Comprobar

```powershell
ollama run pygenesis-unity "Responde en una frase: ¿listo?"
ollama ps
```

## Fine-tuning (referencia)

Ollama no entrena; solo carga GGUF. El flujo habitual:

1. Preparar datos (instrucción → respuesta Unity/C#).
2. Entrenar fuera de Ollama (Unsloth, LLaMA-Factory, etc.).
3. Exportar a GGUF y copiarlo a `models/`.
4. Ajustar `Modelfile.pygenesis-unity` si cambian persona o parámetros.
5. `powershell -File .\create_ollama_model.ps1` de nuevo.

## Otro nombre de fichero GGUF

Renómbralo a `pygenesis-unity-q4km.gguf` o edita la línea `FROM` en `Modelfile.pygenesis-unity`.
