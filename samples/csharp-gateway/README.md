# C# Gateway Sample

This folder shows the minimal pieces needed for an ASP.NET Core gateway that
forwards chat requests to the Python AI worker.

## Python worker endpoint

The gateway calls:

```text
POST http://127.0.0.1:8000/worker/chat
```

## Files

- `Contracts/AiWorkerDtos.cs`
- `Services/AiWorkerClient.cs`
- `Controllers/AssistantController.cs`

## Program.cs registration

```csharp
using MenuGreen.Gateway.Services;

builder.Services.Configure<AiWorkerOptions>(
    builder.Configuration.GetSection(AiWorkerOptions.SectionName)
);

builder.Services.AddHttpClient<IAiWorkerClient, AiWorkerClient>();
```

## appsettings.json

```json
{
  "AiWorker": {
    "BaseUrl": "http://127.0.0.1:8000"
  }
}
```

## Public gateway endpoint

```text
POST /api/assistant/chat
```

The controller maps the Python worker response back to a simpler API that your
mobile app or frontend can consume.
