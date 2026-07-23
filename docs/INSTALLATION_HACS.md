# Installation avec HACS

Cette intégration n'est pas encore publiée dans le catalogue HACS par défaut.
Il faut donc ajouter son dépôt GitHub comme dépôt personnalisé.

## Prérequis

- Home Assistant est installé et accessible ;
- HACS est déjà installé et configuré dans Home Assistant ;
- la caméra Bosch est joignable depuis Home Assistant ;
- un compte caméra disposant des droits nécessaires est disponible.

## Ajouter le dépôt personnalisé

1. Ouvrez **HACS** dans Home Assistant.
2. Ouvrez le menu à trois points en haut à droite, puis sélectionnez
   **Dépôts personnalisés** (*Custom repositories*).
3. Dans le champ **Dépôt**, saisissez exactement cette URL :

   ```text
   https://github.com/bdherouville/home-assistant-bosch-video
   ```

4. Sélectionnez le type **Intégration** (*Integration*).
5. Cliquez sur **Ajouter**.

La procédure officielle HACS pour les dépôts personnalisés est disponible dans
[la documentation HACS](https://hacs.xyz/docs/faq/custom_repositories/).

## Installer Bosch Video

1. Dans HACS, recherchez **Bosch Video**.
2. Ouvrez la fiche de l'intégration.
3. Cliquez sur **Télécharger** et conservez la dernière version stable
   proposée.
4. Redémarrez Home Assistant lorsque HACS le demande.

HACS installe les fichiers dans le dossier
`<config>/custom_components/bosch_video`.

## Ajouter une caméra

1. Dans Home Assistant, ouvrez
   **Paramètres > Appareils et services**.
2. Cliquez sur **Ajouter une intégration**.
3. Recherchez **Bosch Video**.
4. Renseignez l'adresse de la caméra, le port ONVIF ainsi que le nom
   d'utilisateur et le mot de passe de la caméra.
5. Ajoutez une entrée Bosch Video distincte pour chaque caméra physique.

L'intégration vérifie l'identité de la caméra lors d'une réauthentification ou
d'une reconfiguration afin d'éviter de remplacer accidentellement une caméra
par une autre.

## Mettre à jour l'intégration

Lorsqu'une mise à jour apparaît dans HACS :

1. ouvrez **Bosch Video** dans HACS ;
2. téléchargez la nouvelle version ;
3. redémarrez Home Assistant si HACS le demande.

Les versions installables par HACS correspondent aux versions publiées dans
les [releases GitHub](https://github.com/bdherouville/home-assistant-bosch-video/releases).

## Dépannage

- Si **Bosch Video** n'apparaît pas après l'installation, redémarrez Home
  Assistant puis videz le cache du navigateur.
- Vérifiez que le dossier
  `<config>/custom_components/bosch_video` a bien été créé.
- Vérifiez que Home Assistant peut joindre l'adresse et le port ONVIF de la
  caméra.
- Consultez les journaux Home Assistant en filtrant sur
  `custom_components.bosch_video`.
- Ne publiez jamais les identifiants, adresses privées, numéros de série,
  diagnostics bruts ou URL de flux de votre caméra.

Pour le fonctionnement général des intégrations téléchargées, consultez
[la documentation HACS sur les intégrations](https://hacs.xyz/docs/use/repositories/type/integration/).
