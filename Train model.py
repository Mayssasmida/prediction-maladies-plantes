
import os
import json
import numpy as np
import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2 
from tensorflow.keras import layers, Model 
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint

# ─────────────────────────────────────────
# 1. CONFIGURATION
# ─────────────────────────────────────────
DATASET_DIR   = "plantvillage"   # chemin vers ton dossier PlantVillage
IMG_SIZE      = (224, 224)       # taille d'entrée de MobileNetV2
BATCH_SIZE    = 32
EPOCHS        = 15               # augmente si tu as un GPU
LEARNING_RATE = 0.001

# ─────────────────────────────────────────
# 2. CHARGEMENT ET AUGMENTATION DES IMAGES
# ─────────────────────────────────────────
# ImageDataGenerator gère automatiquement le split train/validation
# et applique des transformations pour éviter le surapprentissage
train_datagen = ImageDataGenerator(
    rescale=1.0 / 255,          # normalise les pixels entre 0 et 1
    validation_split=0.2,        # 20% des images pour la validation
    rotation_range=20,           # rotation aléatoire jusqu'à 20°
    width_shift_range=0.1,       # décalage horizontal léger
    height_shift_range=0.1,      # décalage vertical léger
    horizontal_flip=True,        # miroir horizontal aléatoire
    zoom_range=0.1               # zoom léger
)

val_datagen = ImageDataGenerator(
    rescale=1.0 / 255,
    validation_split=0.2
)

print("📂 Chargement des images depuis :", DATASET_DIR)

train_generator = train_datagen.flow_from_directory(
    DATASET_DIR,
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode="categorical",
    subset="training",
    shuffle=True,
    seed=42
)

val_generator = val_datagen.flow_from_directory(
    DATASET_DIR,
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode="categorical",
    subset="validation",
    shuffle=False,
    seed=42
)

NUM_CLASSES = train_generator.num_classes
print(f"✅ {NUM_CLASSES} classes détectées")
print(f"✅ {train_generator.samples} images d'entraînement")
print(f"✅ {val_generator.samples} images de validation")

# Sauvegarde de la liste des classes (utile pour mqtt_client.py)
class_indices = train_generator.class_indices
class_names   = {v: k for k, v in class_indices.items()}  # index → nom

with open("class_names.json", "w") as f:
    json.dump(class_names, f, ensure_ascii=False, indent=2)
print("💾 class_names.json sauvegardé")

# ─────────────────────────────────────────
# 3. CONSTRUCTION DU MODÈLE (TRANSFER LEARNING)
# ─────────────────────────────────────────
# MobileNetV2 a été pré-entraîné sur ImageNet (millions d'images)
# On réutilise ses couches pour reconnaître les formes, textures...
# et on ajoute nos propres couches pour les 38 maladies de plantes.

base_model = MobileNetV2(
    weights="imagenet",          # poids pré-entraînés
    include_top=False,           # on enlève la tête de classification originale
    input_shape=(224, 224, 3)    # 224x224 pixels, 3 canaux RGB
)

# Phase 1 : on gèle la base → seule notre tête s'entraîne
base_model.trainable = False

# Notre tête de classification personnalisée
x = base_model.output
x = layers.GlobalAveragePooling2D()(x)    # compresse les features en vecteur
x = layers.Dense(256, activation="relu")(x)  # couche dense
x = layers.Dropout(0.3)(x)               # régularisation contre l'overfitting
output = layers.Dense(NUM_CLASSES, activation="softmax")(x)  # 38 classes

model = Model(inputs=base_model.input, outputs=output)

model.compile(
    optimizer=tf.keras.optimizers.Adam(LEARNING_RATE),
    loss="categorical_crossentropy",
    metrics=["accuracy"]
)

model.summary()

# ─────────────────────────────────────────
# 4. ENTRAÎNEMENT — PHASE 1 (tête seulement)
# ─────────────────────────────────────────
print("\n🚀 Phase 1 : entraînement de la tête de classification...")

callbacks = [
    EarlyStopping(patience=3, restore_best_weights=True, verbose=1),
    ModelCheckpoint("plant_disease_model.h5", save_best_only=True, verbose=1)
]

history = model.fit(
    train_generator,
    validation_data=val_generator,
    epochs=EPOCHS,
    callbacks=callbacks,
    verbose=1
)

# ─────────────────────────────────────────
# 5. FINE-TUNING — PHASE 2 (débloquer les dernières couches)
# ─────────────────────────────────────────
# On débloque les 30 dernières couches de MobileNetV2 pour
# affiner les poids sur nos images de plantes.
print("\n🔧 Phase 2 : fine-tuning des dernières couches...")

base_model.trainable = True
for layer in base_model.layers[:-30]:
    layer.trainable = False          # on gèle toutes les couches sauf les 30 dernières

model.compile(
    optimizer=tf.keras.optimizers.Adam(LEARNING_RATE / 10),  # lr plus faible pour le fine-tuning
    loss="categorical_crossentropy",
    metrics=["accuracy"]
)

history_fine = model.fit(
    train_generator,
    validation_data=val_generator,
    epochs=10,                       # moins d'epochs pour le fine-tuning
    callbacks=callbacks,
    verbose=1
)

# ─────────────────────────────────────────
# 6. ÉVALUATION FINALE
# ─────────────────────────────────────────
print("\n📊 Évaluation finale sur la validation...")
loss, acc = model.evaluate(val_generator, verbose=0)
print(f"✅ Accuracy : {acc * 100:.2f}%")
print(f"✅ Loss     : {loss:.4f}")
print("\n💾 Modèle sauvegardé dans : plant_disease_model.h5")
print("💾 Classes sauvegardées dans : class_names.json")