---
name: slicer-data-loading-visualization-french
description: STC-VIS-101 Tutoriel de chargement de donnees et visualisation dans 3D Slicer. Montre comment charger et visualiser des images DICOM et des modeles 3D. Du Compendium de Formation 3D Slicer par Sonia Pujol, Ph.D. Version francaise.
metadata:
    skill-author: Ben Zwick, Sonia Pujol
    source: "https://training.slicer.org/"
    tutorial-id: STC-VIS-101
    application-version: Slicer-5.4
    language: French
---

# STC-VIS-101 : Les bases du chargement de donnees et de la visualisation (Francais)

Source : [3D Slicer Training Compendium](https://training.slicer.org/)
PDF : [Tutoriel de visualisation (Francais)](https://spujol.github.io/SlicerVisualizationTutorial/SlicerVisualizationTutorial_SoniaPujol-FrenchVersion.pdf)
Site web : [SlicerVisualizationTutorial](https://spujol.github.io/SlicerVisualizationTutorial/)
Auteur : Sonia Pujol, Ph.D.
Traduction francaise developpee dans le cadre du projet d'internationalisation de 3D Slicer finance par la Chan Zuckerberg Initiative.

- **Public :** Utilisateurs debutants souhaitant decouvrir les fonctionnalites de visualisation de base de 3D Slicer.
- **Modules :** DICOM, Volume Rendering, Models
- **Version de l'application :** Slicer-5.4

## Apercu

Le tutoriel Les bases du chargement de donnees et de la visualisation montre comment charger et visualiser des images DICOM et des modeles 3D dans 3D Slicer.

## Jeu de donnees

Telecharger le jeu de donnees du tutoriel : [Jeu de donnees de visualisation 3D](https://www.dropbox.com/s/03emcqnlec4t2s5/3DVisualizationDataset.zip?dl=1)

## Deroulement

Suggerer a l'utilisateur d'ouvrir le PDF du tutoriel en parallele pour les captures d'ecran detaillees.

---

### Partie 1 : Chargement et exploration des donnees d'exemple

#### Etape 1
Presenter l'interface principale de 3D Slicer : la vue 3D (en haut a droite), les trois vues en coupe (axiale, sagittale, coronale), le panneau de module (a gauche) et la sonde de donnees (en bas a gauche). Attendre que l'utilisateur termine.

#### Etape 2
Vider la scene. Telecharger les donnees d'exemple `MRHead`.

#### Etape 3
Demander a l'utilisateur d'observer le volume IRM dans les trois vues en coupe — chaque vue montre un plan anatomique different. Defiler avec la molette. Attendre que l'utilisateur termine.

#### Etape 4
Demander a l'utilisateur d'ajuster le fenetre/niveau : appuyer sur W pour activer l'outil, glisser dans une vue en coupe, puis appuyer sur V pour revenir. Attendre que l'utilisateur termine.

#### Etape 5
Demander a l'utilisateur de cliquer sur le bouton de maximisation (petite icone carree) pour remplir l'ecran, puis cliquer a nouveau pour restaurer. Attendre que l'utilisateur termine.

#### Etape 6
Demander a l'utilisateur de survoler l'icone epingle en haut a gauche d'une vue en coupe pour reveler la barre d'outils, puis cliquer sur >> pour developper. Attendre que l'utilisateur termine.

#### Etape 7
Demander a l'utilisateur d'activer la regle dans la barre d'outils et d'essayer le bouton Rotation vers le plan du volume. Attendre que l'utilisateur termine.

---

### Partie 2 : Disposition et navigation liee

#### Etape 8
Demander a l'utilisateur de cliquer sur le selecteur de disposition et passer a la disposition Conventionnelle. Attendre que l'utilisateur termine.

#### Etape 9
Demander a l'utilisateur de cliquer sur l'icone de liaison (chaine) pour lier toutes les vues. Le defilement ou le zoom s'applique maintenant a toutes. Attendre que l'utilisateur termine.

#### Etape 10
Afficher les trois plans de coupe anatomiques dans la vue 3D.

#### Etape 11
Demander a l'utilisateur de pratiquer la navigation 3D : clic gauche + glisser pour tourner, clic droit + glisser pour zoomer, clic milieu + glisser pour deplacer. Attendre que l'utilisateur termine.

---

### Partie 3 : Chargement de la scene du tutoriel

#### Etape 12
Vider la scene.

#### Etape 13
Demander a l'utilisateur de charger le fichier `VisualizationTutorial_HeadScene.mrb` en le glissant-deposant dans Slicer, ou via Fichier > Ajouter des donnees. Attendre que l'utilisateur termine.

#### Etape 14
Demander a l'utilisateur d'ouvrir le module Data (Ctrl+D) et d'explorer les noeuds charges — cliquer sur les icones oeil, essayer de masquer le modele "skin". Attendre que l'utilisateur termine.

---

### Partie 4 : Techniques de visualisation

#### Etape 15
Demander a l'utilisateur de superposer deux volumes : developper les controles de composition, selectionner T2 MRI comme premier plan, et utiliser le curseur d'opacite. Attendre que l'utilisateur termine.

#### Etape 16
Demander a l'utilisateur de creer un dossier "White matter models" dans le module Data et d'y glisser les noeuds de matiere blanche. Attendre que l'utilisateur termine.

#### Etape 17
Activer le rendu volumique sur les donnees IRM avec un preset MR-Default.

#### Etape 18
Regler l'opacite du modele du crane a environ 30% pour le rendre semi-transparent.

#### Etape 19
Afficher les plans de coupe anatomiques dans la vue 3D.

#### Etape 20
Demander a l'utilisateur d'explorer le decoupage de modeles : ouvrir le module Models, selectionner un modele cerebral, activer Clipping dans 3D Display, et experimenter avec les directions. Attendre que l'utilisateur termine.

---

### Partie 5 : Sauvegarde et rechargement

#### Etape 21
Demander a l'utilisateur de sauvegarder la scene : cliquer sur Sauvegarder, nommer le fichier `myNewScene.mrb`, choisir un emplacement. Attendre que l'utilisateur termine.

#### Etape 22
Demander a l'utilisateur de fermer la scene et de la recharger depuis Fichier > Recent pour verifier. Attendre que l'utilisateur termine.
