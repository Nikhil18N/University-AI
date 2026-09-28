# Error Handling

## LLM unavailable
Return a friendly temporary-service message. Log technical details internally.

## Vector DB unavailable
Do not answer university-specific questions from memory. Explain that verification is
temporarily unavailable.

## No relevant retrieval
Say the information could not be verified and suggest the appropriate official channel.

## Database unavailable
Return a generic service-unavailable response without exposing stack traces.

## Invalid input
Return a structured 4xx error.

## Timeouts
Use bounded timeouts and cancellation. Avoid indefinite requests.
