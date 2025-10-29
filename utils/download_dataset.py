import os
import kaggle

os.makedirs('./data', exist_ok=True)

#Importing dataset from Kaggle. Must have token in .kaggle folder. It downloads and unzip: images, obs_and_meta, and bonus folders
kaggle.api.authenticate()
kaggle.api.dataset_download_files('travisdaws/spatiotemporal-wildlife-dataset', path='./data', unzip=True)