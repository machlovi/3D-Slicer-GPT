---
name: slicer-dicom-tutorial-spanish
description: STC-DICOM-101 Tutorial DICOM y Slicer. Proporciona una introduccion al estandar DICOM y muestra como cargar y visualizar conjuntos de datos DICOM en 3D Slicer. Del Compendio de Formacion 3D Slicer por Sonia Pujol, Ph.D. Version en espanol.
metadata:
    skill-author: Ben Zwick, Sonia Pujol
    source: "https://training.slicer.org/"
    tutorial-id: STC-DICOM-101
    application-version: Slicer-5.0
    language: Spanish
---

# STC-DICOM-101: DICOM y Slicer (Espanol)

Fuente: [3D Slicer Training Compendium](https://training.slicer.org/)
PDF: [Tutorial DICOM y Slicer (Espanol)](https://slicerlatinamerica.github.io/media/Tutorials/3DSlicerDICOMTutorial-SPujol_es_419.pdf)
Autora: Sonia Pujol, Ph.D.
Traduccion al espanol disponible a traves de la comunidad Slicer Latin America.

- **Publico:** Usuarios principiantes que desean aprender sobre DICOM en Slicer.
- **Modulos:** DICOM, Volumes
- **Version de la aplicacion:** Slicer-5.0

## Descripcion general

El tutorial DICOM y Slicer proporciona una introduccion al estandar DICOM y muestra como cargar y visualizar conjuntos de datos DICOM en 3D Slicer.

## Flujo de trabajo

Comenzar mencionando el PDF complementario del tutorial para capturas de pantalla detalladas: https://slicerlatinamerica.github.io/media/Tutorials/3DSlicerDICOMTutorial-SPujol_es_419.pdf

### Paso 1
Limpiar la escena. Si el usuario no tiene archivos DICOM, descargar los datos de ejemplo `CTChest` para usar durante el tutorial.

### Paso 2
Explicar el estandar DICOM: define formatos para almacenamiento e intercambio de imagenes medicas con metadatos de pacientes, organizado en la jerarquia Paciente > Estudio > Serie. Practicamente todos los dispositivos de imagen clinica producen archivos DICOM.

### Paso 3
Si el usuario tiene sus propios archivos DICOM, pedirle que haga clic en Importar en el modulo DICOM y seleccione la carpeta. Si los datos de ejemplo se cargaron en el Paso 1, omitir este paso. Esperar a que el usuario termine.

### Paso 4
Explorar el panel de la base de datos DICOM. Los datos estan organizados por Paciente > Estudio > Serie — examinar los metadatos de cada serie. Esperar a que el usuario termine.

### Paso 5
Seleccionar una serie en el navegador y hacer clic en Cargar. El volumen aparece en las vistas de corte. Esperar a que el usuario termine.

### Paso 6
Explorar el volumen cargado: desplazarse por los cortes, hacer clic y arrastrar las lineas de interseccion, y ajustar el nivel de ventana arrastrando en una vista de corte. Probar un preset de ventana/nivel adecuado para el tipo de datos. Esperar a que el usuario termine.

### Paso 7
Acceder al modulo Volumes para examinar las propiedades del volumen: dimensiones, espaciado, origen, tipo escalar y configuraciones de ventana/nivel. Esperar a que el usuario termine.

### Paso 8
Activar el renderizado volumetrico con un preset adecuado al tipo de datos. Centrar la vista 3D. Pedir al usuario que explore girando, acercando y desplazando. Esperar a que el usuario termine.

### Conclusion

Resumir lo aprendido: importacion y exploracion de datos DICOM, la jerarquia Paciente/Estudio/Serie, carga y exploracion de volumenes, examen de propiedades del volumen, y activacion del renderizado volumetrico.
