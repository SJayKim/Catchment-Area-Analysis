import { SSEEvent } from './types';

/**
 * Parse an SSE stream from a ReadableStreamDefaultReader,
 * yielding parsed SSEEvent objects.
 */
export async function* parseSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>
): AsyncGenerator<SSEEvent> {
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
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
