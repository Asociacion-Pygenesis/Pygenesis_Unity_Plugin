# Pesos GGUF (local, no versionados)

Descarga desde Hugging Face: [SuNavar/Pygenesis-Unity — pygenesis-unity-q4km.gguf](https://huggingface.co/SuNavar/Pygenesis-Unity/blob/main/pygenesis-unity-q4km.gguf) (~4,7 GB).

Copia el archivo aquí:

```
Tools/ollama/models/pygenesis-unity-q4km.gguf
```

El fichero **no se sube a Git** (está en `.gitignore`). Solo vive en tu máquina.

Tras copiarlo:

```powershell
cd Tools\ollama
powershell -File .\create_ollama_model.ps1
```

Eso registra el modelo en Ollama como `pygenesis-unity:latest`.
