---
name: my-segment-skill-multilingual
description: Segmentation workflow for brain MRI datasets, with instructions in multiple languages.
metadata:
    skill-author: Talk2View
---

# Mon Skill de Segmentation Multilingue

## Datensätze

Verarbeite diese Datensätze aus den Slicer-Beispieldaten der Reihe nach:

- MR Brain Tumor 1
- MR Brain Tumor 2

## Segmentos

Para cada conjunto de dados, crie estes segmentos:

| Name       | Color |
| ---------- | ----- |
| Tumor      | red   |
| Ventricles | blue  |

## Jak segmentować

### Tumor

Bruuch de Adaptive Brush mit em MRI T1+GD enhancing tumor preset, mol uf RAS [-5, 27, 28] mit 20 mm Radius

### Ventricles

Primero, salta a RAS [18, 21, 1] en todas las vistas de corte, que está cerca de donde están los ventrículos.
然后使用 Adaptive Brush，选择 simple threshold 算法，半径 7 mm，threshold zone 30%。

## Munkafolyamat

Assicurati che la scena sia vuota prima di creare una nuova segmentazione.

각 데이터셋에 대해:

1. Pobierz przykładowe dane
2. أنشئ تجزئة مع الجزء الأول من الجدول
3. सक्रिय करें tool को specified preset या algorithm के साथ, फिर कोई भी extras लागू करें
4. 3D'de segmentasyonu göster ve eğer segment zaten boyanmışsa ve boş değilse, tüm dilim görünümlerinde segmente atla
5. Diga ao usuário que ele pode refinar o segmento agora e aguarde até que termine
6. Wann de Benutzer fertig isch, füeg s nächscht Segment dezue und fang wieder bi Schritt 3 aa
7. Quand tous les segments sont terminés, rapportez le volume de chaque segment, sauvegardez la scène, et videz la scène avant de passer au jeu de données suivant
