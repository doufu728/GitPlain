# -*- coding: utf-8 -*-
"""本地预览服务器：模拟 GitHub Pages 的两个行为
   1. 找不到的路径返回 404.html（状态码 404，内容是我们自己的 404 页）
   2. 静态文件按扩展名给正确的 Content-Type
用法： python serve.py [port]     默认 8137
"""
import http.server
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8137


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def send_error(self, code, message=None, explain=None):
        if code == 404:
            path = os.path.join(ROOT, '404.html')
            if os.path.exists(path):
                with open(path, 'rb') as f:
                    body = f.read()
                self.send_response(404)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
        super().send_error(code, message, explain)

    def log_message(self, format, *args):
        pass


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == '__main__':
    srv = Server(('127.0.0.1', PORT), Handler)
    print('serving %s on http://127.0.0.1:%d' % (ROOT, PORT))
    srv.serve_forever()
