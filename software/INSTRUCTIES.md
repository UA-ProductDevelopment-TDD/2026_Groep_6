# Instructies: de hond besturen met twee telefoons

Twee mensen sturen samen één Bittle. Elke speler bestuurt twee poten vanaf zijn eigen telefoon. Een laptop zit daartussen: daarop draait een kleine server die de webpagina voor de telefoons toont en de poten van de robot (of van de 3D-hond in Bittle Studio) aanstuurt.

```
telefoon 1 ──┐   wifi/hotspot   ┌── laptop: server.py ── USB / Bluetooth ──> Bittle
telefoon 2 ──┘                  └──                    ── of ──> Bittle Studio (3D-simulatie)
```

Alles staat in `software/`:
- `two-player-controller/`: de server en de telefoonpagina
- `bittle-studio/`: Bittle Studio (3D-simulatie), met de knoppen **Follow** en **Fullscreen**

---

## Eenmalig installeren

1. Installeer **Python 3.11 of 3.12** via <https://www.python.org/downloads/>. Vink **"Add python.exe to PATH"** aan.
2. Open in Verkenner de map `software\two-player-controller`. Klik in de adresbalk, typ `cmd` en druk op Enter. Er opent een zwart venster dat al in die map staat.
3. Typ:
   ```
   pip install -r requirements.txt
   ```
   Werkt `pip` niet? Typ dan `py -m pip install -r requirements.txt`.
4. Ga je met Bittle Studio werken? Dubbelklik dan één keer op `software\bittle-studio\launchers\windows\Setup`.

---

## De server starten

Open het zwarte venster in `software\two-player-controller` (zie stap 2 hierboven) en kies **één** van deze opdrachten:

| Waarmee? | Opdracht |
|---|---|
| Echte robot via **USB-kabel** | `python server.py --serial COM3` |
| Echte robot via **Bluetooth** | `python server.py --ble` |
| **Bittle Studio** (3D-simulatie) | `python server.py --studio` |
| Alleen de pagina testen, zonder robot | `python server.py --dry-run` |

- **USB:** het COM-nummer vind je in **Apparaatbeheer > Poorten (COM & LPT)**. Zoek "USB-Enhanced-SERIAL CH343". Zet ook de batterij van de robot aan, want USB alleen geeft te weinig stroom voor de motoren. Sluit de Seriële Monitor van Arduino IDE en de Petoi-app, want maar één programma tegelijk kan de poort gebruiken.
- **Bluetooth:** sluit eerst de Petoi-app op je telefoon. De robot laat maar één Bluetooth-verbinding tegelijk toe.
- **Bittle Studio:** start eerst de Studio (dubbelklik `software\bittle-studio\launchers\windows\Start Bittle Studio`) en wacht tot ze in je browser openstaat. Start daarna de server. De server zet de physics van de Studio zelf aan. Druk je in de Studio op **Reset**, druk dan daarna op **Run physics**.

**Stoppen:** druk op **Ctrl+C** in het zwarte venster. **Opnieuw starten:** pijltje omhoog en Enter.

---

## De telefoons verbinden

1. Zet de **hotspot** aan op een telefoon of op de laptop. Verbind de laptop en beide telefoons met die hotspot. **Eduroam werkt niet**: het blokkeert telefoons die met de laptop willen praten.
2. De server toont een paar adressen. Test eerst `http://localhost:8080` in de browser van de laptop: je moet "Bittle Duo" zien.
3. Typ op de telefoons het adres van de laptop, bijvoorbeeld `http://172.20.10.11:8080`. Typ `http://` er voluit bij. Weet je niet welk adres het is? Typ `ipconfig` in een zwart venster en neem het **IPv4-adres** onder **"Wireless LAN adapter Wi-Fi"**. Niet dat van Radmin VPN of andere VPN's.
4. Laadt de pagina niet op de telefoon? Dan blokkeert de Windows Firewall ze. Open **Opdrachtprompt als administrator** en typ:
   ```
   netsh advfirewall firewall add rule name="Bittle Duo" dir=in action=allow protocol=TCP localport=8080
   ```
   Helpt dat niet? Ga dan naar **Windows Defender Firewall met geavanceerde beveiliging > Regels voor binnenkomende verbindingen** en verwijder de **python**-regels met een rood blokkeer-icoon. Start de server opnieuw en klik op **Toestaan**.

---

## Spelen

1. Kies op elke telefoon een rol. De twee spelers kiezen elk een helft van hetzelfde paar:
   - **Links / rechts**: LEFT heeft de linkerpoten, RIGHT de rechterpoten
   - **Voor / achter**: FRONT heeft de voorpoten, BACK de achterpoten
   - **Diagonaal** (zoals een kameleon loopt): DIAGONAL 1 heeft linksvoor en rechtsachter, DIAGONAL 2 heeft rechtsvoor en linksachter
2. Elke telefoon heeft twee vlakken, één per poot:
   - Houd een vlak vast en schuif **opzij** om de voet op te tillen. De bol wordt groen.
   - Schuif **omhoog of omlaag** om de poot naar voor of naar achter te zwaaien.
   - **Laat los** om de voet neer te zetten.
3. Bittle loopt met diagonale paren: linksvoor gaat samen met rechtsachter, en rechtsvoor met linksachter. Zeg het ritme hardop tegen elkaar.
4. **Reset legs** zet alle vier de voeten weer in het midden.

In Bittle Studio houdt **Follow** de camera op de hond, en **Fullscreen** maakt het 3D-beeld schermvullend. Met Esc ga je terug.

Meer details, zoals hoe je hoeken en snelheid instelt, vind je in `two-player-controller/README.md`.
