---
name: slicer-dicom-tutorial-french
description: STC-DICOM-101 Tutoriel DICOM et Slicer. Fournit une introduction au standard DICOM et montre comment charger et visualiser des jeux de donnees DICOM dans 3D Slicer. Du Compendium de Formation 3D Slicer par Sonia Pujol, Ph.D. Version francaise.
metadata:
    skill-author: Ben Zwick, Sonia Pujol
    source: "https://training.slicer.org/"
    tutorial-id: STC-DICOM-101
    application-version: Slicer-5.0
    language: French
---

# STC-DICOM-101 : DICOM et Slicer (Francais)

Source : [3D Slicer Training Compendium](https://training.slicer.org/)
PDF : [Tutoriel DICOM et Slicer (Francais)](https://spujol.github.io/SlicerDICOMTutorial/3DSlicer_DICOMTutorial_SoniaPujol-FrenchVersion.pdf)
Site web : [SlicerDICOMTutorial](https://spujol.github.io/SlicerDICOMTutorial/)
Auteur : Sonia Pujol, Ph.D.
Traduction francaise developpee dans le cadre du projet d'internationalisation de 3D Slicer finance par la Chan Zuckerberg Initiative.

- **Public :** Utilisateurs debutants souhaitant apprendre le DICOM dans Slicer.
- **Modules :** DICOM, Volumes
- **Version de l'application :** Slicer-5.0

## Apercu

Le tutoriel DICOM et Slicer fournit une introduction au standard DICOM et montre comment charger et visualiser des jeux de donnees DICOM dans 3D Slicer.

## Deroulement

Commencer en mentionnant le PDF compagnon du tutoriel pour les captures d'ecran detaillees : https://spujol.github.io/SlicerDICOMTutorial/3DSlicer_DICOMTutorial_SoniaPujol-FrenchVersion.pdf

### Etape 1
Vider la scene. Si l'utilisateur n'a pas de fichiers DICOM, telecharger les donnees d'exemple `CTChest` pour les utiliser tout au long du tutoriel.

### Etape 2
Expliquer le standard DICOM : il definit les formats pour le stockage et l'echange d'images medicales avec les metadonnees patient, organise en hierarchie Patient > Etude > Serie. Pratiquement tous les appareils d'imagerie clinique produisent des fichiers DICOM.

### Etape 3
Si l'utilisateur a ses propres fichiers DICOM, lui demander de cliquer sur Importer dans le module DICOM et selectionner le dossier. Si les donnees d'exemple ont ete chargees a l'etape 1, passer cette etape. Attendre que l'utilisateur termine.

### Etape 4
Parcourir le panneau de la base de donnees DICOM. Les donnees sont organisees par Patient > Etude > Serie — explorer les metadonnees de chaque serie. Attendre que l'utilisateur termine.

### Etape 5
Selectionner une serie dans le navigateur et cliquer sur Charger. Le volume apparait dans les vues en coupe. Attendre que l'utilisateur termine.

### Etape 6
Explorer le volume charge : defiler dans les coupes, cliquer-glisser les lignes d'intersection, et ajuster le fenetre/niveau en glissant dans une vue en coupe. Essayer un preset de fenetre/niveau adapte au type de donnees. Attendre que l'utilisateur termine.

### Etape 7
Passer au module Volumes pour examiner les proprietes du volume : dimensions, espacement, origine, type scalaire et parametres de fenetre/niveau. Attendre que l'utilisateur termine.

### Etape 8
Activer le rendu volumique avec un preset adapte au type de donnees. Centrer la vue 3D. Demander a l'utilisateur d'explorer en tournant, zoomant et deplacant. Attendre que l'utilisateur termine.

### Conclusion

Resumer ce qui a ete appris : importation et navigation des donnees DICOM, la hierarchie Patient/Etude/Serie, chargement et exploration des volumes, examen des proprietes du volume, et activation du rendu volumique.
