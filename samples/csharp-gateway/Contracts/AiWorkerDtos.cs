namespace MenuGreen.Gateway.Contracts;

public sealed record ConversationMessageDto(string Role, string Content);

public sealed record AssistantChatRequestDto(
    string Message,
    string? UserId,
    string? ThreadId,
    string? RequestId,
    IReadOnlyList<ConversationMessageDto>? ConversationHistory
);

public sealed record AiWorkerChatRequestDto(
    string Message,
    string? UserId,
    string? ThreadId,
    string? RequestId,
    IReadOnlyList<ConversationMessageDto>? ConversationHistory
);

public sealed record AiWorkerChatResponseDto(
    string RequestId,
    string ThreadId,
    string Response,
    string? Intent,
    string SubscriptionTier,
    double DurationMs,
    bool PersistenceFallbackUsed,
    string Source
);

public sealed record AssistantChatResponseDto(
    string RequestId,
    string ThreadId,
    string Response,
    string? Intent
);
