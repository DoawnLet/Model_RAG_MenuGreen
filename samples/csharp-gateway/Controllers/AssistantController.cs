using MenuGreen.Gateway.Contracts;
using MenuGreen.Gateway.Services;
using Microsoft.AspNetCore.Mvc;

namespace MenuGreen.Gateway.Controllers;

[ApiController]
[Route("api/assistant")]
public sealed class AssistantController : ControllerBase
{
    private readonly IAiWorkerClient _aiWorkerClient;
    private readonly ILogger<AssistantController> _logger;

    public AssistantController(
        IAiWorkerClient aiWorkerClient,
        ILogger<AssistantController> logger
    )
    {
        _aiWorkerClient = aiWorkerClient;
        _logger = logger;
    }

    [HttpPost("chat")]
    [ProducesResponseType(typeof(AssistantChatResponseDto), StatusCodes.Status200OK)]
    public async Task<ActionResult<AssistantChatResponseDto>> Chat(
        [FromBody] AssistantChatRequestDto request,
        CancellationToken cancellationToken
    )
    {
        var requestId = request.RequestId ?? HttpContext.TraceIdentifier;
        var normalizedRequest = request with { RequestId = requestId };

        try
        {
            var workerResponse = await _aiWorkerClient.ChatAsync(
                normalizedRequest,
                cancellationToken
            );

            Response.Headers["X-Request-Id"] = workerResponse.RequestId;

            return Ok(
                new AssistantChatResponseDto(
                    workerResponse.RequestId,
                    workerResponse.ThreadId,
                    workerResponse.Response,
                    workerResponse.Intent
                )
            );
        }
        catch (HttpRequestException ex)
        {
            _logger.LogError(ex, "AI worker request failed for {RequestId}", requestId);
            return StatusCode(
                StatusCodes.Status502BadGateway,
                new
                {
                    requestId,
                    code = "ai_worker_unavailable",
                    message = "The AI worker is unavailable or returned an invalid response.",
                    details = ex.Message
                }
            );
        }
    }
}
