# Rancho de Pokémon Olympus

Lista de los suscriptores de Patreon y Twitch que viven en el rancho del juego.

- `rancho.txt`: la lista que descarga el juego. La regenera cada día la Action
  **Actualizar rancho** (`.github/workflows/rancho.yml`); no hace falta tocarla a mano.
- `actualizar_rancho.py`: consulta Patreon y Twitch y escribe `rancho.txt`.
- `obtener_token_twitch.py`: se ejecuta una vez en el PC para conseguir el
  `TWITCH_REFRESH_TOKEN`.

Secretos del repositorio (*Settings → Secrets and variables → Actions*):
`PATREON_TOKEN`, `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`, `TWITCH_REFRESH_TOKEN`.

Las instrucciones completas están en `Plugins/[Cabra] Rancho/Servidor/README.md`
del repositorio del juego.
