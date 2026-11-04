# Instructions de développement du projet

## Langue et méthode
- Répondre en français.
- Travailler par petites étapes.
- Expliquer les changements envisagés avant de les appliquer.
- Ne pas modifier des fichiers sans rapport avec la demande.

## Reprise du travail
Avant la première analyse ou modification d'une session :
1. Lire CONTEXT.md s'il existe.
2. Lire SUIVI_DEV.md s'il existe.
3. Vérifier l'état réel des fichiers nécessaires à la tâche.
4. Signaler les écarts entre la documentation et le code.
5. Résumer brièvement la situation et la prochaine étape.

Ne pas considérer un ancien échange ou un document comme une preuve
qu'une modification a réellement été appliquée ou testée.

## Suivi continu
Après chaque étape significative terminée :
- Mettre à jour SUIVI_DEV.md, sous réserve des autorisations d'écriture.
- Ne pas attendre la fin de la conversation.
- Indiquer :
  - l'objectif en cours ;
  - les décisions prises et leurs raisons ;
  - les fichiers modifiés ;
  - les tests exécutés et leurs résultats ;
  - les tests non réalisés ;
  - les problèmes connus ;
  - la prochaine action précise.

Si SUIVI_DEV.md n'existe pas, proposer sa création.

## Documentation durable
CONTEXT.md décrit l'architecture, les dépendances et les règles métier.
Ne le modifier que si ces informations changent.
Préserver les informations encore valides.

## Exactitude
Distinguer clairement :
- proposé ;
- appliqué ;
- testé ;
- restant à faire.

Ne jamais annoncer un test réussi sans l'avoir exécuté et vérifié.

## Confidentialité et contrôle
- Ne pas lire ni copier les fichiers .env, secrets, clés ou mots de passe.
- Ne pas inclure de données personnelles dans la documentation.
- Ne pas consulter les autres projets sans accord explicite.
- Demander confirmation avant toute commande destructive,
  installation de dépendances, opération sur une base de données,
  commit, push ou déploiement.