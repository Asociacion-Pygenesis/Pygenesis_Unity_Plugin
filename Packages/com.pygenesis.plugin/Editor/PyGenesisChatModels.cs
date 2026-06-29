using System;
using System.Collections.Generic;

/// <summary>
/// Contrato JSON de GET /chat/capabilities y POST /chat (alineado con el backend FastAPI).
/// </summary>
[Serializable]
public class PyGenesisChatCapabilitiesDto
{
    public string assistant;
    public string greeting;
    public List<PyGenesisCapabilityItemDto> capabilities;
}

[Serializable]
public class PyGenesisCapabilityItemDto
{
    public string id;
    public string title;
    public string description;
}

[Serializable]
public class PyGenesisChatMessageDto
{
    public string role;
    public string content;
}

[Serializable]
public class PyGenesisChatRequestDto
{
    public List<PyGenesisChatMessageDto> messages;
    public string scene_name;
    /// <summary>Misma instantánea que Analyze Scene (jerarquía, luces, etc.) para el LLM del chat.</summary>
    public PyGenesisSceneSnapshotData scene_snapshot;
}

[Serializable]
public class PyGenesisChatResponseDto
{
    public string role;
    public string content;
    /// <summary>Opcional; el backend puede enviar model, history_messages_used, etc.</summary>
    public Newtonsoft.Json.Linq.JObject metadata;
}
