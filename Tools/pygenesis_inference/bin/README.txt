# Binarios llama.cpp para PyGenesis (Windows x64, Vulkan)

PyGenesis solo necesita llama-server y sus DLL; no hace falta llama-cli, bench, quantize, etc.

## 1. Qué descargar

1. Abre https://github.com/ggml-org/llama.cpp/releases
2. En la release más reciente (cualquier bXXXX sirve), descarga el asset:

   llama-bXXXX-bin-win-vulkan-x64.zip

   Ejemplo: llama-b7526-bin-win-vulkan-x64.zip
   (El número bXXXX cambia en cada release; elige siempre *win-vulkan-x64*, no CUDA ni CPU-only.)

3. Descomprime el ZIP en una carpeta temporal.

## 2. Qué copiar a esta carpeta (bin/)

Copia aquí SOLO estos archivos (22 DLL/EXE + este README):

  llama-server.exe
  llama-server-impl.dll
  llama.dll
  llama-common.dll
  mtmd.dll
  ggml.dll
  ggml-base.dll
  ggml-vulkan.dll
  libomp140.x86_64.dll
  ggml-cpu-alderlake.dll
  ggml-cpu-cannonlake.dll
  ggml-cpu-cascadelake.dll
  ggml-cpu-cooperlake.dll
  ggml-cpu-haswell.dll
  ggml-cpu-icelake.dll
  ggml-cpu-ivybridge.dll
  ggml-cpu-piledriver.dll
  ggml-cpu-sandybridge.dll
  ggml-cpu-sapphirerapids.dll
  ggml-cpu-skylakex.dll
  ggml-cpu-sse42.dll
  ggml-cpu-x64.dll
  ggml-cpu-zen4.dll

Ruta final (runtime junto al proyecto):

  Tools/pygenesis_inference/bin/

Ruta final (instalador en %USERPROFILE%\.pygenesis):

  %USERPROFILE%\.pygenesis\pygenesis_inference\bin\

## 3. Qué NO copiar

No copies del ZIP: llama-cli.exe, llama-bench.exe, llama-quantize.exe, rpc-server.exe,
ni carpetas de ejemplos. Ocupa espacio y PyGenesis no los usa.

## 4. Comprobar

En PowerShell, desde pygenesis_inference:

  .\bin\llama-server.exe --version

Si responde versión, los binarios están bien. El arranque completo lo hace start_bridge.ps1
o Unity (PyGenesis → Open Assistant → Start Backend).

## 5. Arranque

- Desde Unity (recomendado): PyGenesis → Open Assistant → Start Backend
  (arranca el puente en :8081 y luego el backend en :8765).
- Manual: powershell -File start_bridge.ps1 en la carpeta pygenesis_inference.

No versionar en Git (.gitignore).
