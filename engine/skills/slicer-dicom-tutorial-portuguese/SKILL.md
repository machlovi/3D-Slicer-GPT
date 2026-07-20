---
name: slicer-dicom-tutorial-portuguese
description: STC-DICOM-101 Tutorial DICOM e Slicer. Fornece uma introducao ao padrao DICOM e mostra como carregar e visualizar conjuntos de dados DICOM no 3D Slicer. Do Compendio de Treinamento 3D Slicer por Sonia Pujol, Ph.D. Versao em portugues.
metadata:
    skill-author: Ben Zwick, Sonia Pujol
    source: "https://training.slicer.org/"
    tutorial-id: STC-DICOM-101
    application-version: Slicer-5.0
    language: Portuguese
---

# STC-DICOM-101: DICOM e Slicer (Portugues)

Fonte: [3D Slicer Training Compendium](https://training.slicer.org/)
PDF: [Tutorial DICOM e Slicer (Portugues)](https://slicerlatinamerica.github.io/media/Tutorials/3DSlicerDICOMTutorial-SPujol_pt_BR.pdf)
Autora: Sonia Pujol, Ph.D.
Traducao em portugues disponibilizada pela comunidade Slicer Latin America.

- **Publico:** Usuarios iniciantes que desejam aprender sobre DICOM no Slicer.
- **Modulos:** DICOM, Volumes
- **Versao do aplicativo:** Slicer-5.0

## Visao geral

O tutorial DICOM e Slicer fornece uma introducao ao padrao DICOM e mostra como carregar e visualizar conjuntos de dados DICOM no 3D Slicer.

## Fluxo de trabalho

Comecar mencionando o PDF complementar do tutorial para capturas de tela detalhadas: https://slicerlatinamerica.github.io/media/Tutorials/3DSlicerDICOMTutorial-SPujol_pt_BR.pdf

### Etapa 1
Limpar a cena. Se o usuario nao tiver arquivos DICOM, baixar os dados de exemplo `CTChest` para usar durante o tutorial.

### Etapa 2
Explicar o padrao DICOM: ele define formatos para armazenamento e troca de imagens medicas com metadados de pacientes, organizado na hierarquia Paciente > Estudo > Serie. Praticamente todos os dispositivos de imagem clinica produzem arquivos DICOM.

### Etapa 3
Se o usuario tiver seus proprios arquivos DICOM, pedir que clique em Importar no modulo DICOM e selecione a pasta. Se os dados de exemplo foram carregados na Etapa 1, pular esta etapa. Aguardar que o usuario termine.

### Etapa 4
Navegar pelo painel do banco de dados DICOM. Os dados sao organizados por Paciente > Estudo > Serie — explorar os metadados de cada serie. Aguardar que o usuario termine.

### Etapa 5
Selecionar uma serie no navegador e clicar em Carregar. O volume aparece nas visualizacoes de fatias. Aguardar que o usuario termine.

### Etapa 6
Explorar o volume carregado: rolar pelas fatias, clicar e arrastar as linhas de intersecao, e ajustar o nivel de janela arrastando em uma visualizacao de fatia. Experimentar um preset de janela/nivel adequado ao tipo de dados. Aguardar que o usuario termine.

### Etapa 7
Acessar o modulo Volumes para examinar as propriedades do volume: dimensoes, espacamento, origem, tipo escalar e configuracoes de janela/nivel. Aguardar que o usuario termine.

### Etapa 8
Ativar a renderizacao volumetrica com um preset adequado ao tipo de dados. Centrar a visualizacao 3D. Pedir ao usuario para explorar girando, dando zoom e deslocando. Aguardar que o usuario termine.

### Conclusao

Resumir o que foi aprendido: importacao e navegacao de dados DICOM, a hierarquia Paciente/Estudo/Serie, carregamento e exploracao de volumes, exame das propriedades do volume, e ativacao da renderizacao volumetrica.
