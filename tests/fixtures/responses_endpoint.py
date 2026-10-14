"""Isolated Responses-protocol endpoint for installed host boundary tests."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread


class ResponsesEndpoint:
    def __init__(self):
        self.requests = []
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"data":[],"object":"list"}')

            def do_POST(self):
                value = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                parent.requests.append(value)
                part = {"type": "output_text", "text": "Probe complete.", "annotations": []}
                item = {"id": "msg_probe", "type": "message", "role": "assistant", "status": "completed", "content": [part], "phase": "final_answer"}
                response = {"id": "resp_probe", "object": "response", "created_at": 1, "model": value.get("model", "probe"),
                            "status": "completed", "output": [item], "error": None, "incomplete_details": None,
                            "usage": {"input_tokens": 100, "output_tokens": 3, "total_tokens": 103,
                                      "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}}}
                events = [{"type": "response.created", "response": {**response, "status": "in_progress", "output": []}},
                          {"type": "response.output_item.added", "output_index": 0, "item": {**item, "status": "in_progress", "content": []}},
                          {"type": "response.content_part.added", "output_index": 0, "item_id": item["id"], "content_index": 0, "part": {**part, "text": ""}},
                          {"type": "response.output_text.delta", "output_index": 0, "item_id": item["id"], "content_index": 0, "delta": part["text"]},
                          {"type": "response.output_text.done", "output_index": 0, "item_id": item["id"], "content_index": 0, "text": part["text"]},
                          {"type": "response.content_part.done", "output_index": 0, "item_id": item["id"], "content_index": 0, "part": part},
                          {"type": "response.output_item.done", "output_index": 0, "item": item},
                          {"type": "response.completed", "response": response}]
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                for sequence, event in enumerate(events):
                    self.wfile.write(("event: " + event["type"] + "\ndata: " + json.dumps({**event, "sequence_number": sequence}) + "\n\n").encode())
                self.wfile.write(b"data: [DONE]\n\n")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1"
        return self

    def __exit__(self, *_):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
