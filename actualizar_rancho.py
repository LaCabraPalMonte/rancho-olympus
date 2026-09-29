"""
Genera rancho.txt con los suscriptores de Patreon y Twitch.

Lo ejecuta la GitHub Action (rancho.yml) una vez al dia. Solo usa la libreria
estandar de Python, no hace falta instalar nada.

Cada plataforma se actualiza solo si esta configurada; si no, sus filas del
rancho.txt anterior se quedan como estaban.

    Patreon  secreto PATREON_TOKEN (Creator's Access Token del portal de
             desarrolladores) y, opcional, PATREON_CAMPAIGN_ID.
    Twitch   secretos TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET y
             TWITCH_REFRESH_TOKEN (este ultimo lo da obtener_token_twitch.py).

Los secretos van en los Secrets del repositorio, NUNCA en el codigo ni en el
juego.

Lo que escoge cada suscriptor de Patreon (nick, y en el nivel que deja elegir
especie/shiny/zona) se escribe en la NOTA del miembro en Patreon
(Relaciones > miembro > Nota), asi:

    nick=Pepito; especie=PIKACHU; shiny=si; zona=LAGO

Todas las claves son opcionales. El juego ignora especie/shiny/zona si el nivel
no deja elegir.
"""

import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ARCHIVO = "rancho.txt"
CABECERA = "# RANCHO v1"
COLUMNAS = "# id|nick|tier|miembro_desde|rancho_desde|especie|shiny|zona|origen"
LARGO_MAX_NICK = 20

# Si alguien de Patreon no tiene nick en la nota: primero su nombre de usuario
# de Patreon (vanity) y, si tampoco tiene, su nombre de pila (nunca el
# apellido). Con False, quien no tenga nick ni vanity no sale en el rancho.
USAR_NOMBRE_DE_PILA = True

# Nivel de sub de Twitch -> tier del rancho (tienen que existir en
# Rancho::TIERS). Un nivel que no este aqui no sale en el rancho.
TIERS_TWITCH = {
    "1000": "HUMAN",
    "2000": "DEMIGOD",
    "3000": "GOD",
}
# Las subs regaladas tambien cuentan.
INCLUIR_SUBS_REGALADAS = True

API_PATREON = "https://www.patreon.com/api/oauth2/v2"
API_TWITCH = "https://api.twitch.tv/helix"


#===============================================================================
# Utilidades
#===============================================================================
def pedir(url, cabeceras, datos=None):
    cabeceras = dict(cabeceras, **{"User-Agent": "RanchoPkmOlympus/1.0"})
    if datos is not None:
        datos = urllib.parse.urlencode(datos).encode()
    peticion = urllib.request.Request(url, data=datos, headers=cabeceras)
    try:
        with urllib.request.urlopen(peticion, timeout=30) as respuesta:
            return json.load(respuesta)
    except urllib.error.HTTPError as e:
        # El cuerpo dice el motivo ("Invalid refresh token"...); nunca lleva los secretos
        motivo = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError("HTTP %d en %s: %s" % (e.code, url.split("?")[0], motivo)) from None


def limpiar(texto, largo=None):
    texto = re.sub(r"[|\r\n\t]", " ", texto or "").strip()
    return texto[:largo].strip() if largo else texto


def fila(origen, id, nick, tier, miembro_desde="", especie="", shiny="", zona=""):
    """Una fila de rancho.txt. rancho_desde se rellena al juntar."""
    return [str(id), limpiar(nick, LARGO_MAX_NICK), tier, miembro_desde, "",
            especie, shiny, zona, origen]


#===============================================================================
# Patreon
#===============================================================================
def patreon():
    token = os.environ.get("PATREON_TOKEN", "").strip()
    if not token:
        return None
    cabeceras = {"Authorization": "Bearer " + token}
    filas = []
    for miembro, usuario, tiers in miembros_patreon(cabeceras, campana_patreon(cabeceras)):
        attr = miembro["attributes"]
        # Los ex-suscriptores (y los que tienen el pago rechazado) no salen
        if attr.get("patron_status") != "active_patron" or not tiers or not usuario:
            continue
        nota = leer_nota(attr.get("note"))
        nick = nick_patreon(nota, miembro, usuario)
        if not nick:
            continue
        filas.append(fila("PATREON", usuario["id"], nick, clave_tier(tiers),
                          (attr.get("pledge_relationship_start") or "")[:10],
                          limpiar(nota.get("especie")).upper(),
                          limpiar(nota.get("shiny")).lower(),
                          limpiar(nota.get("zona")).upper()))
    return filas


def campana_patreon(cabeceras):
    campana = os.environ.get("PATREON_CAMPAIGN_ID", "").strip()
    if campana:
        return campana
    datos = pedir(API_PATREON + "/campaigns", cabeceras)["data"]
    if not datos:
        raise RuntimeError("Este token de Patreon no tiene ninguna campana.")
    return datos[0]["id"]


def miembros_patreon(cabeceras, campana):
    """Devuelve (miembro, usuario, tiers) de cada miembro, pagina a pagina."""
    parametros = urllib.parse.urlencode({
        "include": "currently_entitled_tiers,user",
        "fields[member]": "full_name,patron_status,pledge_relationship_start,note",
        "fields[tier]": "title,amount_cents",
        "fields[user]": "vanity,first_name",
        "page[count]": "500",
    })
    url = "%s/campaigns/%s/members?%s" % (API_PATREON, campana, parametros)
    while url:
        pagina = pedir(url, cabeceras)
        incluidos = {(o["type"], o["id"]): o for o in pagina.get("included", [])}
        for miembro in pagina["data"]:
            rel = miembro.get("relationships", {})
            usuario = rel.get("user", {}).get("data")
            usuario = incluidos.get(("user", usuario["id"])) if usuario else None
            tiers = [incluidos.get(("tier", t["id"]))
                     for t in rel.get("currently_entitled_tiers", {}).get("data", [])]
            yield miembro, usuario, [t for t in tiers if t]
        url = pagina.get("links", {}).get("next")


def leer_nota(nota):
    ret = {}
    for trozo in (nota or "").split(";"):
        if "=" in trozo:
            clave, valor = trozo.split("=", 1)
            ret[clave.strip().lower()] = valor.strip()
    return ret


def clave_tier(tiers):
    # Si tiene varios, cuenta el mas caro
    mejor = max(tiers, key=lambda t: t["attributes"].get("amount_cents") or 0)
    return re.sub(r"[^A-Z0-9]", "", (mejor["attributes"].get("title") or "").upper())


def nick_patreon(nota, miembro, usuario):
    nick = nota.get("nick")
    if not nick and usuario:
        nick = usuario["attributes"].get("vanity")
    if not nick and USAR_NOMBRE_DE_PILA:
        nick = (usuario or {}).get("attributes", {}).get("first_name")
        nick = nick or (miembro["attributes"].get("full_name") or "").split(" ")[0]
    return limpiar(nick, LARGO_MAX_NICK)


#===============================================================================
# Twitch
#===============================================================================
def twitch():
    cliente = os.environ.get("TWITCH_CLIENT_ID", "").strip()
    secreto = os.environ.get("TWITCH_CLIENT_SECRET", "").strip()
    refresco = os.environ.get("TWITCH_REFRESH_TOKEN", "").strip()
    if not (cliente and secreto and refresco):
        return None
    respuesta = pedir("https://id.twitch.tv/oauth2/token", {}, {
        "grant_type": "refresh_token",
        "refresh_token": refresco,
        "client_id": cliente,
        "client_secret": secreto,
    })
    if respuesta.get("refresh_token") not in (None, refresco):
        print("::warning::Twitch ha devuelto un refresh token distinto. Si manana "
              "falla, vuelve a ejecutar obtener_token_twitch.py y actualiza el secreto.")
    cabeceras = {"Authorization": "Bearer " + respuesta["access_token"], "Client-Id": cliente}
    canal = pedir(API_TWITCH + "/users", cabeceras)["data"][0]["id"]
    # Twitch no dice desde cuando esta suscrito cada uno: miembro_desde se
    # queda vacio y al juntar pasa a ser el dia en que llego al rancho.
    filas = []
    cursor = None
    while True:
        parametros = {"broadcaster_id": canal, "first": 100}
        if cursor:
            parametros["after"] = cursor
        pagina = pedir(API_TWITCH + "/subscriptions?" + urllib.parse.urlencode(parametros), cabeceras)
        for sub in pagina["data"]:
            if sub["user_id"] == canal:   # El propio canal sale como suscriptor
                continue
            if sub.get("is_gift") and not INCLUIR_SUBS_REGALADAS:
                continue
            tier = TIERS_TWITCH.get(sub.get("tier"))
            if tier:
                filas.append(fila("TWITCH", sub["user_id"], sub.get("user_name") or sub["user_login"], tier))
        cursor = pagina.get("pagination", {}).get("cursor")
        if not cursor or not pagina["data"]:
            return filas


#===============================================================================
# Juntarlo todo
#===============================================================================
FUENTES = [("PATREON", patreon), ("TWITCH", twitch)]


def leer_anterior():
    """(origen, id) -> fila del rancho.txt anterior."""
    ret = {}
    if os.path.exists(ARCHIVO):
        with open(ARCHIVO, encoding="utf-8") as f:
            for linea in f:
                if linea.startswith("#") or not linea.strip():
                    continue
                campos = (linea.rstrip("\r\n").split("|") + [""] * 9)[:9]
                campos[8] = campos[8].strip().upper() or "PATREON"
                ret[(campos[8], campos[0])] = campos
    return ret


def main():
    hoy = datetime.date.today().isoformat()
    anteriores = leer_anterior()
    filas = []
    errores = []
    for origen, fuente in FUENTES:
        conservar = False
        try:
            nuevas = fuente()
        except Exception as e:   # Que falle una plataforma no borra las demas
            print("::error::%s: %s" % (origen, e))
            errores.append(origen)
            nuevas = None
            conservar = True
        if nuevas is None:
            # Sin configurar (o con error): se queda lo que habia
            viejas = [f for (o, _), f in anteriores.items() if o == origen]
            filas.extend(viejas)
            estado = "error, se conservan" if conservar else "sin configurar, se conservan"
            print("%s: %s %d" % (origen, estado, len(viejas)))
            continue
        vistos = set()
        for nueva in nuevas:
            if nueva[0] in vistos:
                continue
            vistos.add(nueva[0])
            vieja = anteriores.get((origen, nueva[0]))
            nueva[4] = vieja[4] if vieja and vieja[4] else hoy
            if vieja and vieja[3] and (not nueva[3] or vieja[3] < nueva[3]):
                nueva[3] = vieja[3]   # La fecha mas antigua que se conozca
            nueva[3] = nueva[3] or nueva[4]
            filas.append(nueva)
        print("%s: %d" % (origen, len(vistos)))
    # Orden fijo: si nada cambia, el archivo sale identico y no hay commit
    filas.sort(key=lambda f: (f[4], f[8], f[0]))
    with open(ARCHIVO, "w", encoding="utf-8", newline="\n") as f:
        f.write(CABECERA + "\n")
        f.write(COLUMNAS + "\n")
        for f_ in filas:
            f.write("|".join(f_) + "\n")
    if errores:
        sys.exit("Han fallado: " + ", ".join(errores))


if __name__ == "__main__":
    main()
