using System;
using System.Text;
using UnityEngine.Networking;

/// <summary>
/// DownloadHandler para la respuesta NDJSON de POST /chat/stream.
/// Va recibiendo bytes a medida que el backend los emite y entrega líneas completas
/// (separadas por '\n') al callback, para poder pintar la respuesta del modelo de forma incremental.
/// </summary>
public class PyGenesisChatStreamDownloadHandler : DownloadHandlerScript
{
    private readonly Action<string> _onLine;
    private readonly Decoder _decoder = Encoding.UTF8.GetDecoder();
    private readonly StringBuilder _lineBuffer = new StringBuilder();
    private readonly StringBuilder _raw = new StringBuilder();

    /// <summary>Texto completo recibido (útil para formatear cuerpos de error no-stream).</summary>
    public string RawText => _raw.ToString();

    public PyGenesisChatStreamDownloadHandler(Action<string> onLine)
    {
        _onLine = onLine;
    }

    protected override bool ReceiveData(byte[] data, int dataLength)
    {
        if (data == null || dataLength <= 0)
        {
            return true;
        }

        // Decodifica UTF-8 de forma incremental (sin romper caracteres multibyte partidos entre paquetes).
        char[] chars = new char[dataLength];
        int charCount = _decoder.GetChars(data, 0, dataLength, chars, 0);
        _raw.Append(chars, 0, charCount);

        for (int i = 0; i < charCount; i++)
        {
            char c = chars[i];
            if (c == '\n')
            {
                FlushLine();
            }
            else if (c != '\r')
            {
                _lineBuffer.Append(c);
            }
        }

        return true;
    }

    protected override void CompleteContent()
    {
        FlushLine();
    }

    private void FlushLine()
    {
        if (_lineBuffer.Length == 0)
        {
            return;
        }

        string line = _lineBuffer.ToString();
        _lineBuffer.Length = 0;

        try
        {
            _onLine?.Invoke(line);
        }
        catch (Exception)
        {
            // Una línea malformada no debe abortar el resto del stream.
        }
    }
}
