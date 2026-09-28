// src/api/sse.js
// Minimal POST-based SSE client over XMLHttpRequest — the transport
// `react-native-sse` uses, inlined rather than added as a dependency so the
// app's install footprint does not grow for one endpoint.
//
// Why XHR and not fetch: React Native's fetch does not expose a readable
// response body stream on all platforms, while XHR fires `onprogress` with the
// partially-received `responseText` — which is exactly what streaming an
// SSE endpoint needs.
//
// Event format produced by POST /chat/stream (FastAPI StreamingResponse):
//   data: {"type": "token",       "content": "..."}
//   data: {"type": "tool_start",  "tool": "...", "args": {...}}
//   data: {"type": "tool_result", "tool": "...", "summary": "..."}
//   data: {"type": "preamble",    "content": "..."}
//   data: {"type": "done",        "message_id": 123}
//   data: {"type": "error",       "detail": "..."}

/**
 * Stream an SSE POST endpoint.
 *
 * @param {object} opts
 * @param {string} opts.url        Absolute or relative URL (relative resolves
 *                                 against the axios baseURL used elsewhere).
 * @param {object} opts.body       JSON request body.
 * @param {string} opts.token      Bearer access token.
 * @param {function} opts.onEvent  Called with each parsed event object.
 * @param {function} opts.onError  Called once with an Error on failure.
 * @returns {function} abort — closes the connection mid-stream.
 */
export function streamSSE({ url, body, token, onEvent, onError }) {
    const xhr = new XMLHttpRequest();
    let processed = 0;
    let buffer = '';
    let aborted = false;

    const base = require('./axiosConfig').default?.defaults?.baseURL || '';
    const fullUrl = url.startsWith('http') ? url : `${base}${url}`;

    const parseChunk = (text) => {
        // SSE frames are separated by a blank line. A chunk boundary can split
        // a frame, so the tail is carried into the next chunk.
        buffer += text;
        const frames = buffer.split('\n\n');
        buffer = frames.pop() || '';
        for (const frame of frames) {
            for (const line of frame.split('\n')) {
                if (!line.startsWith('data:')) continue;
                const payload = line.slice(5).trim();
                if (!payload) continue;
                try {
                    onEvent(JSON.parse(payload));
                } catch (err) {
                    console.warn('[SSE] unparseable event payload:', payload.slice(0, 120));
                }
            }
        }
    };

    xhr.open('POST', fullUrl, true);
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.setRequestHeader('Accept', 'text/event-stream');
    // Matches the header axiosConfig sends on every normal request.
    xhr.setRequestHeader('ngrok-skip-browser-warning', 'true');

    xhr.onprogress = () => {
        if (aborted) return;
        const text = xhr.responseText;
        if (text && text.length > processed) {
            parseChunk(text.slice(processed));
            processed = text.length;
        }
    };

    xhr.onload = () => {
        if (aborted) return;
        // Flush any final frame without a trailing blank line.
        const text = xhr.responseText;
        if (text && text.length > processed) {
            parseChunk(text.slice(processed) + '\n\n');
        }
        if (xhr.status >= 200 && xhr.status < 300) {
            onEvent({ type: '__stream_end', status: xhr.status });
        } else {
            const err = new Error(`Stream failed: HTTP ${xhr.status}`);
            err.status = xhr.status;   // lets the caller refresh on 401
            onError(err);
        }
    };

    xhr.onerror = () => {
        if (!aborted) onError(new Error('Network error while streaming'));
    };

    // A full agent turn is bounded server-side; past two minutes the stream
    // is stuck, not slow, and the user should get an error instead of a spinner.
    xhr.timeout = 120000;

    xhr.ontimeout = () => {
        if (!aborted) onError(new Error('Stream timed out'));
    };

    try {
        xhr.send(JSON.stringify(body));
    } catch (err) {
        onError(err);
        return () => {};
    }

    return function abort() {
        aborted = true;
        try { xhr.abort(); } catch { /* already finished */ }
    };
}
