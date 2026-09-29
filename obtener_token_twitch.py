"""
Consigue el TWITCH_REFRESH_TOKEN para la Action. Se hace UNA vez, en tu PC:

    python obtener_token_twitch.py CLIENT_ID CLIENT_SECRET

Se abre el navegador, entras con la cuenta del canal y aceptas. El script
escribe el refresh token: copialo en el secreto TWITCH_REFRESH_TOKEN del
repositorio del rancho.

La aplicacion de https://dev.twitch.tv/console tiene que tener como URL de
redireccionamiento exactamente  http://localhost:3000  y ser "Confidencial".
"""

import http.server
import json
import secrets
import sys
import urllib.parse
import urllib.request
import webbrowser

REDIRECCION = "http://localhost:3000"
PERMISO = "channel:read:subscriptions"


def main():
    if len(sys.argv) != 3:
        sys.exit("Uso: python obtener_token_twitch.py CLIENT_ID CLIENT_SECRET")
    cliente, secreto = sys.argv[1], sys.argv[2]
    estado = secrets.token_urlsafe(16)
    recibido = {}

    class Respuesta(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            consulta = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if consulta.get("state", [""])[0] == estado:
                recibido.update({k: v[0] for k, v in consulta.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("Listo, ya puedes cerrar esta pestaña.".encode())

        def log_message(self, *args):
            pass

    url = "https://id.twitch.tv/oauth2/authorize?" + urllib.parse.urlencode({
        "client_id": cliente,
        "redirect_uri": REDIRECCION,
        "response_type": "code",
        "scope": PERMISO,
        "state": estado,
    })
    print("Abriendo el navegador. Si no se abre, entra en:\n" + url)
    webbrowser.open(url)
    servidor = http.server.HTTPServer(("localhost", 3000), Respuesta)
    while not recibido:
        servidor.handle_request()
    if "code" not in recibido:
        sys.exit("Twitch no ha dado permiso: %s" % recibido.get("error_description", recibido))
    datos = urllib.parse.urlencode({
        "client_id": cliente,
        "client_secret": secreto,
        "code": recibido["code"],
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECCION,
    }).encode()
    with urllib.request.urlopen("https://id.twitch.tv/oauth2/token", data=datos, timeout=30) as r:
        token = json.load(r)
    print("\nTWITCH_REFRESH_TOKEN =", token["refresh_token"])


if __name__ == "__main__":
    main()
