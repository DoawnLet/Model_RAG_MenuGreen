using System.Net.Http.Json;
using MenuGreen.Gateway.Contracts;
using Microsoft.Extensions.Options;

namespace MenuGreen.Gateway.Services;

public sealed class AiWorkerOptions
{
    public const string SectionName = "AiWorker";
    public string BaseUrl { get; set; } = "http://127.0.0.1:8000";
}

public interface IAiWorkerClient
{
    Task<AiWorkerChatResponseDto> ChatAsync(
        AssistantChatRequestDto request,
        CancellationToken cancellationToken = default
    );
}

public sealed class AiWorkerClient : IAiWorkerClient
{
    private readonly HttpClient _httpClient;

    public AiWorkerClient(HttpClient httpClient, IOptions<AiWorkerOptions> options)
    {
        _httpClient = httpClient;
        _httpClient.BaseAddress = new Uri(options.Value.BaseUrl.TrimEnd('/') + "/");
        _httpClient.Timeout = TimeSpan.FromSeconds(150);
    }

    public async Task<AiWorkerChatResponseDto> ChatAsync(
        AssistantChatRequestDto request,
        CancellationToken cancellationToken = default
    )
    {
        var workerRequest = new AiWorkerChatRequestDto(
            request.Message,
            request.UserId,
            request.ThreadId,
            request.RequestId,
            request.ConversationHistory
        );

        using var response = await _httpClient.PostAsJsonAsync(
            "worker/chat",
            workerRequest,
            cancellationToken
        );

        var body = await response.Content.ReadAsStringAsync(cancellationToken);
        if (!response.IsSuccessStatusCode)
        {
            throw new HttpRequestException(
                $"AI worker returned {(int)response.StatusCode}: {body}"
            );
        }

        var payload = await response.Content.ReadFromJsonAsync<AiWorkerChatResponseDto>(
            cancellationToken: cancellationToken
        );

        return payload
            ?? throw new InvalidOperationException("AI worker returned an empty response.");
    }
}
