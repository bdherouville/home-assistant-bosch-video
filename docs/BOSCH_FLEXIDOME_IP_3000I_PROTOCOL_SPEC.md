# FLEXIDOME IP 3000i IR
## Spécification de protocole et architecture d'intégration Home Assistant

Version du document : 1.0

Date de validation : 2026-07-23

Caméra de validation : `CAMERA_TEST_HOST`

Modèle déclaré par l'appareil : `FLEXIDOME IP 3000i IR`
Firmware validé : `7.93.0024`

> La caméra `CAMERA_TEST_HOST` est le banc d'essai. La caméra de production
> `CAMERA_PRODUCTION_HOST` ne doit recevoir aucune commande issue de cette spécification
> avant validation sur le banc d'essai et définition d'une procédure de retour
> arrière.

## 1. Objet du document

Ce document décrit les protocoles exposés par une caméra Bosch FLEXIDOME IP
3000i IR et propose l'architecture d'une intégration Home Assistant dédiée.

Il couvre :

- la découverte réseau ;
- l'authentification ;
- les services ONVIF ;
- les flux RTSP et les clichés JPEG ;
- les événements, l'analytique et les entrées/sorties ;
- la passerelle HTTP RCP ;
- les objets Bosch BICOM ;
- la correspondance avec les entités Home Assistant ;
- les règles de sécurité, de test et de compatibilité.

Ce n'est pas une reproduction intégrale de la documentation privée RCP de
Bosch. Les commandes natives sont limitées aux éléments observés dans
l'interface Web de la caméra ou vérifiés en lecture seule.

## 2. Statut des informations

Les mentions suivantes sont utilisées :

| Statut | Signification |
|---|---|
| **Vérifié** | Requête exécutée avec succès sur `CAMERA_TEST_HOST`. |
| **Observé** | Présent dans le client JavaScript embarqué ou dans une réponse de capacité. |
| **Documenté** | Décrit par une fiche technique ou un manuel Bosch. |
| **Proposé** | Choix d'architecture pour Home Assistant, non encore implémenté. |
| **À valider** | Ne doit pas encore être utilisé pour une écriture. |

## 3. Résumé matériel

| Capacité | État |
|---|---|
| Capteur vidéo | Une source vidéo ONVIF |
| Résolution maximale validée | 1920 x 1080 |
| Type de caméra | Dôme fixe |
| Pan/tilt motorisé | Non |
| Zoom/focus | Objectif motorisé, commandes Bosch natives |
| IR | Illuminateur intégré |
| Audio | Une source et une sortie, ligne audio externe |
| Entrée d'alarme | Une entrée |
| Sortie d'alarme | Un relais, 12 Vcc / 50 mA maximum |
| Masques de confidentialité | Huit |
| Stockage | microSD et iSCSI |
| Analytique | Essential Video Analytics |
| ONVIF | Profiles S, G et T |

Le réglage mécanique pan/tilt/rotation est manuel. Une commande `onvif.ptz` ne
doit donc pas être présentée comme un déplacement mécanique de ce modèle.

Le manuel fourni concerne également des variantes FLEXIDOME micro/turret.
Pour les caractéristiques physiques du modèle fixe, la fiche technique
`FLEXIDOME_IP_3000i_I_Data_sheet_frFR_73270028939.pdf` est prioritaire.

## 4. Couches de protocole

```text
Home Assistant
  |
  +-- ONVIF SOAP 1.2
  |     Device, Media, Events, DeviceIO, Imaging, Analytics,
  |     Recording, Search et Replay
  |
  +-- RTSP / RTSPS
  |     Vidéo et audio vers Stream, go2rtc ou Frigate
  |
  +-- Bosch RCP sur HTTP(S)
  |     /rcp.xml pour les fonctions Bosch absentes d'ONVIF
  |
  +-- Bosch RCP+ natif
  |     TCP 1756, réservé aux fonctions avancées
  |
  +-- SNMPv3 / Syslog
        Santé et diagnostic
```

La stratégie recommandée est :

1. utiliser ONVIF dès qu'une fonction y est réellement exposée ;
2. utiliser RTSP/go2rtc pour le média ;
3. utiliser les événements ONVIF ou Frigate MQTT pour les détections ;
4. utiliser RCP/BICOM uniquement pour les fonctions Bosch manquantes ;
5. ne jamais dupliquer une détection Frigate avec une détection Bosch sans
   définir une règle de priorité ou de fusion.

## 5. Services réseau

| Service | Port | État sur le banc | Usage |
|---|---:|---|---|
| HTTP | 80 | Activé | WebGUI, ONVIF, RCP HTTP, clichés |
| HTTPS | 443 | Activé | Variante chiffrée des services HTTP |
| RTSP | 554 | Activé | Média RTP/RTSP |
| RTSPS | 9554 | Activé | RTSP chiffré |
| RCP+ | 1756/TCP | Activé | Protocole Bosch natif |
| Discovery Bosch | 1800 | Activé | Découverte propriétaire |
| ONVIF Discovery | UDP 3702 | Activé | WS-Discovery multicast |
| iSCSI | 3260 | Activé | Stockage externe |
| SNMP | 161/UDP | Désactivé sur le banc | Supervision |
| Syslog | configurable | Non configuré | Journalisation distante |

### 5.1 ONVIF Discovery

La ligne « ONVIF discovery » de l'interface Bosch active WS-Discovery. Elle
n'active pas un port SOAP distinct.

Une sonde WS-Discovery envoyée à `239.255.255.250:3702` reçoit une réponse de
`CAMERA_TEST_HOST` annonçant :

```text
http://camera.example.invalid/onvif/device_service
https://camera.example.invalid/onvif/device_service
```

L'intégration doit utiliser l'adresse annoncée et ne pas supposer que le port
est toujours 80.

## 6. Comptes et authentification

### 6.1 Rôles Bosch

| Compte | Usage recommandé |
|---|---|
| `service` | Administration, ONVIF complet et RCP/BICOM |
| `user` | Fonctions utilisateur standard et média |
| `live` | Consultation en direct |

Sur le banc d'essai :

- `service` réussit `GetDeviceInformation` ;
- `user` reçoit `The requested action requires authorization` ;
- `service` est donc requis pour une intégration Bosch complète.

Cette contrainte est spécifique au comportement vérifié de cette caméra. La
documentation générique Home Assistant indique qu'un compte standard suffit
souvent aux caméras ONVIF, mais ce n'est pas le cas de l'appel d'identification
sur ce firmware Bosch.

### 6.2 Authentification ONVIF exacte

Le service accepte SOAP 1.2 avec un `UsernameToken` WS-Security utilisant
`PasswordDigest`.

```text
PasswordDigest =
  Base64(
    SHA1(
      nonce_binaire
      + Created_encodé_en_UTF8
      + mot_de_passe_encodé_en_UTF8
    )
  )
```

Le jeton contient :

```xml
<wsse:Security>
  <wsse:UsernameToken>
    <wsse:Username>service</wsse:Username>
    <wsse:Password Type="...#PasswordDigest">[digest]</wsse:Password>
    <wsse:Nonce EncodingType="...#Base64Binary">[nonce]</wsse:Nonce>
    <wsu:Created>2026-07-23T19:51:40+00:00</wsu:Created>
  </wsse:UsernameToken>
</wsse:Security>
```

Résultats vérifiés :

| Variante | Résultat |
|---|---|
| `service` + `PasswordDigest` | Acceptée |
| `service` + `PasswordText` | Refusée |
| `user` + `PasswordDigest` | Refusée |
| Mauvais digest | Refusé |
| HTTP Basic sans WS-Security | Refusé |
| Aucune authentification | Refusée |

HTTP Basic ou HTTP Digest ne remplace donc pas WS-Security pour les appels
SOAP de cette caméra.

L'horloge de Home Assistant et celle de la caméra doivent être synchronisées.
Une dérive peut invalider `Created` et provoquer une erreur d'authentification.

### 6.3 Authentification RCP HTTP

La passerelle `/rcp.xml` utilise HTTP Digest. Les lectures privilégiées
réussissent avec `service`. Le compte `user` a retourné HTTP 401 pour la lecture
des services réseau.

### 6.4 Stockage des secrets

L'intégration Home Assistant doit :

- stocker le nom d'utilisateur et le mot de passe dans la config entry ;
- ne jamais les placer dans les options, états ou attributs d'entité ;
- les masquer dans les diagnostics ;
- déclencher un flux `reauth` sur une erreur `NotAuthorized` ;
- ne jamais journaliser l'enveloppe WS-Security complète.

## 7. Endpoints ONVIF vérifiés

Un appel authentifié `GetServices` retourne dix endpoints :

| Namespace | Endpoint |
|---|---|
| Device v1 | `/onvif/device_service` |
| Media v1 | `/onvif/media_service` |
| Events v1 | `/onvif/event_service` |
| DeviceIO v1 | `/onvif/deviceio_service` |
| Media v2 | `/onvif/media2_service` |
| Analytics v2 | `/onvif/analytics_service` |
| Replay v1 | `/onvif/replay_service` |
| Search v1 | `/onvif/search_service` |
| Recording v1 | `/onvif/recording_service` |
| Imaging v2 | `/onvif/imaging_service` |

Le modèle n'annonce pas de service PTZ.

## 8. Service Device

### 8.1 Opérations à utiliser

| Opération | Usage Home Assistant |
|---|---|
| `GetDeviceInformation` | Fabricant, modèle, firmware, numéro de série |
| `GetServices` | Découverte des endpoints |
| `GetCapabilities` | Capacités principales |
| `GetNetworkInterfaces` | MAC et interface active |
| `GetSystemDateAndTime` | Diagnostic de synchronisation |
| `GetHostname` | Diagnostic |
| `GetScopes` | Nom, matériel et profils ONVIF |

### 8.2 Identifiant stable

L'identifiant de config entry doit être, par ordre de préférence :

1. le numéro de série retourné par ONVIF ;
2. la MAC retournée par `GetNetworkInterfaces`.

L'adresse IP ne doit jamais être utilisée comme identifiant unique. Elle est
modifiable et peut être mise à jour lors d'une redécouverte ou d'un flux
`reconfigure`.

## 9. Service Media

### 9.1 Capacités

Capacités vérifiées :

- maximum annoncé : 16 profils ;
- RTP multicast : oui ;
- RTP sur RTSP/TCP : oui ;
- rotation : oui ;
- une source vidéo ;
- une source audio, deux canaux ;
- URI de cliché fonctionnelle malgré `SnapshotUri=null` dans les capacités.

### 9.2 Profils du banc d'essai

Les valeurs sont celles de `CAMERA_TEST_HOST` et doivent être relues à chaque
configuration. Elles ne doivent pas être codées en dur.

| Token | Nom | Encodage | Résolution | FPS annoncé | Débit annoncé |
|---:|---|---|---:|---:|---:|
| `0` | `H26x_L1S1` | H.264 Main | 1920 x 1080 | 30 | 5600 kbit/s |
| `1` | `H26x_L1S2` | H.264 Main | 768 x 432 | 30 | 1400 kbit/s |
| `2` | `JPEG_L1S3` | JPEG | 1920 x 1080 | 1 | 6000 kbit/s |

Home Assistant doit créer des entités caméra uniquement pour les profils H.264
compatibles, comme le fait l'intégration ONVIF native.

### 9.3 URI retournées

Exemples retournés par `GetStreamUri` :

```text
/rtsp_tunnel?p=0&h26x=4&vcd=2
/rtsp_tunnel?p=1&inst=2&h26x=4
```

URI de cliché :

```text
/snap.jpg?JpegCam=1
```

Les URI Bosch directes déjà validées dans le projet sont :

```text
rtsp://HOST:554/?inst=1
rtsp://HOST:554/?inst=2
```

L'intégration ne doit pas reconstruire une URI si ONVIF en retourne une
utilisable. Les URI directes servent de solution de compatibilité Bosch.

### 9.4 Audio

ONVIF retourne :

- une source audio ;
- deux canaux ;
- une configuration G.711 ;
- 64 kbit/s ;
- 8 kHz.

La fiche technique documente également L16 et AAC-LC. Les capacités réelles
doivent être lues avant toute reconfiguration.

Le transport audio vers Frigate/go2rtc est distinct des entités Home Assistant.
Le talkback bidirectionnel reste **à valider** de bout en bout.

## 10. Service Imaging

### 10.1 Réglages exposés

Le banc retourne :

| Réglage | Valeur actuelle | Plage |
|---|---:|---:|
| Luminosité | 128 | 0 à 255 |
| Saturation | 128 | 0 à 255 |
| Contraste | 128 | 0 à 255 |

### 10.2 Limites

Les éléments suivants ne sont pas exposés par ONVIF Imaging sur ce firmware :

- focus ;
- autofocus ;
- exposition ;
- netteté ;
- balance des blancs ;
- WDR ;
- modes IR-cut exploitables.

La documentation Home Assistant prévoit des switches ONVIF pour l'IR et
l'autofocus, mais ils ne peuvent pas être créés ici à partir des options Imaging
retournées. Les commandes Bosch BICOM sont nécessaires.

## 11. Service DeviceIO

### 11.1 Capacités vérifiées

| Ressource | Nombre | Token |
|---|---:|---|
| Source vidéo | 1 | `1` |
| Source audio | 1 | `1` |
| Sortie audio | 1 | `AudioOut 1` |
| Entrée numérique | 1 | `Input_1` |
| Relais | 1 | `Output_1` |
| Port série | 0 | - |

### 11.2 Entrée numérique

L'entrée `Input_1` annonce `IdleState=open`. Son état initial observé dans les
événements est `LogicalState=true`.

Entité proposée :

```text
binary_sensor.<camera>_alarm_input
```

La polarité doit être calculée à partir de `IdleState`, pas supposée.

### 11.3 Relais

Le relais `Output_1` annonce :

- mode actuel : `Bistable` ;
- état de repos : `open` ;
- délai actuel : 0,5 s ;
- modes disponibles : `Bistable`, `Monostable` ;
- plage de délai : 0,5 à 300 s ;
- délai non discret.

Entités proposées :

- `switch` lorsque le mode est bistable ;
- `button` « Impulsion relais » lorsque le mode est monostable ;
- `select` pour le mode ;
- `number` pour le délai.

Les écritures ONVIF à utiliser sont `SetRelayOutputState` et
`SetRelayOutputSettings`. Chaque valeur doit être vérifiée après écriture.

## 12. Service Events

### 12.1 Particularité Bosch PullPoint

La caméra déclare :

```text
WSPullPointSupport = false
WSPausableSubscriptionManagerInterfaceSupport = false
MaxPullPoints = 10
```

Malgré cela, les appels suivants réussissent :

1. `CreatePullPointSubscription` ;
2. `PullMessages`.

L'adresse temporaire observée est de la forme :

```text
/Web_Service?Idx=N
```

Cette contradiction est connue du code ONVIF Home Assistant, qui essaie
PullPoint sur certaines caméras Bosch même quand la capacité est annoncée
fausse.

L'intégration doit donc tester la fonction au lieu de se fier uniquement au
booléen de capacité.

### 12.2 Événements initiaux vérifiés

Une première lecture PullPoint retourne :

| Topic | Données |
|---|---|
| `VideoSource/MotionAlarm` | `Source`, `State` |
| `VideoSource/GlobalSceneChange/AnalyticsService` | `Source`, `State` |
| `VideoSource/ImageTooBright/AnalyticsService` | `Source`, `State` |
| `VideoSource/ImageTooDark/AnalyticsService` | `Source`, `State` |
| `Device/Trigger/Relay` | `RelayToken`, `LogicalState` |
| `Device/Trigger/DigitalInput` | `InputToken`, `LogicalState` |

### 12.3 Autres familles annoncées

Le TopicSet contient notamment :

- `Media/ConfigurationChanged` ;
- `Media/ProfileChanged` ;
- `RecordingConfig/JobState` ;
- `RecordingConfig/RecordingConfiguration` ;
- `RecordingConfig/RecordingJobConfiguration` ;
- `RecordingConfig/TrackConfiguration` ;
- `RuleEngine/CountAggregation/Counter` ;
- `Monitoring/AsynchronousOperationStatus` ;
- `Monitoring/Profile/ActiveConnections` ;
- `Advancesecurity/Keystore/KeyStatus`.

### 12.4 Transport événementiel

Ordre de préférence :

1. webhook ONVIF si sa compatibilité est confirmée ;
2. PullPoint avec renouvellement et reprise automatique ;
3. MQTT Bosch Event Broker dans une phase ultérieure.

La caméra annonce `mqtt` et `mqtts` comme protocoles d'Event Broker, avec
quatre brokers maximum. Cette possibilité n'a pas encore été configurée.

Le gestionnaire doit :

- renouveler ou recréer la souscription avant expiration ;
- limiter le nombre de souscriptions ;
- dédupliquer les événements ;
- convertir l'heure caméra en UTC ;
- restaurer l'abonnement après une coupure ;
- supprimer les callbacks à l'unload de la config entry.

## 13. Service Analytics

### 13.1 Capacités vérifiées

- règles : oui ;
- modules analytiques : oui ;
- options de règles : oui ;
- options de modules : oui ;
- métadonnées : oui.

Une configuration compatible existe :

```text
token = 1
name = Analytics #1
use_count = 0
```

`use_count=0` signifie qu'elle n'est actuellement attachée à aucun profil du
banc d'essai.

### 13.2 Module

Le module annoncé est :

```text
tt:Viproc
```

### 13.3 Règles annoncées

`GetSupportedRules` retourne quinze types :

1. `ObjectInField`
2. `CrossingLines`
3. `Loitering`
4. `ConditionChange`
5. `FollowingRoute`
6. `Tampering`
7. `RemovedObject`
8. `IdleObject`
9. `EnteringField`
10. `LeavingField`
11. `SimilaritySearch`
12. `CrowdDetection`
13. `LineCounting`
14. `OccupancyCounting`
15. `MotionRegionDetector`

Aucune règle n'est actuellement créée sur le banc.

### 13.4 Politique d'intégration

Phase initiale :

- lire les capacités ;
- exposer les événements de règles déjà configurées ;
- ne pas modifier la configuration VCA.

Phase avancée :

- fournir un flux de configuration guidé ;
- valider les paramètres contre `GetSupportedRules` ;
- sauvegarder l'ancienne configuration ;
- créer ou modifier une seule règle à la fois ;
- permettre un retour arrière.

L'éditeur Bosch Alarm Task ne doit pas être automatisé. Le manuel indique qu'il
peut écraser les paramètres des autres pages d'alarme et que cette opération
n'est pas directement annulable.

## 14. Recording, Search et Replay

### 14.1 Recording

Capacités vérifiées :

- deux enregistrements maximum ;
- deux jobs maximum ;
- débit par enregistrement : 20 000 kbit/s maximum ;
- débit total : 20 000 kbit/s maximum ;
- encodages : H.264, G.711, AAC ;
- enregistrement de métadonnées : oui ;
- export : MP4 ;
- créations dynamiques de recordings/tracks : non.

### 14.2 Search

La caméra annonce :

- recherche de métadonnées : non ;
- événements généraux de début : non.

### 14.3 Replay

La caméra annonce :

- lecture inversée : oui ;
- RTP/RTSP/TCP : oui ;
- timeout de session : 60 s.

Frigate reste le gestionnaire recommandé pour la rétention et les clips Home
Assistant. ONVIF Recording/Replay peut être utilisé pour consulter une microSD
locale, sans devenir une seconde politique de rétention concurrente.

## 15. RCP via HTTP

### 15.1 Format de lecture

```text
GET /rcp.xml
    ?command=0xNNNN
    &type=TYPE
    &direction=READ
    &num=1
```

Authentification : HTTP Digest avec le compte `service`.

Paramètres observés :

| Paramètre | Description |
|---|---|
| `command` | Opcode RCP sur 16 bits |
| `type` | Type de la valeur |
| `direction` | `READ` ou `WRITE` |
| `num` | Index de ligne, flux, entrée ou sortie |
| `payload` | Valeur ou tableau d'octets |
| `sessionid` | Session RCP optionnelle |
| `idstring` | Identifiant client optionnel |

### 15.2 Types observés

| Type | Sens |
|---|---|
| `F_FLAG` | Booléen/octet |
| `T_OCTET` | Entier 8 bits |
| `T_WORD` | Entier 16 bits |
| `T_DWORD` | Entier 32 bits |
| `P_STRING` | Chaîne |
| `P_UNICODE` | Chaîne Unicode |
| `P_OCTET` | Tableau d'octets |

### 15.3 Réponse XML

La réponse contient :

- `command` ;
- `type` ;
- `direction` ;
- `num` ;
- `sessionid` ;
- `auth` ;
- `protocol` ;
- `result`, ou `result/err`.

Le niveau `auth=2` correspond au compte `service` dans les réponses vérifiées.

### 15.4 Erreurs RCP

| Code | Signification |
|---:|---|
| `0x10` | Version invalide |
| `0x20` | Client non enregistré |
| `0x21` | Identifiant client invalide |
| `0x30` | Méthode invalide |
| `0x40` | Commande invalide |
| `0x50` | Type d'accès invalide |
| `0x60` | Type de données invalide |
| `0x70` | Erreur d'écriture |
| `0x80` | Taille de paquet invalide |
| `0x90` | Lecture non prise en charge |
| `0xA0` | Niveau d'autorisation invalide |
| `0xB0` | Session invalide |
| `0xC0` | Réessayer plus tard |
| `0xD0` | Timeout |
| `0xE0` | Licence absente |
| `0xF0` | Erreur spécifique à la commande |
| `0xF1` | Format d'adresse invalide |
| `0xF2` | Non pris en charge sur cette plateforme |
| `0xFF` | Erreur inconnue |

## 16. Commandes RCP identifiées

### 16.1 Réseau et système

| Fonction | Opcode | Type | Statut |
|---|---:|---|---|
| Services réseau | `0x0C62` | `P_OCTET` | Vérifié en lecture |
| Orientation capteur | `0x0C39` | `P_OCTET` | Observé, lecture refusée `0x90` |
| État encodeur | `0x0A90` | `P_OCTET` | Observé, lecture refusée `0x90` |

Une erreur `0x90` signifie ici que cette méthode de lecture n'est pas supportée,
pas que l'authentification a échoué.

### 16.2 Audio

| Fonction | Opcode | Type | Statut |
|---|---:|---|---|
| Audio activé | `0x000C` | `F_FLAG` | Vérifié, valeur `0` |
| Entrée sélectionnée | `0x09B8` | `T_DWORD` | Vérifié, valeur `0` |
| Capacités audio | `0x09BF` | `T_DWORD` | Vérifié, valeur `3` |
| Niveau d'entrée | `0x000A` | `T_DWORD` | Observé |
| Maximum entrée | `0x09BA` | `T_DWORD` | Observé |
| Niveau microphone | `0x09BC` | `T_DWORD` | Observé |
| Maximum microphone | `0x09BD` | `T_DWORD` | Observé |
| Niveau sortie | `0x09B7` | `T_DWORD` | Observé |
| Maximum sortie | `0x09BB` | `T_DWORD` | Observé |
| Format d'enregistrement | `0x0AE9` | `T_OCTET` | Observé |
| Débit AAC | `0x0B9A` | `T_DWORD` | Observé |
| Crête entrée | `0x09C6` | `T_DWORD` | Observé |
| Crête sortie | `0x09C7` | `T_DWORD` | Observé |

La valeur de capacité audio `3` correspond à entrée ligne + sortie ligne.

### 16.3 Alarmes, relais et masques

| Fonction | Opcode | Type | Statut |
|---|---:|---|---|
| Capacités entrées | `0x0C6A` | `P_OCTET` | Vérifié, une entrée |
| Nombre d'alarmes virtuelles | `0x0AED` | `T_DWORD` | Vérifié, 16 |
| État/impulsion relais | `0x0094` | `F_FLAG` | Observé |
| Nom de relais | `0x0109` | `P_UNICODE` | Observé |
| État de repos relais | `0x0BDB` | `T_OCTET` | Observé |
| Options masques privés | `0x0BD7` | `P_OCTET` | Vérifié, huit masques |
| Polygones masques privés | `0x0BD8` | `P_OCTET` | Observé |
| Options masques VCA | `0x0C6F` | `P_OCTET` | Observé |
| Polygones masques VCA | `0x0C6E` | `P_OCTET` | Observé |

Le relais doit être commandé par ONVIF DeviceIO en priorité. RCP sert de
compatibilité ou pour les paramètres absents d'ONVIF.

## 17. BICOM

### 17.1 Transport

BICOM est encapsulé dans RCP avec :

```text
RCP command = 0x09A5
RCP type    = P_OCTET
```

Serveurs observés dans le client Bosch :

| Serveur | Valeur |
|---|---:|
| Device | `2` |
| Camera | `4` |
| PTZ/lens | `6` |
| CA | `8` |
| I/O | `10` |
| VCA | `12` |

Actions observées :

| Action | Valeur |
|---|---:|
| Get | `0x01` |
| Set | `0x03` |
| GetMax | `0x0B` |
| GetMin | `0x0C` |

Le cadrage exact, confirmé dans le client Web Bosch puis sur le banc, est :

```text
octet 0      flags de format (0x85 par défaut)
octets 1..2  identifiant du serveur, big-endian
octets 3..4  identifiant de l'objet, big-endian
octet 5      action BICOM
octets 6..n  valeur optionnelle
```

La requête BICOM utilise toujours une requête RCP XML de direction `WRITE`,
y compris pour l'action BICOM `Get`. Le `payload` est la représentation
hexadécimale des octets ci-dessus. Une réponse reprend le même en-tête de six
octets ; l'action `0x6F` signale une erreur BICOM et les octets suivants en
portent le code.

Erreurs BICOM :

| Code | Signification |
|---:|---|
| `0x0001` | Object ID illégal |
| `0x0002` | Member ID illégal |
| `0x0003` | Opération illégale |
| `0x0010` | Hors plage |
| `0x0011` | Taille de données illégale |
| `0x0020` | Non autorisé |
| `0x0021` | OSD actif |

### 17.2 Objectif et focus

Objets observés dans `page_lenssettings.js` :

| Fonction | Serveur | Objet | Statut |
|---|---:|---:|---|
| Mode de focus | Camera `4` | `496` | Observé |
| Vitesse de focus | Camera `4` | `498` | Observé |
| Limite proche jour | Camera `4` | `501` | Observé |
| Limite proche nuit | Camera `4` | `503` | Observé |
| Correction de focus IR | Camera `4` | `1043` | Observé |
| Auto-iris | Camera `4` | `432` | Observé |
| Niveau auto-iris | Camera `4` | `434` | Observé |
| Zoom numérique | Camera `4` | `464` | Observé |
| Vitesse maximale de zoom | PTZ/lens `6` | `289` | Observé |
| Limite de zoom | PTZ/lens `6` | `297` | Observé |

Ces objets n'ont pas encore été écrits. Avant de créer une entité :

1. lire la valeur courante ;
2. lire `GetMin` et `GetMax` si disponibles ;
3. comparer avec les options visibles du WebGUI ;
4. écrire sur le banc uniquement ;
5. relire et vérifier ;
6. définir la valeur de retour arrière.

### 17.3 Jour/nuit et IR

| Fonction | Serveur | Objet | Statut |
|---|---:|---:|---|
| Mode jour/nuit | Camera `4` | `320` | Lecture/écriture vérifiées |
| Illuminateur IR | Camera `4` | `1040` | Lecture vérifiée |
| Intensité IR | Camera `4` | `1041` | Lecture/écriture vérifiées, plage `0..30` |

Valeurs confirmées par `page_alc.js` :

| Objet | Valeur | Signification |
|---|---:|---|
| Jour/nuit `4/320` | `0` | Jour, couleur |
| Jour/nuit `4/320` | `1` | Nuit, monochrome |
| Jour/nuit `4/320` | `2` | Automatique |
| Illuminateur `4/1040` | `0` | Arrêt |
| Illuminateur `4/1040` | `1` | Marche |
| Illuminateur `4/1040` | `2` | Automatique |

Le banc a retourné `2` pour le mode jour/nuit, `2` pour l'illuminateur et `30`
pour l'intensité. Un essai réversible de l'intensité `30 → 29 → 30` a confirmé
le cadrage d'écriture et la relecture, avec restauration de la valeur initiale.
Les actions `GetMin` et `GetMax` ne sont pas implémentées par ce firmware pour
ces objets ; les plages et options doivent donc provenir des contrôles du
WebGUI et rester associées au firmware testé.

Ces objets sont les candidats principaux pour les entités `select`, `switch` et
`number` Bosch, car ONVIF Imaging ne les expose pas correctement.

## 18. RCP+ natif, SNMP et Syslog

### 18.1 RCP+ TCP 1756

Le port 1756 est ouvert. Le manuel le décrit comme un port RCP+ non chiffré.

Politique :

- ne pas l'utiliser dans la première version ;
- préférer `/rcp.xml` sur HTTPS lorsque possible ;
- ne pas exposer le port 1756 hors du réseau caméra ;
- n'ajouter un client binaire qu'avec une référence de protocole fiable.

### 18.2 SNMP

La caméra documente SNMP v1/v3 et MIB-II. Le banc a SNMP désactivé.

Recommandation :

- SNMPv3 uniquement ;
- SHA/AES ;
- entités de diagnostic désactivées par défaut ;
- aucun secret SNMP dans les états ou diagnostics.

Les OID spécifiques Bosch restent à inventorier.

### 18.3 Syslog

Syslog est utile pour :

- erreurs de stockage ;
- redémarrages ;
- authentifications refusées ;
- erreurs réseau ;
- diagnostics VCA.

Il doit rester un canal de diagnostic et non la source principale des états.

## 19. Relation avec Frigate

| Fonction | Responsable recommandé |
|---|---|
| Détection personne/objet | Frigate |
| Zones et suivi d'objets | Frigate |
| Clichés et clips d'alarme | Frigate |
| Sabotage/scene change | Bosch ONVIF |
| Entrée physique et relais | Bosch ONVIF DeviceIO |
| Comptage, ligne, flânage | Bosch VCA si configuré |
| Flux vidéo/audio | RTSP via go2rtc |
| Orchestration | Home Assistant |

Les événements Frigate et Bosch doivent recevoir des identifiants de source
différents. Une automation peut fusionner deux événements proches, mais
l'intégration ne doit pas déclarer qu'ils sont identiques.

## 20. Architecture Home Assistant recommandée

### 20.1 Ne pas remplacer l'intégration ONVIF native

Home Assistant possède déjà une intégration `onvif` :

- config flow ;
- WS-Discovery ;
- profils H.264 ;
- caméra et snapshots ;
- événements PullPoint/webhooks ;
- binary sensors et sensors ;
- switches Imaging/Auxiliary ;
- action PTZ ;
- reprise d'authentification.

Une intégration Bosch ne doit pas copier ou remplacer
`homeassistant.components.onvif`.

Deux voies sont possibles :

1. contribuer les améliorations génériques ONVIF à l'intégration native ;
2. créer `bosch_video` pour les fonctions Bosch RCP/BICOM et les capacités
   spécifiques non représentées.

La seconde voie est recommandée pour un premier prototype.

### 20.2 Domaine et manifeste

Domaine proposé :

```text
bosch_video
```

Exemple pour une custom integration :

```json
{
  "domain": "bosch_video",
  "name": "Bosch Video",
  "version": "0.1.0",
  "config_flow": true,
  "integration_type": "device",
  "iot_class": "local_push",
  "dependencies": ["ffmpeg"],
  "after_dependencies": ["onvif", "stream"],
  "requirements": ["bosch-video-client==0.1.0"],
  "loggers": ["bosch_video_client"]
}
```

Pour une intégration Core, `version` doit être omis.

### 20.3 Bibliothèque Python externe

Home Assistant demande que le code protocolaire réside dans une bibliothèque
Python externe. La bibliothèque proposée doit être asynchrone :

```text
bosch_video_client/
  auth.py
  client.py
  discovery.py
  onvif.py
  events.py
  rcp.py
  bicom.py
  models.py
  errors.py
```

Responsabilités :

- `auth.py` : WS-Security et HTTP Digest ;
- `onvif.py` : Device, Media, Imaging, DeviceIO, Events, Analytics ;
- `events.py` : abonnement, renouvellement et parsing ;
- `rcp.py` : requêtes typées et erreurs ;
- `bicom.py` : framing, capacités, plages et validation ;
- `models.py` : dataclasses immuables et comparables ;
- `errors.py` : erreurs d'authentification, connexion et protocole.

La bibliothèque ne stocke pas les identifiants.

### 20.4 Arborescence de l'intégration

```text
custom_components/bosch_video/
  __init__.py
  manifest.json
  const.py
  config_flow.py
  coordinator.py
  entity.py
  camera.py
  binary_sensor.py
  sensor.py
  switch.py
  number.py
  select.py
  button.py
  diagnostics.py
  services.yaml
  strings.json
  translations/
    fr.json
    en.json
```

### 20.5 Config flow

Étapes :

1. découverte WS-Discovery ou saisie manuelle ;
2. affichage du modèle et de l'adresse découverts ;
3. saisie du compte `service` ;
4. test `GetDeviceInformation` ;
5. test `GetServices` ;
6. inventaire des capacités ;
7. création avec numéro de série ou MAC comme `unique_id`.

Le flux doit aussi fournir :

- `reauth` pour changer les identifiants ;
- `reconfigure` pour changer l'hôte ou le port ;
- options pour activer les fonctions expérimentales RCP/BICOM ;
- confirmation explicite avant les commandes avancées.

### 20.6 Runtime et mises à jour

La config entry utilise un `runtime_data` typé contenant :

- client de protocole ;
- modèle de capacités ;
- coordinateur ;
- gestionnaire d'événements ;
- tâches de nettoyage.

Deux canaux de données :

1. **push** pour les événements ONVIF ;
2. **poll coordonné** pour les réglages et diagnostics.

Le `DataUpdateCoordinator` doit utiliser `always_update=False` avec des modèles
comparables. Intervalle initial recommandé : 60 secondes pour les états de
configuration ; aucun polling vidéo.

### 20.7 Entités proposées

#### Caméra

| Entité | Source |
|---|---|
| Flux principal | ONVIF Media profil H.264 token `0` |
| Flux secondaire | ONVIF Media profil H.264 token `1` |

La création de caméras peut rester à l'intégration ONVIF native afin d'éviter
les doublons.

#### Binary sensors

| Entité | Device class | Source |
|---|---|---|
| Mouvement | Motion | `MotionAlarm` |
| Changement global | Problem/Tamper | `GlobalSceneChange` |
| Image trop claire | Problem | `ImageTooBright` |
| Image trop sombre | Problem | `ImageTooDark` |
| Entrée d'alarme | Opening/None | `DigitalInput` |
| Relais actif | None | `Relay` |
| Sabotage VCA | Tamper | règle `Tampering` |
| Zone occupée | Occupancy | règle VCA |

#### Switches

| Entité | Source |
|---|---|
| Relais bistable | ONVIF DeviceIO |
| Audio activé | RCP `0x000C` |
| Illuminateur IR | BICOM `4/1040` |
| Correction focus IR | BICOM `4/1043` |
| Zoom numérique | BICOM `4/464` |

#### Numbers

| Entité | Source |
|---|---|
| Luminosité | ONVIF Imaging |
| Contraste | ONVIF Imaging |
| Saturation | ONVIF Imaging |
| Délai relais | ONVIF DeviceIO |
| Intensité IR | BICOM `4/1041` |
| Vitesse de focus | BICOM `4/498` |
| Niveau de sortie audio | RCP `0x09B7` |

#### Selects

| Entité | Source |
|---|---|
| Mode relais | ONVIF DeviceIO |
| Mode jour/nuit | BICOM `4/320` |
| Mode focus | BICOM `4/496` |
| Limite de zoom | BICOM `6/297` |
| Entrée audio | RCP `0x09B8` |
| Format audio | RCP `0x0AE9` |

#### Buttons

| Entité | Source |
|---|---|
| Impulsion relais | ONVIF DeviceIO |
| Autofocus ponctuel | À identifier/valider |
| Redémarrage | Device Management, désactivé par défaut |

Les entités de configuration sensibles sont désactivées par défaut jusqu'à ce
que leurs écritures soient validées.

### 20.8 Device registry

Le `DeviceInfo` doit fournir :

- identifiers : domaine + numéro de série ;
- connections : MAC ;
- manufacturer : Bosch ;
- model : FLEXIDOME IP 3000i IR ;
- sw_version : firmware ;
- configuration_url : HTTPS si disponible.

### 20.9 Disponibilité et erreurs

| Erreur bibliothèque | Traitement Home Assistant |
|---|---|
| Identifiants refusés | `ConfigEntryAuthFailed` |
| Caméra indisponible au setup | `ConfigEntryNotReady` |
| Timeout ponctuel | `UpdateFailed` |
| Fonction non supportée | Ne pas créer l'entité |
| Valeur hors plage | Refuser avant envoi |
| Erreur RCP/BICOM | Journaliser sans secret, conserver l'état précédent |

### 20.10 Diagnostics

Inclure :

- modèle et firmware ;
- endpoints sans identifiants ;
- capacités ;
- profils et résolutions ;
- compte des erreurs par protocole ;
- état du PullPoint ;
- dernier renouvellement ;
- opcodes pris en charge, sans payload sensible.

Masquer :

- mots de passe ;
- jetons WS-Security ;
- nonce et digest ;
- URI contenant des identifiants ;
- numéro de série si le diagnostic est destiné à être publié ;
- MAC selon la politique de confidentialité.

## 21. Tests

### 21.1 Bibliothèque

- calcul déterministe de `PasswordDigest` ;
- horloge décalée ;
- erreurs SOAP `NotAuthorized` ;
- parsing de chaque réponse ONVIF ;
- parsing des événements Bosch ;
- parsing RCP et BICOM ;
- mapping complet des erreurs ;
- bornes numériques ;
- annulation et timeout ;
- aucune écriture hors d'une méthode explicitement nommée `set_*`.

### 21.2 Intégration

- config flow manuel ;
- découverte ;
- doublon par numéro de série ;
- reauth ;
- reconfigure avec changement d'IP ;
- caméra hors ligne puis retour en ligne ;
- nettoyage des abonnements ;
- entités conditionnelles selon capacités ;
- traductions ;
- diagnostics expurgés ;
- tests avec fixtures SOAP/RCP anonymisées.

### 21.3 Banc matériel

Pour chaque commande d'écriture :

1. capturer la valeur initiale ;
2. vérifier la plage ;
3. effectuer une modification minimale ;
4. relire par le même protocole ;
5. vérifier dans le WebGUI ;
6. restaurer la valeur initiale ;
7. redémarrer uniquement si le réglage l'exige ;
8. vérifier que RTSP, ONVIF et les événements fonctionnent encore.

## 22. Plan d'implémentation

### Phase 0 - Bibliothèque read-only

- découverte ;
- authentification ;
- Device et GetServices ;
- Media ;
- DeviceIO ;
- Imaging ;
- PullPoint ;
- RCP read-only ;
- diagnostics.

### Phase 1 - Intégration Home Assistant read-only

- config flow ;
- device registry ;
- événements ;
- binary sensors ;
- sensors de diagnostic ;
- coexistence avec ONVIF/Frigate.

### Phase 2 - Commandes ONVIF sûres

- relais ;
- luminosité ;
- contraste ;
- saturation ;
- vérification après écriture.

### Phase 3 - Commandes Bosch

- IR ;
- jour/nuit ;
- audio ;
- focus ;
- limites et rollback ;
- entités expérimentales désactivées par défaut.

### Phase 4 - VCA

- lecture des règles ;
- mapping des événements ;
- assistant de configuration ;
- sauvegarde/restauration ;
- tests matériels.

## 23. Limites et inconnues

- Media2 est annoncé mais n'a pas encore été exercé.
- Le talkback audio n'a pas encore été validé.
- ONVIF Imaging n'expose pas focus/autofocus/IR-cut.
- Aucun endpoint PTZ n'est annoncé.
- Les valeurs et plages BICOM doivent encore être interrogées.
- Les OID SNMP Bosch restent à inventorier.
- Les règles VCA sont annoncées mais aucune règle n'est active sur le banc.
- Les écritures RCP/BICOM ne sont pas garanties stables entre firmwares.
- Le SKU matériel exact doit être lu séparément si une différence 2 MP/5 MP
  influe sur les capacités.

## 24. Sources

### Bosch

- `FLEXIDOME_IP_3000i_I_Data_sheet_frFR_73270028939.pdf`
- `FLEXIDOME_IP_micro_3_Operation_Manual_frFR_82103891083.pdf`
- [Bosch IP video products - Cybersecurity guidebook](https://cdn.commerce.boschsecurity.com/public/documents/IP_video_products_Cybersecurity_guidebook_enUS_99078607755.pdf)
- [Bosch firmware download area](https://downloadstore.boschsecurity.com/?type=FW)
- Interface Web et scripts JavaScript du firmware `7.93.0024`
- Réponses en lecture seule de `CAMERA_TEST_HOST`

### ONVIF

- [ONVIF Core Specification](https://www.onvif.org/ver10/tc/ONVIF_core_ver10.pdf)
- [ONVIF Network Interface Specifications](https://www.onvif.org/profiles-specifications-new/)

### Home Assistant

- [Creating your first integration](https://developers.home-assistant.io/docs/creating_component_index/)
- [Integration file structure](https://developers.home-assistant.io/docs/creating_integration_file_structure/)
- [Integration manifest](https://developers.home-assistant.io/docs/creating_integration_manifest/)
- [Config flow](https://developers.home-assistant.io/docs/core/integration/config_flow/)
- [Fetching data](https://developers.home-assistant.io/docs/integration_fetching_data/)
- [Networking and discovery](https://developers.home-assistant.io/docs/network_discovery/)
- [Building a Python library](https://developers.home-assistant.io/docs/api_lib_index/)
- [Integration diagnostics](https://developers.home-assistant.io/docs/core/integration/diagnostics/)
- [Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
- [ONVIF integration](https://www.home-assistant.io/integrations/onvif/)
- [ONVIF integration source](https://github.com/home-assistant/core/tree/dev/homeassistant/components/onvif)
