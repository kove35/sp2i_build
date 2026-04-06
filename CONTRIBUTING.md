# Contribuer à SP2I_Build

Ce document fixe une base simple pour garder le projet lisible, stable et exploitable en équipe.

## 1. Branching

Utiliser des branches courtes et explicites :

- `feature/dashboard-direction`
- `fix/import-kpi-timeout`
- `refactor/dashboard-service`
- `docs/readme-github`

## 2. Convention de commit

Format recommandé :

```text
type: description courte
```

Types principaux :

- `feat` : nouvelle fonctionnalité
- `fix` : correction de bug
- `refactor` : amélioration interne sans changement fonctionnel
- `docs` : documentation
- `test` : tests
- `chore` : maintenance technique

Exemples :

```text
feat: ajout du module dqe intelligent
fix: correction du filtre niveau dans le dashboard direction
refactor: extraction de la logique de ventilation import
docs: ajout du guide d'installation
test: ajout des tests smoke fastapi
```

## 3. Règles simples de code

- écrire des noms explicites
- privilégier des fonctions courtes
- séparer `backend`, `frontend`, `scripts` et `sql`
- commenter surtout la logique métier ou les hypothèses de calcul
- éviter de mélanger code exploratoire et code applicatif

## 4. Workflow Git recommandé

1. partir de `main` ou `develop`
2. créer une branche dédiée
3. coder et tester localement
4. faire des commits lisibles
5. ouvrir une Pull Request avec :
   - objectif
   - périmètre
   - risques
   - tests réalisés

## 5. Fichiers à ne pas committer

Ne pas pousser :

- `.env`
- fichiers `.db`
- logs
- `__pycache__`
- fichiers PDF / Excel source
- exports générés dans `artifacts/`

## 6. Checklist avant commit

- l’application démarre
- les tests passent
- aucun secret n’est présent
- aucun fichier local lourd ou temporaire n’est ajouté
- le commit décrit clairement l’intention

