import { SSEEvent } from './types';

/**
 * Parse an SSE stream from a ReadableStreamDefaultReader,
 * yielding parsed SSEEvent objects.
 *
 * @param inactivityTimeoutMs - If no data arrives within this period, the
 *   stream is considered dead and the generator exits. Defaults to 30s.
 */
export async function* parseSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  inactivityTimeoutMs: number = 30_000,
): AsyncGenerator<SSEEvent> {
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      // Race read against inactivity timeout to detect dead connections
      const readPromise = reader.read();
      const timeoutPromise = new Promise<{ done: true; value: undefined }>(
        (resolve) => setTimeout(() => resolve({ done: true, value: undefined }), inactivityTimeoutMs)
      );

      const { done, value } = await Promise.race([readPromise, timeoutPromise]);
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const event = parseLine(line);
        if (event) yield event;
      }
    }

    // Process remaining buffer
    if (buffer) {
      const event = parseLine(buffer);
      if (event) yield event;
    }
  } finally {
    // Release the lock so the underlying stream can be cancelled/GC'd
    // even if the consumer aborts mid-iteration.
    try {
      reader.releaseLock();
    } catch {
      // Already released or in an invalid state — safe to swallow.
    }
  }
}

function parseLine(line: string): SSEEvent | null {
  if (!line.startsWith('data: ')) return null;
  const data = line.slice(6).trim();
  if (!data || data === '[DONE]') return null;
  try {
    return JSON.parse(data) as SSEEvent;
  } catch {
    return null;
  }
}
